"""Build context_catalog from node files for agentic prompt."""

import json
import logging
from typing import Optional
from uuid import UUID

from app.models.schemas import NodeFile, FileType

logger = logging.getLogger(__name__)


def build_context_catalog(crops: list[NodeFile], node_id: str) -> list[dict]:
    """
    Build context_catalog from crop files.

    Args:
        crops: List of NodeFile objects with file_type='crop'
        node_id: The document node ID

    Returns:
        List of context items with block_id, kind, page_index, etc.
    """
    catalog = []

    for crop in crops:
        if crop.file_type != FileType.CROP.value:
            continue

        block_id = crop.metadata.get("block_id")
        if not block_id:
            logger.warning(f"Crop {crop.file_name} has no block_id in metadata")
            continue

        item = {
            "context_item_id": block_id,
            "kind": "crop",
            "page_index": crop.metadata.get("page_index"),
            "block_type": crop.metadata.get("block_type", "unknown"),
            "r2_key": crop.r2_key,
            "node_id": str(crop.node_id),
        }

        # Add bbox if available
        coords = crop.metadata.get("coords_norm")
        if coords:
            item["bbox"] = coords

        catalog.append(item)

    logger.info(f"Built context_catalog with {len(catalog)} items for node {node_id}")
    return catalog


def context_catalog_to_json(catalog: list[dict]) -> str:
    """Convert context_catalog to JSON string for prompt."""
    return json.dumps(catalog, ensure_ascii=False, indent=2)


async def build_context_catalog_from_gemini_file(
    supabase_repo,
    gemini_file_data: dict,
) -> Optional[list[dict]]:
    """
    Build context_catalog from a Gemini file's saved crop_index or source_node_file_id.

    Args:
        supabase_repo: SupabaseRepo instance
        gemini_file_data: Dict with gemini file info including crop_index or source_node_file_id

    Returns:
        Context catalog or None if unable to build
    """
    # First priority: use saved crop_index directly
    crop_index = gemini_file_data.get("crop_index")
    if crop_index and isinstance(crop_index, list) and len(crop_index) > 0:
        logger.info(f"Using saved crop_index: {len(crop_index)} items")
        return crop_index

    # Fallback: try to build from source_node_file_id or source_r2_key
    source_node_file_id = gemini_file_data.get("source_node_file_id")
    source_r2_key = gemini_file_data.get("source_r2_key")

    if not source_node_file_id and not source_r2_key:
        logger.debug("Gemini file has no crop_index, source_node_file_id or source_r2_key")
        return None

    node_id = None

    # Try to get node_id from source_node_file_id
    if source_node_file_id:
        try:
            import asyncio

            def _sync_get_node_file():
                client = supabase_repo._get_client()
                response = (
                    client.table("node_files")
                    .select("node_id")
                    .eq("id", source_node_file_id)
                    .limit(1)
                    .execute()
                )
                return response.data[0]["node_id"] if response.data else None

            node_id = await asyncio.to_thread(_sync_get_node_file)

        except Exception as e:
            logger.warning(f"Failed to get node_id from source_node_file_id: {e}")

    # Try to extract node_id from r2_key
    if not node_id and source_r2_key:
        # Extract node_id from r2_key format: tree_docs/{node_id}/{filename}
        if source_r2_key.startswith("tree_docs/"):
            rel_path = source_r2_key[len("tree_docs/"):]
            parts = rel_path.split("/")
            if len(parts) >= 2:
                node_id = parts[0]

    if not node_id:
        logger.debug("Could not determine node_id for gemini file")
        return None

    # Fetch all crops for this node
    try:
        crops = await supabase_repo.fetch_node_files_single(node_id)
        crop_files = [f for f in crops if f.file_type == FileType.CROP.value]

        if not crop_files:
            logger.debug(f"No crops found for node {node_id}")
            return None

        return build_context_catalog(crop_files, node_id)

    except Exception as e:
        logger.error(f"Failed to fetch crops for node {node_id}: {e}")
        return None


async def build_context_catalog_for_conversation(
    supabase_repo,
    conversation_id: str,
) -> tuple[list[dict], set[str]]:
    """
    Build combined context_catalog from all files in conversation.

    Args:
        supabase_repo: SupabaseRepo instance
        conversation_id: Conversation ID

    Returns:
        Tuple of (combined catalog, set of node_ids used)
    """
    # Get all gemini files for conversation
    conv_files = await supabase_repo.qa_get_conversation_files(conversation_id)

    combined_catalog = []
    node_ids_used = set()

    for gemini_file in conv_files:
        catalog = await build_context_catalog_from_gemini_file(supabase_repo, gemini_file)
        if catalog:
            # Track node_id
            if catalog:
                node_id = catalog[0].get("node_id")
                if node_id:
                    node_ids_used.add(node_id)

            # Merge, avoiding duplicates by context_item_id
            existing_ids = {item["context_item_id"] for item in combined_catalog}
            for item in catalog:
                if item["context_item_id"] not in existing_ids:
                    combined_catalog.append(item)
                    existing_ids.add(item["context_item_id"])

    logger.info(
        f"Built combined context_catalog: {len(combined_catalog)} items "
        f"from {len(node_ids_used)} nodes"
    )

    return combined_catalog, node_ids_used
