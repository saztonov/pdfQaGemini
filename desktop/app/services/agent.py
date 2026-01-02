"""Agent logic - orchestrates Gemini interactions"""
import logging
from typing import Optional, AsyncIterator
from uuid import UUID
import time
from app.services.gemini_client import GeminiClient
from app.services.supabase_repo import SupabaseRepo
from app.services.trace import TraceStore, ModelTrace
from app.models.schemas import ModelReply, ModelAction

logger = logging.getLogger(__name__)


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
                        "description": "Данные действия (context_item_id, r2_key, image_ref, hint_text и т.д.)",
                        "properties": {
                            "context_item_id": {"type": "string"},
                            "r2_key": {"type": "string"},
                            "image_ref": {"type": "string"},
                            "hint_text": {"type": "string"},
                            "page": {"type": "integer"},
                            "text": {"type": "string"}
                        }
                    },
                    "note": {
                        "type": "string",
                        "description": "Опциональная заметка"
                    }
                },
                "required": ["type", "payload"]
            }
        },
        "is_final": {
            "type": "boolean",
            "description": "Является ли ответ финальным"
        }
    },
    "required": ["assistant_text"]
}


SYSTEM_PROMPT = """Ты — помощник для анализа PDF-документов.

КРИТИЧЕСКИ ВАЖНО: Отвечай СТРОГО на основе прикреплённых файлов в контексте. Используй ТОЛЬКО информацию из загруженных документов. Если файлы отсутствуют или не содержат ответа — сообщи об этом. ЗАПРЕЩЕНО использовать внешние знания или выдумывать информацию.

Правила:
- Отвечай кратко и по делу на русском языке.
- ОБЯЗАТЕЛЬНО цитируй конкретные места из документов для подтверждения ответа.
- Если нет прикреплённых файлов — верни: "Документы не загружены в контекст. Загрузите файлы в Gemini Files."
- Если информации недостаточно — укажи: "В загруженных документах нет информации по этому вопросу."
- Если нужно показать изображение — верни action "open_image" с context_item_id или r2_key.
- Если нужен ROI — верни action "request_roi" с описанием области.
- Когда ответ готов — установи is_final=true или добавь action "final".

Формат ответа: JSON с полями assistant_text, actions[], is_final.
"""


class Agent:
    """Main agent orchestrator for Q&A"""
    
    def __init__(
        self,
        gemini_client: GeminiClient,
        supabase_repo: SupabaseRepo,
        trace_store: Optional[TraceStore] = None,
    ):
        self.gemini_client = gemini_client
        self.supabase_repo = supabase_repo
        self.trace_store = trace_store
    
    async def ask(
        self,
        conversation_id: UUID,
        user_text: str,
        file_refs: list[dict],
        model: str,
        thinking_level: str = "low",
    ) -> ModelReply:
        """
        Ask question to Gemini with structured output.
        
        Args:
            conversation_id: Conversation UUID
            user_text: User question
            file_refs: List of dicts with 'uri' and 'mime_type' keys
            model: Model name (required)
            thinking_level: "low" or "high"
        
        Returns:
            ModelReply with assistant text and actions
        """
        logger.info(f"=== Agent.ask ===")
        logger.info(f"  model: {model}")
        logger.info(f"  file_refs count: {len(file_refs)}")
        for i, fr in enumerate(file_refs[:3]):
            logger.info(f"    [{i}] uri={fr.get('uri')}, mime={fr.get('mime_type')}")
        
        # Create trace
        trace = ModelTrace(
            conversation_id=conversation_id,
            model=model,
            thinking_level=thinking_level,
            system_prompt=SYSTEM_PROMPT,
            user_text=user_text,
            input_files=file_refs,
        )
        
        start_time = time.perf_counter()
        
        try:
            # Save user message
            await self.supabase_repo.qa_add_message(
                conversation_id=str(conversation_id),
                role="user",
                content=user_text,
                meta={
                    "file_refs": file_refs,
                    "model": model,
                }
            )
            
            # Generate structured response with files
            result_dict = await self.gemini_client.generate_structured(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_text=user_text,
                file_refs=file_refs,
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
                    "file_refs": file_refs,
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
    
    async def ask_stream(
        self,
        conversation_id: UUID,
        user_text: str,
        file_refs: list[dict],
        model: str,
        thinking_level: str = "medium",
    ) -> AsyncIterator[dict]:
        """
        Ask question with streaming response including thoughts.
        
        Yields dicts with:
            - type: "thought" | "text" | "done" | "error"
            - content: str
        
        Args:
            conversation_id: Conversation UUID
            user_text: User question
            file_refs: List of dicts with 'uri' and 'mime_type'
            model: Model name
            thinking_level: "low", "medium", or "high"
        """
        logger.info(f"=== Agent.ask_stream ===")
        logger.info(f"  model: {model}, thinking: {thinking_level}")
        logger.info(f"  file_refs count: {len(file_refs)}")
        
        start_time = time.perf_counter()
        
        # Save user message
        await self.supabase_repo.qa_add_message(
            conversation_id=str(conversation_id),
            role="user",
            content=user_text,
            meta={
                "file_refs": file_refs,
                "model": model,
                "thinking_level": thinking_level,
            }
        )
        
        full_thought = ""
        full_answer = ""
        
        try:
            async for chunk in self.gemini_client.generate_stream_with_thoughts(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_text=user_text,
                file_refs=file_refs,
                thinking_level=thinking_level,
            ):
                chunk_type = chunk.get("type", "")
                content = chunk.get("content", "")
                
                if chunk_type == "thought":
                    full_thought += content
                    yield {"type": "thought", "content": content}
                elif chunk_type == "text":
                    full_answer += content
                    yield {"type": "text", "content": content}
            
            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Save assistant message
            await self.supabase_repo.qa_add_message(
                conversation_id=str(conversation_id),
                role="assistant",
                content=full_answer,
                meta={
                    "model": model,
                    "thinking_level": thinking_level,
                    "thought_summary": full_thought[:500] if full_thought else None,
                    "latency_ms": latency_ms,
                }
            )
            
            yield {"type": "done", "content": full_answer}
            
        except Exception as e:
            logger.error(f"ask_stream error: {e}", exc_info=True)
            yield {"type": "error", "content": str(e)}