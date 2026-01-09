"""Gemini API client - native async with aiohttp"""

import logging
import re
import json
import mimetypes
import tempfile
import os
from pathlib import Path
from typing import Optional, AsyncIterator

from google import genai
from google.genai import types

from shared.exceptions import ServiceError
from shared.retry import retry_async
from shared.models import AVAILABLE_MODELS

logger = logging.getLogger(__name__)

# Exceptions that should trigger retries
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
)

# Emoji pattern for display_name cleanup
EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f1e0-\U0001f1ff"
    "\U00002702-\U000027b0"
    "\U000024c2-\U0001f251"
    "]+",
    flags=re.UNICODE,
)


class GeminiClient:
    """Native async Gemini API client using aiohttp"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        """Lazy init Gemini client"""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def list_models(self) -> list[dict]:
        """List available Gemini models (fixed list from config)"""
        return AVAILABLE_MODELS.copy()

    @retry_async(
        max_attempts=3,
        initial_delay=1.0,
        exceptions=RETRYABLE_EXCEPTIONS,
        log_prefix="[GeminiClient] ",
    )
    async def list_files(self) -> list[dict]:
        """List uploaded files in Gemini Files API (native async)"""
        client = self._get_client()
        try:
            result = []
            async for file in await client.aio.files.list():
                file_info = {
                    "name": file.name,
                    "uri": file.uri,
                    "mime_type": file.mime_type,
                    "display_name": getattr(file, "display_name", None),
                    "create_time": getattr(file, "create_time", None),
                    "expiration_time": getattr(file, "expiration_time", None),
                    "size_bytes": getattr(file, "size_bytes", None),
                    "sha256_hash": getattr(file, "sha256_hash", None),
                }
                result.append(file_info)
                logger.debug(
                    f"Gemini file: name={file.name}, display_name={getattr(file, 'display_name', None)}"
                )

            logger.info(f"Gemini files list: {len(result)} files")
            return result
        except Exception as e:
            raise ServiceError(f"Failed to list Gemini files: {e}")

    @retry_async(
        max_attempts=3,
        initial_delay=2.0,
        exceptions=RETRYABLE_EXCEPTIONS,
        log_prefix="[GeminiClient] ",
    )
    async def upload_file(
        self,
        path: Path,
        mime_type: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> dict:
        """Upload file to Gemini Files API (native async)"""
        client = self._get_client()
        try:
            logger.info(f"GeminiClient.upload_file: starting upload {path}")

            # Auto-detect mime_type if not provided
            if mime_type is None:
                detected_type, _ = mimetypes.guess_type(str(path))
                mime_type_final = detected_type or "application/octet-stream"
            else:
                mime_type_final = mime_type

            # Text-like formats to convert to text/plain
            text_like_ext = {".json", ".html", ".htm", ".csv", ".md", ".xml"}
            text_like_mime = {"text/html", "application/json", "text/csv", "application/xml"}
            suffix = path.suffix.lower()

            if mime_type_final in text_like_mime or suffix in text_like_ext:
                logger.warning(f"  mime '{mime_type_final}' -> text/plain for compatibility")
                mime_type_final = "text/plain"

            # Clean display_name from emojis
            final_display_name = display_name or path.name
            final_display_name = EMOJI_PATTERN.sub("", final_display_name).strip()

            # Native async upload
            logger.info("  - Calling client.aio.files.upload()...")
            uploaded_file = await client.aio.files.upload(
                file=str(path),
                config=types.UploadFileConfig(
                    mime_type=mime_type_final,
                    display_name=final_display_name,
                ),
            )

            result = {
                "name": uploaded_file.name,
                "uri": uploaded_file.uri,
                "mime_type": uploaded_file.mime_type,
                "display_name": getattr(uploaded_file, "display_name", None),
                "size_bytes": getattr(uploaded_file, "size_bytes", None),
            }

            logger.info(f"  File uploaded: name={result['name']}")
            return result

        except Exception as e:
            logger.error(f"  Failed to upload file to Gemini: {e}", exc_info=True)
            raise ServiceError(f"Failed to upload file to Gemini: {e}")

    @retry_async(
        max_attempts=3,
        initial_delay=2.0,
        exceptions=RETRYABLE_EXCEPTIONS,
        log_prefix="[GeminiClient] ",
    )
    async def upload_bytes(
        self,
        data: bytes,
        mime_type: str,
        display_name: str,
    ) -> dict:
        """Upload bytes directly to Gemini Files API"""
        # Write to temp file and upload
        suffix = mimetypes.guess_extension(mime_type) or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(data)
            temp_path = Path(f.name)

        try:
            return await self.upload_file(temp_path, mime_type, display_name)
        finally:
            os.unlink(temp_path)

    async def delete_file(self, name: str) -> None:
        """Delete file from Gemini Files API (native async)"""
        client = self._get_client()
        try:
            await client.aio.files.delete(name=name)
        except Exception as e:
            raise ServiceError(f"Failed to delete Gemini file {name}: {e}")

    @retry_async(
        max_attempts=3,
        initial_delay=2.0,
        max_delay=10.0,
        exceptions=RETRYABLE_EXCEPTIONS,
        log_prefix="[GeminiClient] ",
    )
    async def generate_structured(
        self,
        model: str,
        system_prompt: str,
        user_text: str,
        file_refs: list[dict],
        schema: dict,
        thinking_level: str = "low",
        thinking_budget: Optional[int] = None,
        media_resolution: str = "low",
    ) -> dict:
        """Generate structured output using JSON schema (native async)"""
        client = self._get_client()
        try:
            # Build contents - files FIRST, then text
            contents_list = []

            for file_ref in file_refs:
                uri = file_ref.get("uri", "")
                ref_mime = file_ref.get("mime_type", "application/octet-stream")
                is_roi = file_ref.get("is_roi", False)
                if uri:
                    file_name = uri
                    if "/files/" in uri:
                        file_name = "files/" + uri.split("/files/")[-1]

                    logger.info(f"Getting file: name={file_name}, is_roi={is_roi}")
                    try:
                        file_obj = await client.aio.files.get(name=file_name)
                        file_uri = getattr(file_obj, "uri", None) or uri
                        file_mime = getattr(file_obj, "mime_type", None) or ref_mime

                        if file_mime == "application/json":
                            file_mime = "text/plain"

                        contents_list.append(
                            types.Part.from_uri(file_uri=file_uri, mime_type=file_mime)
                        )
                    except Exception as e:
                        logger.error(f"  Failed to get file {file_name}: {e}")

            if user_text:
                contents_list.append(user_text)

            # Map media_resolution string to enum
            resolution_map = {
                "low": "MEDIA_RESOLUTION_LOW",
                "medium": "MEDIA_RESOLUTION_MEDIUM",
                "high": "MEDIA_RESOLUTION_HIGH",
            }
            resolution_value = resolution_map.get(media_resolution, "MEDIA_RESOLUTION_LOW")

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                response_mime_type="application/json",
                response_json_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                media_resolution=resolution_value,
                temperature=1.0,
            )

            model_id = model.removeprefix("models/")

            logger.info(
                f"generate_structured: model={model_id}, files={len(file_refs)}, resolution={resolution_value}"
            )

            # Native async generate
            response = await client.aio.models.generate_content(
                model=model_id,
                contents=contents_list,
                config=config,
            )

            # Extract usage metadata
            usage_metadata = getattr(response, "usage_metadata", None)
            usage_dict = {}
            if usage_metadata:
                usage_dict = {
                    "input_tokens": getattr(usage_metadata, "prompt_token_count", None),
                    "output_tokens": getattr(usage_metadata, "candidates_token_count", None),
                    "total_tokens": getattr(usage_metadata, "total_token_count", None),
                }
                logger.info(
                    f"Usage: input={usage_dict['input_tokens']}, output={usage_dict['output_tokens']}"
                )

            # Prefer SDK parsed output
            parsed = getattr(response, "parsed", None)
            result = None
            if parsed is not None:
                if isinstance(parsed, dict):
                    result = parsed
                elif hasattr(parsed, "model_dump"):
                    result = parsed.model_dump()
                else:
                    result = dict(parsed)
            else:
                # Fallback: parse JSON from text
                result_text = getattr(response, "text", "") or ""
                logger.info(f"Response received: {len(result_text)} chars")
                result = json.loads(result_text)

            # Add usage to result
            if usage_dict:
                result["_usage"] = usage_dict

            return result

        except Exception as e:
            logger.error(f"Generate error: {e}", exc_info=True)
            raise ServiceError(f"Failed to generate structured content: {e}")

    @retry_async(
        max_attempts=3,
        initial_delay=2.0,
        exceptions=RETRYABLE_EXCEPTIONS,
        log_prefix="[GeminiClient] ",
    )
    async def generate_simple(
        self,
        model: str,
        prompt: str,
        file_uris: Optional[list[str]] = None,
    ) -> str:
        """Simple text generation (native async)"""
        client = self._get_client()
        try:
            parts = []

            if file_uris:
                for file_uri in file_uris:
                    file_name = file_uri
                    if "/files/" in file_uri:
                        file_name = "files/" + file_uri.split("/files/")[-1]
                    try:
                        file_obj = await client.aio.files.get(name=file_name)
                        file_mime = (
                            getattr(file_obj, "mime_type", None) or "application/octet-stream"
                        )
                        actual_uri = getattr(file_obj, "uri", None) or file_uri
                        if file_mime == "application/json":
                            file_mime = "text/plain"
                        parts.append(types.Part.from_uri(file_uri=actual_uri, mime_type=file_mime))
                    except Exception:
                        parts.append(
                            types.Part.from_uri(
                                file_uri=file_uri, mime_type="application/octet-stream"
                            )
                        )

            parts.append(types.Part(text=prompt))

            model_id = model.removeprefix("models/")

            config = types.GenerateContentConfig(temperature=1.0)

            response = await client.aio.models.generate_content(
                model=model_id,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )

            return response.text

        except Exception as e:
            raise ServiceError(f"Failed to generate content: {e}")

    async def generate_stream_with_thoughts(
        self,
        model: str,
        system_prompt: str,
        user_text: str,
        file_refs: list[dict],
        thinking_level: str = "medium",
        thinking_budget: Optional[int] = None,
    ) -> AsyncIterator[dict]:
        """Generate content with streaming and thought summaries (native async)"""
        client = self._get_client()
        accumulated_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        try:
            contents_list = []

            for file_ref in file_refs:
                uri = file_ref.get("uri", "")
                ref_mime = file_ref.get("mime_type", "application/octet-stream")
                if uri:
                    file_name = uri
                    if "/files/" in uri:
                        file_name = "files/" + uri.split("/files/")[-1]
                    try:
                        file_obj = await client.aio.files.get(name=file_name)
                        file_uri = getattr(file_obj, "uri", None) or uri
                        file_mime = getattr(file_obj, "mime_type", None) or ref_mime
                        if file_mime == "application/json":
                            file_mime = "text/plain"
                        contents_list.append(
                            types.Part.from_uri(file_uri=file_uri, mime_type=file_mime)
                        )
                    except Exception as e:
                        logger.error(f"Failed to get file {file_name}: {e}")

            if user_text:
                contents_list.append(user_text)

            thinking_config_params = {
                "thinking_level": thinking_level,
                "include_thoughts": True,
            }
            if thinking_budget is not None:
                thinking_config_params["thinking_budget"] = thinking_budget

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                thinking_config=types.ThinkingConfig(**thinking_config_params),
                temperature=1.0,
            )

            model_id = model.removeprefix("models/")

            logger.info(
                f"Streaming: model={model_id}, thinking_level={thinking_level}, budget={thinking_budget}"
            )

            # Native async streaming
            async for chunk in client.aio.models.generate_content_stream(
                model=model_id,
                contents=contents_list,
                config=config,
            ):
                if not chunk.candidates:
                    continue

                # Accumulate usage metadata from chunks
                usage_metadata = getattr(chunk, "usage_metadata", None)
                if usage_metadata:
                    accumulated_usage["input_tokens"] = (
                        getattr(usage_metadata, "prompt_token_count", 0)
                        or accumulated_usage["input_tokens"]
                    )
                    accumulated_usage["output_tokens"] = (
                        getattr(usage_metadata, "candidates_token_count", 0)
                        or accumulated_usage["output_tokens"]
                    )
                    accumulated_usage["total_tokens"] = (
                        getattr(usage_metadata, "total_token_count", 0)
                        or accumulated_usage["total_tokens"]
                    )

                for part in chunk.candidates[0].content.parts:
                    if not part.text:
                        continue

                    if part.thought:
                        thought_sig = getattr(part, "thought_signature", None)
                        yield {
                            "type": "thought",
                            "content": part.text,
                            "finished": False,
                            "thought_signature": str(thought_sig) if thought_sig else None,
                        }
                    else:
                        yield {"type": "text", "content": part.text}

            # Send final usage metadata
            if any(accumulated_usage.values()):
                yield {"type": "usage", "usage": accumulated_usage}

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            raise ServiceError(f"Streaming failed: {e}")
