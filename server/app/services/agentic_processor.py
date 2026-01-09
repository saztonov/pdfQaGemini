"""Agentic loop processor for server-side LLM orchestration.

This module handles the agentic loop on the server:
1. Call model with context_catalog
2. Process request_files actions: download from R2 -> upload to Gemini
3. Call model again with new files
4. Repeat until is_final=true or max iterations

Reference documentation:
- Gemini SDK: https://googleapis.github.io/python-genai/
- R2 S3 API: https://developers.cloudflare.com/r2/api/s3/api/
"""

import sys
import json
import logging
import mimetypes
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

# Ensure server imports take precedence
_server_path = Path(__file__).resolve().parents[2]
if str(_server_path) not in sys.path:
    sys.path.insert(0, str(_server_path))

from app.services.gemini_client import GeminiClient
from app.services.r2_async import R2AsyncClient
from app.services.pdf_renderer import PDFRenderer

# Import from shared for build_user_prompt
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from shared.agent_core import build_user_prompt

if TYPE_CHECKING:
    from app.services.agent import Agent

logger = logging.getLogger(__name__)

# Maximum iterations for agentic loop
MAX_ITERATIONS = 5


@dataclass
class AgenticContext:
    """Context for agentic loop execution"""

    conversation_id: str
    user_text: str
    system_prompt: str
    user_text_template: str
    model_name: str
    thinking_level: str
    thinking_budget: Optional[int]
    file_refs: list[dict] = field(default_factory=list)
    context_catalog: str = ""
    history: list[dict] = field(default_factory=list)

    # Parsed context catalog for quick lookup
    _catalog_lookup: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Parse context_catalog JSON into lookup dict"""
        if self.context_catalog:
            try:
                catalog_list = json.loads(self.context_catalog)
                for item in catalog_list:
                    ctx_id = item.get("context_item_id")
                    if ctx_id:
                        self._catalog_lookup[ctx_id] = item
                logger.info(f"Parsed context_catalog: {len(self._catalog_lookup)} items")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse context_catalog: {e}")

    def get_r2_key_for_block(self, context_item_id: str) -> Optional[str]:
        """Get R2 key for a block/crop by its context_item_id"""
        item = self._catalog_lookup.get(context_item_id)
        if item:
            return item.get("r2_key")
        return None

    def get_r2_url_for_block(self, context_item_id: str) -> Optional[str]:
        """Get full R2 URL for a block/crop by its context_item_id"""
        item = self._catalog_lookup.get(context_item_id)
        if item:
            return item.get("r2_url")
        return None

    def get_item_info(self, context_item_id: str) -> Optional[dict]:
        """Get full item info from catalog"""
        return self._catalog_lookup.get(context_item_id)


@dataclass
class AgenticLoopResult:
    """Result of agentic loop execution"""

    assistant_text: str
    actions: list[dict]
    is_final: bool
    iterations: int
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    files_loaded: list[str] = field(default_factory=list)


class AgenticProcessor:
    """Handles agentic loop processing on the server.

    Uses:
    - GeminiClient for model calls and file uploads
    - R2AsyncClient for downloading crops from R2 storage
    - PDFRenderer for ROI extraction at high resolution
    - Agent for orchestrating Gemini API calls
    """

    def __init__(
        self,
        gemini_client: GeminiClient,
        r2_client: R2AsyncClient,
        agent: "Agent",
        pdf_renderer: Optional[PDFRenderer] = None,
    ):
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.agent = agent
        self.pdf_renderer = pdf_renderer or PDFRenderer()

    async def run_agentic_loop(
        self,
        ctx: AgenticContext,
    ) -> AgenticLoopResult:
        """Run agentic loop until is_final or max iterations.

        Args:
            ctx: Agentic context with all parameters

        Returns:
            AgenticLoopResult with final response and metadata
        """
        current_file_refs = list(ctx.file_refs)
        files_loaded = []

        total_input_tokens = 0
        total_output_tokens = 0
        total_latency_ms = 0.0

        for iteration in range(MAX_ITERATIONS):
            logger.info(f"=== Agentic iteration {iteration + 1}/{MAX_ITERATIONS} ===")
            logger.info(f"  Files: {len(current_file_refs)}, Catalog items: {len(ctx._catalog_lookup)}")

            # Build prompt with context_catalog (first iteration only)
            if iteration == 0 and ctx.context_catalog:
                user_prompt = build_user_prompt(
                    question=ctx.user_text,
                    context_catalog_json=ctx.context_catalog,
                    user_text_template=ctx.user_text_template,
                )
            else:
                # Follow-up iterations use original question
                user_prompt = ctx.user_text

            # Call agent
            result = await self.agent.ask_question(
                user_text=user_prompt,
                file_refs=current_file_refs,
                model=ctx.model_name,
                system_prompt=ctx.system_prompt,
                thinking_level=ctx.thinking_level,
                thinking_budget=ctx.thinking_budget,
                history=ctx.history if iteration == 0 else None,  # History only on first call
            )

            # Accumulate metrics
            total_input_tokens += result.input_tokens or 0
            total_output_tokens += result.output_tokens or 0
            total_latency_ms += result.latency_ms or 0.0

            logger.info(
                f"  Reply: is_final={result.is_final}, "
                f"actions={len(result.actions)}, "
                f"tokens={result.total_tokens}"
            )

            # Check if final
            if result.is_final:
                logger.info(f"Agentic loop completed at iteration {iteration + 1}")
                return AgenticLoopResult(
                    assistant_text=result.assistant_text,
                    actions=result.actions,
                    is_final=True,
                    iterations=iteration + 1,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    total_tokens=total_input_tokens + total_output_tokens,
                    latency_ms=total_latency_ms,
                    files_loaded=files_loaded,
                )

            # Process actions
            should_continue = False

            for action_dict in result.actions:
                action_type = action_dict.get("type")

                if action_type == "request_files":
                    # Get items from flat schema or payload
                    items = action_dict.get("items") or []
                    if not items and action_dict.get("payload"):
                        items = action_dict["payload"].get("items", [])

                    if items:
                        new_refs = await self._process_request_files(ctx, items)
                        if new_refs:
                            current_file_refs.extend(new_refs)
                            files_loaded.extend([
                                item.get("context_item_id", "unknown")
                                for item in items
                                if item.get("context_item_id")
                            ])
                            should_continue = True
                            logger.info(f"  Loaded {len(new_refs)} new files")
                    else:
                        logger.warning("  request_files action without items")

                elif action_type == "final":
                    # Explicit final action
                    logger.info("  Explicit final action")
                    return AgenticLoopResult(
                        assistant_text=result.assistant_text,
                        actions=result.actions,
                        is_final=True,
                        iterations=iteration + 1,
                        total_input_tokens=total_input_tokens,
                        total_output_tokens=total_output_tokens,
                        total_tokens=total_input_tokens + total_output_tokens,
                        latency_ms=total_latency_ms,
                        files_loaded=files_loaded,
                    )

                elif action_type == "request_roi":
                    # Check if model provided bbox coordinates for auto-processing
                    roi_ref = await self._process_request_roi(ctx, action_dict)
                    if roi_ref:
                        current_file_refs.append(roi_ref)
                        files_loaded.append(f"roi_{action_dict.get('image_context_item_id', 'unknown')}")
                        should_continue = True
                        logger.info("  Processed ROI with provided bbox")
                    else:
                        # No bbox provided - ROI requires user interaction
                        # Return current result so client can handle
                        logger.info("  request_roi requires client interaction (no bbox)")
                        return AgenticLoopResult(
                            assistant_text=result.assistant_text,
                            actions=result.actions,
                            is_final=False,
                            iterations=iteration + 1,
                            total_input_tokens=total_input_tokens,
                            total_output_tokens=total_output_tokens,
                            total_tokens=total_input_tokens + total_output_tokens,
                            latency_ms=total_latency_ms,
                            files_loaded=files_loaded,
                        )

            # If no continue actions, return current result
            if not should_continue:
                logger.info(f"No more actions to process at iteration {iteration + 1}")
                return AgenticLoopResult(
                    assistant_text=result.assistant_text,
                    actions=result.actions,
                    is_final=result.is_final,
                    iterations=iteration + 1,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    total_tokens=total_input_tokens + total_output_tokens,
                    latency_ms=total_latency_ms,
                    files_loaded=files_loaded,
                )

        # Max iterations reached
        logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached")
        return AgenticLoopResult(
            assistant_text=result.assistant_text if result else "Превышен лимит итераций",
            actions=result.actions if result else [],
            is_final=False,
            iterations=MAX_ITERATIONS,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tokens=total_input_tokens + total_output_tokens,
            latency_ms=total_latency_ms,
            files_loaded=files_loaded,
        )

    async def _process_request_files(
        self,
        ctx: AgenticContext,
        items: list[dict],
    ) -> list[dict]:
        """Process request_files action - download from R2 and upload to Gemini.

        Args:
            ctx: Agentic context with catalog lookup
            items: List of items to fetch, each with context_item_id

        Returns:
            List of new file_refs for Gemini API
        """
        new_refs = []

        for item in items:
            context_item_id = item.get("context_item_id")
            if not context_item_id:
                logger.warning("  Item without context_item_id, skipping")
                continue

            # Look up R2 URL or key from catalog
            r2_url = ctx.get_r2_url_for_block(context_item_id)
            r2_key = ctx.get_r2_key_for_block(context_item_id)

            if not r2_url and not r2_key:
                logger.warning(f"  No r2_url or r2_key found for {context_item_id}")
                continue

            item_info = ctx.get_item_info(context_item_id)

            try:
                # Download from R2 (prefer URL, fall back to key)
                if r2_url:
                    logger.info(f"  Downloading {context_item_id} from URL: {r2_url}")
                    data = await self.r2_client.download_from_url(r2_url)
                else:
                    logger.info(f"  Downloading {context_item_id} from R2 key: {r2_key}")
                    data = await self.r2_client.download_bytes(r2_key)

                if not data:
                    logger.warning(f"  Empty data for {context_item_id}")
                    continue

                # Determine mime type
                mime_type = mimetypes.guess_type(r2_key)[0] or "application/pdf"

                # Upload to Gemini
                logger.info(f"  Uploading {context_item_id} to Gemini ({len(data)} bytes)")
                upload_result = await self.gemini_client.upload_bytes(
                    data=data,
                    mime_type=mime_type,
                    display_name=f"{context_item_id}.pdf",
                )

                gemini_uri = upload_result.get("uri")
                if gemini_uri:
                    new_refs.append({
                        "uri": gemini_uri,
                        "mime_type": mime_type,
                        "display_name": upload_result.get("display_name"),
                    })
                    logger.info(f"  Uploaded {context_item_id}: {gemini_uri}")

            except Exception as e:
                logger.error(f"  Failed to load {context_item_id}: {e}", exc_info=True)

        return new_refs

    async def _process_request_roi(
        self,
        ctx: AgenticContext,
        action_dict: dict,
    ) -> Optional[dict]:
        """Process request_roi action - render zoomed region and upload to Gemini.

        Only processes if model provided bbox coordinates. Otherwise returns None
        to signal that client interaction is needed.

        Args:
            ctx: Agentic context with catalog lookup
            action_dict: The request_roi action dict

        Returns:
            File ref dict for Gemini API, or None if bbox not provided
        """
        # Extract bbox coordinates from flat schema
        bbox_x1 = action_dict.get("bbox_x1")
        bbox_y1 = action_dict.get("bbox_y1")
        bbox_x2 = action_dict.get("bbox_x2")
        bbox_y2 = action_dict.get("bbox_y2")

        # Check nested payload schema
        if bbox_x1 is None and action_dict.get("payload"):
            payload = action_dict["payload"]
            suggested_bbox = payload.get("suggested_bbox_norm")
            if suggested_bbox:
                bbox_x1 = suggested_bbox.get("x1")
                bbox_y1 = suggested_bbox.get("y1")
                bbox_x2 = suggested_bbox.get("x2")
                bbox_y2 = suggested_bbox.get("y2")

        # If no bbox provided, can't process on server
        if not all(v is not None for v in [bbox_x1, bbox_y1, bbox_x2, bbox_y2]):
            logger.info("  No bbox coordinates provided for request_roi")
            return None

        # Get image context_item_id
        image_context_item_id = action_dict.get("image_context_item_id")
        if not image_context_item_id and action_dict.get("payload"):
            image_ref = action_dict["payload"].get("image_ref", {})
            image_context_item_id = image_ref.get("context_item_id")

        if not image_context_item_id:
            logger.warning("  request_roi without image_context_item_id")
            return None

        # Get R2 URL or key for the crop
        r2_url = ctx.get_r2_url_for_block(image_context_item_id)
        r2_key = ctx.get_r2_key_for_block(image_context_item_id)

        if not r2_url and not r2_key:
            logger.warning(f"  No r2_url or r2_key found for {image_context_item_id}")
            return None

        # Get DPI (default 400)
        dpi = action_dict.get("dpi") or 400
        if action_dict.get("payload"):
            dpi = action_dict["payload"].get("dpi") or dpi

        try:
            # Download crop from R2 (prefer URL, fall back to key)
            if r2_url:
                logger.info(f"  Downloading crop for ROI from URL: {r2_url}")
                pdf_data = await self.r2_client.download_from_url(r2_url)
            else:
                logger.info(f"  Downloading crop for ROI from R2 key: {r2_key}")
                pdf_data = await self.r2_client.download_bytes(r2_key)

            if not pdf_data:
                logger.warning(f"  Empty data for {image_context_item_id}")
                return None

            # Render ROI at high resolution
            bbox_norm = (bbox_x1, bbox_y1, bbox_x2, bbox_y2)
            logger.info(f"  Rendering ROI: bbox={bbox_norm}, dpi={dpi}")
            roi_png = self.pdf_renderer.render_roi(
                pdf_data=pdf_data,
                bbox_norm=bbox_norm,
                page_num=0,
                dpi=dpi,
            )

            if not roi_png:
                logger.warning("  Failed to render ROI")
                return None

            # Upload ROI to Gemini
            display_name = f"roi_{image_context_item_id}_{dpi}dpi.png"
            logger.info(f"  Uploading ROI to Gemini: {display_name} ({len(roi_png)} bytes)")

            upload_result = await self.gemini_client.upload_bytes(
                data=roi_png,
                mime_type="image/png",
                display_name=display_name,
            )

            gemini_uri = upload_result.get("uri")
            if gemini_uri:
                logger.info(f"  ROI uploaded: {gemini_uri}")
                return {
                    "uri": gemini_uri,
                    "mime_type": "image/png",
                    "display_name": display_name,
                    "is_roi": True,
                }

            return None

        except Exception as e:
            logger.error(f"  Failed to process ROI for {image_context_item_id}: {e}", exc_info=True)
            return None
