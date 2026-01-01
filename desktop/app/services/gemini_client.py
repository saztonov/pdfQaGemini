"""Gemini API client"""
import asyncio
import logging
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types
from app.utils.errors import ServiceError

logger = logging.getLogger(__name__)


class GeminiClient:
    """Async wrapper for Gemini API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Optional[genai.Client] = None
    
    def _get_client(self) -> genai.Client:
        """Lazy init Gemini client"""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client
    
    async def list_models(self) -> list[dict]:
        """
        List available Gemini models.
        Returns list of dicts with: name, display_name, description
        """
        def _sync_list():
            client = self._get_client()
            try:
                logger.info("Запрос списка моделей от Gemini API...")
                models = client.models.list()
                result = []
                total_count = 0
                
                for model in models:
                    total_count += 1
                    name = getattr(model, "name", "")
                    
                    # Debug first 5 models
                    if total_count <= 5:
                        logger.info(f"Model {total_count}: name={name}")
                    
                    # Filter: include models with "gemini" in name (text generation models)
                    if "gemini" in name.lower():
                        result.append({
                            "name": name,
                            "display_name": getattr(model, "display_name", name),
                            "description": getattr(model, "description", ""),
                        })
                
                logger.info(f"Всего моделей: {total_count}, gemini-моделей: {len(result)}")
                # Log all gemini model names
                for m in result:
                    logger.info(f"  -> {m['name']}")
                return result
            except Exception as e:
                logger.error(f"Ошибка list_models: {e}", exc_info=True)
                raise ServiceError(f"Failed to list models: {e}")
        
        return await asyncio.to_thread(_sync_list)
    
    async def list_files(self) -> list[dict]:
        """
        List uploaded files in Gemini Files API.
        Returns list of dicts with: name, uri, mime_type, display_name, create_time, expiration_time
        """
        def _sync_list():
            client = self._get_client()
            try:
                files = client.files.list()
                
                result = []
                for file in files:
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
                
                return result
            except Exception as e:
                raise ServiceError(f"Failed to list Gemini files: {e}")
        
        return await asyncio.to_thread(_sync_list)
    
    async def upload_file(
        self,
        path: Path,
        mime_type: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> dict:
        """
        Upload file to Gemini Files API.
        Returns dict with: name, uri, mime_type
        """
        import logging
        logger = logging.getLogger(__name__)
        
        def _sync_upload():
            client = self._get_client()
            try:
                logger.info(f"GeminiClient.upload_file: начало загрузки файла {path}")
                logger.info(f"  - path exists: {path.exists()}")
                logger.info(f"  - mime_type (входной): {mime_type}")
                logger.info(f"  - display_name: {display_name}")
                
                # Auto-detect mime_type if not provided
                if mime_type is None:
                    import mimetypes
                    detected_type, _ = mimetypes.guess_type(str(path))
                    mime_type_final = detected_type or "application/octet-stream"
                    logger.info(f"  - mime_type авто-определен: {mime_type_final}")
                else:
                    mime_type_final = mime_type
                    logger.info(f"  - mime_type используется переданный: {mime_type_final}")
                
                # Текстовые форматы, которые безопаснее грузить как text/plain
                text_like_ext = {".json", ".html", ".htm", ".csv", ".md", ".xml"}
                text_like_mime = {"text/html", "application/json", "text/csv", "application/xml"}
                
                suffix = path.suffix.lower()
                
                if mime_type_final in text_like_mime or suffix in text_like_ext:
                    logger.warning(
                        f"  - mime '{mime_type_final}' ({suffix}) приведён к text/plain для совместимости с Gemini"
                    )
                    mime_type_final = "text/plain"
                
                # Очистка display_name от эмодзи (может вызвать проблемы в API)
                final_display_name = display_name or path.name
                # Удаляем эмодзи используя regex
                import re
                emoji_pattern = re.compile(
                    "["
                    "\U0001F600-\U0001F64F"  # emoticons
                    "\U0001F300-\U0001F5FF"  # symbols & pictographs
                    "\U0001F680-\U0001F6FF"  # transport & map symbols
                    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                    "\U00002702-\U000027B0"
                    "\U000024C2-\U0001F251"
                    "]+", 
                    flags=re.UNICODE
                )
                final_display_name = emoji_pattern.sub('', final_display_name).strip()
                if final_display_name != (display_name or path.name):
                    logger.info(f"  - display_name очищен от эмодзи: '{display_name or path.name}' -> '{final_display_name}'")
                
                # Upload
                logger.info(f"  - Вызов client.files.upload()...")
                uploaded_file = client.files.upload(
                    file=str(path),
                    config={
                        'mime_type': mime_type_final,
                        'display_name': final_display_name,
                    }
                )
                
                result = {
                    "name": uploaded_file.name,
                    "uri": uploaded_file.uri,
                    "mime_type": uploaded_file.mime_type,
                    "display_name": getattr(uploaded_file, "display_name", None),
                    "size_bytes": getattr(uploaded_file, "size_bytes", None),
                }
                
                logger.info(f"  - ✓ Файл успешно загружен: name={result['name']}")
                return result
                
            except Exception as e:
                logger.error(f"  - ✗ Ошибка загрузки файла в Gemini: {e}", exc_info=True)
                raise ServiceError(f"Failed to upload file to Gemini: {e}")
        
        return await asyncio.to_thread(_sync_upload)
    
    async def delete_file(self, name: str) -> None:
        """Delete file from Gemini Files API"""
        def _sync_delete():
            client = self._get_client()
            try:
                client.files.delete(name=name)
            except Exception as e:
                raise ServiceError(f"Failed to delete Gemini file {name}: {e}")
        
        await asyncio.to_thread(_sync_delete)
    
    async def generate_structured(
        self,
        model: str,
        system_prompt: str,
        user_text: str,
        file_refs: list[dict],
        schema: dict,
        thinking_level: str = "low",
    ) -> dict:
        """
        Generate structured output using JSON schema.
        
        Args:
            model: Model name (e.g. "gemini-3-flash")
            system_prompt: System instructions
            user_text: User message text
            file_refs: List of dicts with 'uri' and 'mime_type' keys
            schema: JSON schema for structured output
            thinking_level: "low", "medium", or "high" for reasoning depth
        
        Returns:
            Parsed JSON dict matching schema
        """
        import logging
        logger = logging.getLogger(__name__)
        
        def _sync_generate():
            client = self._get_client()
            try:
                # Build contents - files FIRST, then text (per documentation)
                # Per docs: contents=[myfile, prompt] - file objects + text
                contents_list = []
                
                # Add file objects first (get them via files.get API)
                for file_ref in file_refs:
                    uri = file_ref.get("uri", "")
                    mime_type = file_ref.get("mime_type", "application/octet-stream")
                    if uri:
                        # Extract file name from URI
                        # e.g. https://generativelanguage.googleapis.com/v1beta/files/xxx -> files/xxx
                        file_name = uri
                        if "/files/" in uri:
                            file_name = "files/" + uri.split("/files/")[-1]
                        
                        logger.info(f"Getting file: uri={uri}, name={file_name}")
                        try:
                            # Get file object from API
                            file_obj = client.files.get(name=file_name)
                            file_uri = getattr(file_obj, 'uri', None) or uri
                            file_mime = getattr(file_obj, 'mime_type', None) or mime_type or "application/octet-stream"
                            logger.info(f"  File retrieved: name={file_obj.name}, uri={file_uri}, mime={file_mime}, state={getattr(file_obj, 'state', 'unknown')}")
                            
                            # Если файл загружен как application/json - приведём к text/plain
                            if file_mime == "application/json":
                                logger.warning(f"  application/json -> text/plain для совместимости")
                                file_mime = "text/plain"
                            
                            # Use Part.from_uri with correct mime from file object
                            contents_list.append(
                                types.Part.from_uri(
                                    file_uri=file_uri,
                                    mime_type=file_mime,
                                )
                            )
                        except Exception as e:
                            logger.error(f"  Failed to get file {file_name}: {e}")
                
                # Add user text after files
                if user_text:
                    contents_list.append(user_text)
                
                # Contents is just a list of files + text
                contents = contents_list
                
                # Generation config
                # thinking_config only for models that support it (gemini-2.5+)
                logger.info(f"=== generate_structured ===")
                logger.info(f"  model (input): {model}")
                logger.info(f"  files count: {len(file_refs)}")
                logger.info(f"  user_text len: {len(user_text)}")
                
                # Config with response_json_schema (correct parameter name per docs)
                logger.info(f"  Building config for model: {model}")
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt if system_prompt else None,
                    response_mime_type="application/json",
                    response_json_schema=schema,
                )
                logger.info(f"  Using config with response_json_schema")
                
                # Remove 'models/' prefix if present - SDK adds it automatically
                model_id = model
                if model_id.startswith("models/"):
                    model_id = model_id[7:]  # Remove 'models/' prefix
                
                logger.info(f"Sending request: model_id={model_id}, files={len(file_refs)}, text_len={len(user_text)}")
                
                def _call(m: str):
                    return client.models.generate_content(
                        model=m,
                        contents=contents,
                        config=config,
                    )

                # Generate
                response = _call(model_id)

                # Prefer SDK parsed output when response_schema is used
                parsed = getattr(response, "parsed", None)
                if parsed is not None:
                    if isinstance(parsed, dict):
                        return parsed
                    # Pydantic model / typed object
                    if hasattr(parsed, "model_dump"):
                        return parsed.model_dump()
                    return dict(parsed)

                # Fallback: parse JSON from text
                import json
                result_text = getattr(response, "text", "") or ""
                logger.info(f"Response received: {len(result_text)} chars")
                return json.loads(result_text)
                
            except Exception as e:
                logger.error(f"Generate error: {e}", exc_info=True)
                raise ServiceError(f"Failed to generate structured content: {e}")
        
        return await asyncio.to_thread(_sync_generate)
    
    async def generate_simple(
        self,
        model: str,
        prompt: str,
        file_uris: Optional[list[str]] = None,
    ) -> str:
        """
        Simple text generation (non-structured).
        
        Args:
            model: Model name
            prompt: User prompt
            file_uris: Optional list of file URIs
        
        Returns:
            Generated text
        """
        def _sync_generate():
            client = self._get_client()
            try:
                # Build parts
                parts = []
                
                # Add files if any
                if file_uris:
                    for file_uri in file_uris:
                        # Extract file name and get actual mime from API
                        file_name = file_uri
                        if "/files/" in file_uri:
                            file_name = "files/" + file_uri.split("/files/")[-1]
                        try:
                            file_obj = client.files.get(name=file_name)
                            file_mime = getattr(file_obj, 'mime_type', None) or "application/octet-stream"
                            actual_uri = getattr(file_obj, 'uri', None) or file_uri
                            # Fix json mime
                            if file_mime == "application/json":
                                file_mime = "text/plain"
                            parts.append(
                                types.Part.from_uri(
                                    file_uri=actual_uri,
                                    mime_type=file_mime,
                                )
                            )
                        except Exception:
                            # Fallback - use URI as-is with generic mime
                            parts.append(
                                types.Part.from_uri(
                                    file_uri=file_uri,
                                    mime_type="application/octet-stream",
                                )
                            )
                
                # Add prompt
                parts.append(types.Part(text=prompt))
                
                # Remove 'models/' prefix if present
                model_id = model
                if model_id.startswith("models/"):
                    model_id = model_id[7:]
                
                # Generate
                def _call(m: str):
                    return client.models.generate_content(
                        model=m,
                        contents=[types.Content(role="user", parts=parts)],
                    )

                response = _call(model_id)
                
                return response.text
                
            except Exception as e:
                raise ServiceError(f"Failed to generate content: {e}")
        
        return await asyncio.to_thread(_sync_generate)
