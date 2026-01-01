"""Gemini API client"""
import asyncio
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types
from app.utils.errors import ServiceError


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
        def _sync_upload():
            client = self._get_client()
            try:
                # Auto-detect mime_type if not provided
                if mime_type is None:
                    import mimetypes
                    detected_type, _ = mimetypes.guess_type(str(path))
                    mime_type_final = detected_type or "application/octet-stream"
                else:
                    mime_type_final = mime_type
                
                # Upload
                uploaded_file = client.files.upload(
                    path=str(path),
                    config=types.UploadFileConfig(
                        mime_type=mime_type_final,
                        display_name=display_name or path.name,
                    )
                )
                
                return {
                    "name": uploaded_file.name,
                    "uri": uploaded_file.uri,
                    "mime_type": uploaded_file.mime_type,
                    "display_name": getattr(uploaded_file, "display_name", None),
                    "size_bytes": getattr(uploaded_file, "size_bytes", None),
                }
            except Exception as e:
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
        file_uris: list[str],
        schema: dict,
        thinking_level: str = "low",
    ) -> dict:
        """
        Generate structured output using JSON schema.
        
        Args:
            model: Model name (e.g. "gemini-3-flash-preview")
            system_prompt: System instructions
            user_text: User message text
            file_uris: List of Gemini file URIs to include
            schema: JSON schema for structured output
            thinking_level: "low" or "high" for reasoning depth
        
        Returns:
            Parsed JSON dict matching schema
        """
        def _sync_generate():
            client = self._get_client()
            try:
                # Build contents
                contents = []
                
                # System prompt (as user role with marker)
                if system_prompt:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"[SYSTEM]\n{system_prompt}")],
                        )
                    )
                
                # User message with files
                user_parts = []
                
                # Add file URIs
                for file_uri in file_uris:
                    # Extract mime_type from URI or default
                    # Gemini Files API URIs typically: https://generativelanguage.googleapis.com/v1beta/files/...
                    # We need to infer or use generic
                    user_parts.append(
                        types.Part.from_uri(
                            file_uri=file_uri,
                            mime_type="application/pdf",  # Default, adjust as needed
                        )
                    )
                
                # Add user text
                if user_text:
                    user_parts.append(types.Part(text=user_text))
                
                if user_parts:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=user_parts,
                        )
                    )
                
                # Generation config
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    thinking_config=types.ThinkingConfig(
                        thinking_mode=thinking_level  # "low" or "high"
                    ) if thinking_level else None,
                )
                
                # Generate
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                
                # Parse JSON response
                import json
                result_text = response.text
                return json.loads(result_text)
                
            except Exception as e:
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
                        parts.append(
                            types.Part.from_uri(
                                file_uri=file_uri,
                                mime_type="application/pdf",
                            )
                        )
                
                # Add prompt
                parts.append(types.Part(text=prompt))
                
                # Generate
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Content(role="user", parts=parts)
                    ],
                )
                
                return response.text
                
            except Exception as e:
                raise ServiceError(f"Failed to generate content: {e}")
        
        return await asyncio.to_thread(_sync_generate)
