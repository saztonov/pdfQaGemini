"""Supabase repository - async data access without RLS"""
import asyncio
import logging
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
from supabase import create_client, Client
from app.models.schemas import TreeNode, NodeFile, Conversation, Message

logger = logging.getLogger(__name__)


class SupabaseRepo:
    """Async Supabase data access layer"""
    
    def __init__(self, url: str, key: str):
        logger.info(f"Инициализация SupabaseRepo: url={url[:30]}...")
        self.url = url
        self.key = key
        self._client: Optional[Client] = None
    
    def _get_client(self) -> Client:
        """Lazy init Supabase client"""
        if self._client is None:
            logger.info("Создание Supabase клиента...")
            self._client = create_client(self.url, self.key)
            logger.info("Supabase клиент создан успешно")
        return self._client
    
    # Tree operations
    
    async def fetch_roots(self) -> list[TreeNode]:
        """Fetch root tree nodes"""
        logger.info(f"fetch_roots вызван")
        
        def _sync_fetch():
            logger.info("_sync_fetch: получение клиента...")
            client = self._get_client()
            logger.info("_sync_fetch: выполнение запроса к tree_nodes...")
            response = (
                client.table("tree_nodes")
                .select("*")
                .is_("parent_id", "null")
                .order("sort_order")
                .order("name")
                .execute()
            )
            logger.info(f"_sync_fetch: получено {len(response.data)} записей")
            return [TreeNode(**row) for row in response.data]
        
        result = await asyncio.to_thread(_sync_fetch)
        logger.info(f"fetch_roots завершён: {len(result)} корневых узлов")
        return result
    
    async def fetch_children(self, client_id: str, parent_id: str) -> list[TreeNode]:
        """Fetch child nodes for given parent"""
        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("tree_nodes")
                .select("*")
                .eq("parent_id", parent_id)
                .order("sort_order")
                .order("name")
                .execute()
            )
            return [TreeNode(**row) for row in response.data]
        
        return await asyncio.to_thread(_sync_fetch)
    
    async def get_descendant_documents(
        self,
        client_id: str,
        root_ids: list[str],
        node_types: Optional[list[str]] = None
    ) -> list[TreeNode]:
        """Get descendant nodes via RPC, optionally filtered by node_type"""
        def _sync_fetch():
            client = self._get_client()
            params = {
                "p_root_ids": root_ids,
            }
            if node_types:
                params["p_node_types"] = node_types
            
            response = client.rpc("qa_get_descendants", params).execute()
            return [TreeNode(**row) for row in response.data]
        
        return await asyncio.to_thread(_sync_fetch)
    
    async def fetch_node_files(self, node_ids: list[str]) -> list[NodeFile]:
        """Fetch files for multiple nodes (chunked to 200)"""
        if not node_ids:
            return []
        
        def _sync_fetch(chunk: list[str]):
            client = self._get_client()
            response = (
                client.table("node_files")
                .select("*")
                .in_("node_id", chunk)
                .execute()
            )
            return [NodeFile(**row) for row in response.data]
        
        # Chunk requests
        chunk_size = 200
        chunks = [node_ids[i:i+chunk_size] for i in range(0, len(node_ids), chunk_size)]
        
        tasks = [asyncio.to_thread(_sync_fetch, chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks)
        
        # Flatten
        all_files = []
        for result in results:
            all_files.extend(result)
        return all_files
    
    async def fetch_node_files_single(self, node_id: str) -> list[NodeFile]:
        """Fetch files for single node"""
        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("node_files")
                .select("*")
                .eq("node_id", node_id)
                .order("file_type")
                .execute()
            )
            return [NodeFile(**row) for row in response.data]
        
        return await asyncio.to_thread(_sync_fetch)
    
    # QA Conversations
    
    async def qa_create_conversation(
        self,
        title: str = "",
        model_default: str = "gemini-3-flash-preview"
    ) -> Conversation:
        """Create new conversation"""
        def _sync_create():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "id": str(uuid4()),
                "client_id": "default",
                "title": title,
                "model_default": model_default,
                "created_at": now,
                "updated_at": now,
            }
            response = (
                client.table("qa_conversations")
                .insert(data)
                .execute()
            )
            return Conversation(**response.data[0])
        
        return await asyncio.to_thread(_sync_create)
    
    async def qa_add_nodes(self, conversation_id: str, node_ids: list[str]) -> None:
        """Add nodes to conversation context (upsert)"""
        if not node_ids:
            return
        
        def _sync_add():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            records = [
                {
                    "id": str(uuid4()),
                    "conversation_id": conversation_id,
                    "node_id": node_id,
                    "added_at": now,
                }
                for node_id in node_ids
            ]
            client.table("qa_conversation_nodes").upsert(
                records,
                on_conflict="conversation_id,node_id"
            ).execute()
        
        await asyncio.to_thread(_sync_add)
    
    async def qa_add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        meta: Optional[dict] = None
    ) -> Message:
        """Add message to conversation"""
        def _sync_add():
            client = self._get_client()
            data = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "meta": meta or {},
                "created_at": datetime.utcnow().isoformat(),
            }
            response = (
                client.table("qa_messages")
                .insert(data)
                .execute()
            )
            return Message(**response.data[0])
        
        return await asyncio.to_thread(_sync_add)
    
    async def qa_list_messages(self, conversation_id: str) -> list[Message]:
        """List messages in conversation"""
        def _sync_list():
            client = self._get_client()
            response = (
                client.table("qa_messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at")
                .execute()
            )
            return [Message(**row) for row in response.data]
        
        return await asyncio.to_thread(_sync_list)
    
    # Gemini Files
    
    async def qa_upsert_gemini_file(
        self,
        gemini_name: str,
        gemini_uri: str,
        display_name: str,
        mime_type: str,
        size_bytes: Optional[int] = None,
        sha256: Optional[str] = None,
        source_node_file_id: Optional[str] = None,
        source_r2_key: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> dict:
        """Upsert Gemini File cache entry"""
        def _sync_upsert():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "client_id": "default",
                "gemini_name": gemini_name,
                "gemini_uri": gemini_uri,
                "display_name": display_name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "source_node_file_id": source_node_file_id,
                "source_r2_key": source_r2_key,
                "expires_at": expires_at,
                "updated_at": now,
            }
            response = (
                client.table("qa_gemini_files")
                .upsert(data, on_conflict="gemini_name")
                .execute()
            )
            return response.data[0]
        
        return await asyncio.to_thread(_sync_upsert)
    
    async def qa_attach_gemini_file(
        self,
        conversation_id: str,
        gemini_file_id: str
    ) -> None:
        """Attach Gemini file to conversation"""
        def _sync_attach():
            client = self._get_client()
            data = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "gemini_file_id": gemini_file_id,
                "added_at": datetime.utcnow().isoformat(),
            }
            client.table("qa_conversation_gemini_files").upsert(
                data,
                on_conflict="conversation_id,gemini_file_id"
            ).execute()
        
        await asyncio.to_thread(_sync_attach)
    
    # Artifacts
    
    async def qa_add_artifact(
        self,
        conversation_id: str,
        artifact_type: str,
        r2_key: str,
        file_name: str,
        mime_type: str,
        file_size: int,
        metadata: Optional[dict] = None,
    ) -> None:
        """Add artifact to conversation"""
        def _sync_add():
            client = self._get_client()
            data = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "artifact_type": artifact_type,
                "r2_key": r2_key,
                "file_name": file_name,
                "mime_type": mime_type,
                "file_size": file_size,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
            }
            client.table("qa_artifacts").insert(data).execute()
        
        await asyncio.to_thread(_sync_add)
