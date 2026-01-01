"""Agent logic - orchestrates Gemini interactions"""
from typing import Optional
from uuid import UUID
import time
from app.services.gemini_client import GeminiClient
from app.services.supabase_repo import SupabaseRepo
from app.services.trace import TraceStore, ModelTrace
from app.models.schemas import ModelReply, ModelAction


# JSON Schema for ModelReply
MODEL_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "assistant_text": {
            "type": "string",
            "description": "Текст ответа ассистента"
        },
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["answer", "open_image", "request_roi", "final"]
                    },
                    "payload": {
                        "type": "object",
                        "description": "Данные действия (context_item_id, r2_key, image_ref, hint_text и т.д.)"
                    },
                    "note": {
                        "type": "string",
                        "description": "Опциональная заметка"
                    }
                },
                "required": ["type", "payload"]
            },
            "default": []
        },
        "is_final": {
            "type": "boolean",
            "description": "Является ли ответ финальным",
            "default": False
        }
    },
    "required": ["assistant_text"]
}


SYSTEM_PROMPT = """Ты — помощник для работы с PDF-документами через Gemini API.

Правила:
- Отвечай кратко и по делу на русском языке.
- Используй прикреплённые файлы для ответа.
- Если нужно показать изображение — верни action "open_image" с context_item_id или r2_key.
- Если нужен ROI (region of interest) — верни action "request_roi" с описанием области.
- Когда закончишь — установи is_final=true или добавь action "final".

Формат ответа: JSON с полями assistant_text, actions[], is_final.
"""


class Agent:
    """Main agent orchestrator for Q&A"""
    
    def __init__(
        self,
        gemini_client: GeminiClient,
        supabase_repo: SupabaseRepo,
        trace_store: Optional[TraceStore] = None,
        default_model: str = "gemini-3-flash-preview",
    ):
        self.gemini_client = gemini_client
        self.supabase_repo = supabase_repo
        self.trace_store = trace_store
        self.default_model = default_model
    
    async def ask(
        self,
        conversation_id: UUID,
        user_text: str,
        file_uris: list[str],
        model: Optional[str] = None,
        thinking_level: str = "low",
    ) -> ModelReply:
        """
        Ask question to Gemini with structured output.
        
        Args:
            conversation_id: Conversation UUID
            user_text: User question
            file_uris: List of Gemini file URIs to include
            model: Model name (defaults to self.default_model)
            thinking_level: "low" or "high"
        
        Returns:
            ModelReply with assistant text and actions
        """
        model = model or self.default_model
        
        # Create trace
        trace = ModelTrace(
            conversation_id=conversation_id,
            model=model,
            thinking_level=thinking_level,
            system_prompt=SYSTEM_PROMPT,
            user_text=user_text,
            input_files=[{"uri": uri} for uri in file_uris],
        )
        
        start_time = time.perf_counter()
        
        try:
            # Save user message
            await self.supabase_repo.qa_add_message(
                conversation_id=str(conversation_id),
                role="user",
                content=user_text,
                meta={
                    "file_uris": file_uris,
                    "model": model,
                }
            )
            
            # Generate structured response
            result_dict = await self.gemini_client.generate_structured(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_text=user_text,
                file_uris=file_uris,
                schema=MODEL_REPLY_SCHEMA,
                thinking_level=thinking_level,
            )
            
            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Parse to ModelReply
            reply = ModelReply(**result_dict)
            
            # Update trace
            trace.response_json = result_dict
            trace.parsed_actions = [
                {"type": action.type, "payload": action.payload, "note": action.note}
                for action in reply.actions
            ]
            trace.latency_ms = latency_ms
            trace.is_final = reply.is_final
            
            # Save assistant message
            await self.supabase_repo.qa_add_message(
                conversation_id=str(conversation_id),
                role="assistant",
                content=reply.assistant_text,
                meta={
                    "model": model,
                    "thinking_level": thinking_level,
                    "file_uris": file_uris,
                    "actions": trace.parsed_actions,
                    "is_final": reply.is_final,
                    "trace_id": trace.id,
                }
            )
            
            # Store trace
            if self.trace_store:
                self.trace_store.add(trace)
            
            return reply
        
        except Exception as e:
            # Record error
            trace.errors.append(str(e))
            trace.latency_ms = (time.perf_counter() - start_time) * 1000
            
            if self.trace_store:
                self.trace_store.add(trace)
            
            raise
    
    async def load_conversation_history(self, conversation_id: UUID) -> list[dict]:
        """Load conversation message history"""
        messages = await self.supabase_repo.qa_list_messages(str(conversation_id))
        
        return [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "meta": msg.meta,
                "created_at": msg.created_at,
            }
            for msg in messages
        ]
