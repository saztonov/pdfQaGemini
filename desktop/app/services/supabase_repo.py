"""Supabase repository - async data access without RLS"""
import asyncio
import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4
from supabase import create_client, Client
from app.models.schemas import TreeNode, NodeFile, Conversation, ConversationWithStats, Message

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

    async def fetch_roots(self, client_id: str = "default") -> list[TreeNode]:
        """Fetch root tree nodes (all projects, no client_id filter)"""
        logger.info("fetch_roots вызван")

        def _sync_fetch():
            logger.info("_sync_fetch: получение клиента...")
            client = self._get_client()
            logger.info("_sync_fetch: выполнение запроса к tree_nodes...")
            # Не фильтруем по client_id - показываем все корневые проекты
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

    async def fetch_children(self, parent_id: str) -> list[TreeNode]:
        """Fetch child nodes for given parent (no client_id filter)"""

        def _sync_fetch():
            client = self._get_client()
            # Не фильтруем по client_id - дочерние узлы уже привязаны к родителю
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
        self, client_id: str, root_ids: list[str], node_types: Optional[list[str]] = None
    ) -> list[TreeNode]:
        """Get descendant nodes via RPC, optionally filtered by node_type"""

        def _sync_fetch():
            client = self._get_client()
            params = {
                "p_client_id": client_id or "default",
                "p_root_ids": root_ids,
            }
            if node_types:
                params["p_node_types"] = node_types

            logger.info(f"RPC qa_get_descendants: params={params}")
            response = client.rpc("qa_get_descendants", params).execute()
            logger.info(f"RPC qa_get_descendants: returned {len(response.data)} rows")
            if response.data:
                logger.info(f"  First row: {response.data[0]}")
            # RPC doesn't return client_id, add it manually
            cid = client_id or "default"
            return [TreeNode(**{**row, "client_id": cid}) for row in response.data]

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_node_files(self, node_ids: list[str]) -> list[NodeFile]:
        """Fetch files for multiple nodes (chunked to 200)"""
        if not node_ids:
            return []

        def _sync_fetch(chunk: list[str]):
            client = self._get_client()
            response = client.table("node_files").select("*").in_("node_id", chunk).execute()
            return [NodeFile(**row) for row in response.data]

        # Chunk requests
        chunk_size = 200
        chunks = [node_ids[i : i + chunk_size] for i in range(0, len(node_ids), chunk_size)]

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

    async def fetch_document_bundle_files(self, document_node_id: str) -> dict:
        """Fetch bundle files for document node"""

        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("node_files").select("*").eq("node_id", document_node_id).execute()
            )
            files = [NodeFile(**row) for row in response.data]

            text_types = {"ocr_html", "result_json", "pdf"}
            return {
                "text_files": [f for f in files if f.file_type in text_types],
                "crop_files": [f for f in files if f.file_type == "crop"],
                "annotation_files": [f for f in files if f.file_type == "annotation"],
            }

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_all_crops_for_document(
        self, client_id: str, document_node_id: str
    ) -> list[NodeFile]:
        """Fetch all crop files for document including descendants"""
        # Get descendants via RPC
        descendants = await self.get_descendant_documents(
            client_id=client_id,
            root_ids=[document_node_id],
            node_types=None,
        )
        node_ids = [document_node_id] + [str(d.id) for d in descendants]

        # Fetch all files
        all_files = await self.fetch_node_files(node_ids)

        # Filter crops
        return [f for f in all_files if f.file_type == "crop"]

    # QA Conversations

    async def qa_create_conversation(
        self,
        client_id: str,
        title: str = "",
    ) -> Conversation:
        """Create new conversation"""

        def _sync_create():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "id": str(uuid4()),
                "client_id": client_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
            }
            response = client.table("qa_conversations").insert(data).execute()
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
                records, on_conflict="conversation_id,node_id"
            ).execute()

        await asyncio.to_thread(_sync_add)

    async def qa_add_message(
        self, conversation_id: str, role: str, content: str, meta: Optional[dict] = None
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
            response = client.table("qa_messages").insert(data).execute()
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
        token_count: Optional[int] = None,
        sha256: Optional[str] = None,
        source_node_file_id: Optional[str] = None,
        source_r2_key: Optional[str] = None,
        expires_at: Optional[str] = None,
        client_id: str = "default",
    ) -> dict:
        """Upsert Gemini File cache entry"""

        def _sync_upsert():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "client_id": client_id,
                "gemini_name": gemini_name,
                "gemini_uri": gemini_uri,
                "display_name": display_name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "token_count": token_count,
                "sha256": sha256,
                "source_node_file_id": source_node_file_id,
                "source_r2_key": source_r2_key,
                "expires_at": expires_at,
                "updated_at": now,
            }
            response = (
                client.table("qa_gemini_files").upsert(data, on_conflict="gemini_name").execute()
            )
            return response.data[0]

        return await asyncio.to_thread(_sync_upsert)

    async def qa_attach_gemini_file(self, conversation_id: str, gemini_file_id: str) -> None:
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
                data, on_conflict="conversation_id,gemini_file_id"
            ).execute()

        await asyncio.to_thread(_sync_attach)

    # Context files (для восстановления состояния контекста)

    async def qa_save_context_file(
        self,
        conversation_id: str,
        node_file_id: str,
        gemini_name: Optional[str] = None,
        gemini_uri: Optional[str] = None,
        status: str = "local",
    ) -> dict:
        """Сохранить файл контекста с его статусом"""

        def _sync_save():
            client = self._get_client()
            data = {
                "conversation_id": conversation_id,
                "node_file_id": node_file_id,
                "gemini_name": gemini_name,
                "gemini_uri": gemini_uri,
                "status": status,
                "uploaded_at": datetime.utcnow().isoformat() if status == "uploaded" else None,
            }
            response = (
                client.table("qa_conversation_context_files")
                .upsert(data, on_conflict="conversation_id,node_file_id")
                .execute()
            )
            return response.data[0]

        return await asyncio.to_thread(_sync_save)

    async def qa_load_context_files(self, conversation_id: str) -> list[dict]:
        """Загрузить все файлы контекста для диалога"""

        def _sync_load():
            client = self._get_client()
            response = (
                client.table("qa_conversation_context_files")
                .select("*, node_files(*)")
                .eq("conversation_id", conversation_id)
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_load)

    async def qa_delete_context_file(self, conversation_id: str, node_file_id: str) -> None:
        """Удалить файл из контекста"""

        def _sync_delete():
            client = self._get_client()
            client.table("qa_conversation_context_files").delete().eq(
                "conversation_id", conversation_id
            ).eq("node_file_id", node_file_id).execute()

        await asyncio.to_thread(_sync_delete)

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

    # Chat management

    async def qa_list_conversations(
        self, client_id: str = "default", limit: int = 50
    ) -> list[ConversationWithStats]:
        """List conversations with statistics (optimized with single query)"""

        def _sync_list():
            client = self._get_client()

            # Use RPC function for efficient aggregation
            # If RPC not available, fallback to basic query without stats
            try:
                # Try to use RPC function (if exists)
                response = client.rpc(
                    "qa_list_conversations_with_stats", {"p_client_id": client_id, "p_limit": limit}
                ).execute()

                conversations = []
                for row in response.data:
                    conv_data = {
                        **row,
                        "last_message_at": datetime.fromisoformat(row["last_message_at"])
                        if row.get("last_message_at")
                        else None,
                    }
                    conversations.append(ConversationWithStats(**conv_data))

                return conversations

            except Exception as e:
                logger.warning(f"RPC not available, using fallback query: {e}")

                # Fallback: just return conversations without detailed stats
                response = (
                    client.table("qa_conversations")
                    .select("*")
                    .eq("client_id", client_id)
                    .order("updated_at", desc=True)
                    .limit(limit)
                    .execute()
                )

                conversations = []
                for row in response.data:
                    # Basic conversation without stats
                    conv_data = {
                        **row,
                        "message_count": 0,
                        "file_count": 0,
                        "last_message_at": None,
                    }
                    conversations.append(ConversationWithStats(**conv_data))

                return conversations

        return await asyncio.to_thread(_sync_list)

    async def qa_get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("qa_conversations")
                .select("*")
                .eq("id", conversation_id)
                .limit(1)
                .execute()
            )
            if response.data:
                return Conversation(**response.data[0])
            return None

        return await asyncio.to_thread(_sync_get)

    async def qa_update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        model_default: Optional[str] = None,
        update_timestamp: bool = True,
    ) -> Conversation:
        """Update conversation"""

        def _sync_update():
            client = self._get_client()
            data = {}

            if update_timestamp:
                data["updated_at"] = datetime.utcnow().isoformat()

            if title is not None:
                data["title"] = title

            if model_default is not None:
                data["model_default"] = model_default

            # If no fields to update except timestamp, still update timestamp
            if not data and update_timestamp:
                data["updated_at"] = datetime.utcnow().isoformat()

            response = (
                client.table("qa_conversations").update(data).eq("id", conversation_id).execute()
            )
            return Conversation(**response.data[0])

        return await asyncio.to_thread(_sync_update)

    async def qa_delete_conversation(self, conversation_id: str) -> None:
        """Delete conversation and all related data"""

        def _sync_delete():
            client = self._get_client()

            # Delete messages
            client.table("qa_messages").delete().eq("conversation_id", conversation_id).execute()

            # Delete nodes links
            client.table("qa_conversation_nodes").delete().eq(
                "conversation_id", conversation_id
            ).execute()

            # Delete gemini files links
            client.table("qa_conversation_gemini_files").delete().eq(
                "conversation_id", conversation_id
            ).execute()

            # Delete context files
            client.table("qa_conversation_context_files").delete().eq(
                "conversation_id", conversation_id
            ).execute()

            # Delete artifacts
            client.table("qa_artifacts").delete().eq("conversation_id", conversation_id).execute()

            # Delete conversation
            client.table("qa_conversations").delete().eq("id", conversation_id).execute()

        await asyncio.to_thread(_sync_delete)

    async def qa_delete_all_conversations(self, client_id: str = "default") -> None:
        """Delete all conversations and related data for client"""

        def _sync_delete_all():
            client = self._get_client()

            # Get all conversation IDs for this client
            response = (
                client.table("qa_conversations").select("id").eq("client_id", client_id).execute()
            )

            conversation_ids = [row["id"] for row in response.data]

            if not conversation_ids:
                return

            logger.info(f"Удаление {len(conversation_ids)} чатов для client_id={client_id}")

            # Delete all related data for these conversations
            # Using .in_() for batch deletion

            # Delete messages
            client.table("qa_messages").delete().in_("conversation_id", conversation_ids).execute()

            # Delete nodes links
            client.table("qa_conversation_nodes").delete().in_(
                "conversation_id", conversation_ids
            ).execute()

            # Delete gemini files links
            client.table("qa_conversation_gemini_files").delete().in_(
                "conversation_id", conversation_ids
            ).execute()

            # Delete context files
            client.table("qa_conversation_context_files").delete().in_(
                "conversation_id", conversation_ids
            ).execute()

            # Delete artifacts
            client.table("qa_artifacts").delete().in_("conversation_id", conversation_ids).execute()

            # Delete all conversations
            client.table("qa_conversations").delete().eq("client_id", client_id).execute()

            logger.info("Удалены все чаты и связанные данные")

        await asyncio.to_thread(_sync_delete_all)

    async def qa_get_conversation_files(self, conversation_id: str) -> list[dict]:
        """Get all Gemini files attached to conversation"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("qa_conversation_gemini_files")
                .select("*, qa_gemini_files(*)")
                .eq("conversation_id", conversation_id)
                .execute()
            )

            files = []
            for row in response.data:
                gemini_file = row.get("qa_gemini_files")
                if gemini_file:
                    files.append(gemini_file)
            return files

        return await asyncio.to_thread(_sync_get)

    # User Prompts

    async def prompts_list(self, client_id: str = "default") -> list[dict]:
        """List all prompts for client"""

        def _sync_list():
            client = self._get_client()
            response = (
                client.table("user_prompts")
                .select("*")
                .eq("client_id", client_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_list)

    async def prompts_create(
        self,
        title: str,
        system_prompt: str,
        user_text: str,
        r2_key: Optional[str] = None,
        client_id: str = "default",
    ) -> dict:
        """Create new prompt"""

        def _sync_create():
            client = self._get_client()
            now = datetime.utcnow().isoformat()
            data = {
                "id": str(uuid4()),
                "client_id": client_id,
                "title": title,
                "system_prompt": system_prompt,
                "user_text": user_text,
                "r2_key": r2_key,
                "created_at": now,
                "updated_at": now,
            }
            response = client.table("user_prompts").insert(data).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_create)

    async def prompts_update(
        self,
        prompt_id: str,
        title: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_text: Optional[str] = None,
        r2_key: Optional[str] = None,
    ) -> dict:
        """Update prompt"""

        def _sync_update():
            client = self._get_client()
            data = {"updated_at": datetime.utcnow().isoformat()}

            if title is not None:
                data["title"] = title
            if system_prompt is not None:
                data["system_prompt"] = system_prompt
            if user_text is not None:
                data["user_text"] = user_text
            if r2_key is not None:
                data["r2_key"] = r2_key

            response = client.table("user_prompts").update(data).eq("id", prompt_id).execute()
            return response.data[0]

        return await asyncio.to_thread(_sync_update)

    async def prompts_delete(self, prompt_id: str) -> None:
        """Delete prompt"""

        def _sync_delete():
            client = self._get_client()
            client.table("user_prompts").delete().eq("id", prompt_id).execute()

        await asyncio.to_thread(_sync_delete)

    async def prompts_get(self, prompt_id: str) -> Optional[dict]:
        """Get single prompt by ID"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("user_prompts").select("*").eq("id", prompt_id).limit(1).execute()
            )
            if response.data:
                return response.data[0]
            return None

        return await asyncio.to_thread(_sync_get)

    async def fetch_tree_stats(self) -> dict:
        """Fetch tree statistics: projects, documents, folders with PDFs, pdf/md files"""

        def _sync_fetch():
            client = self._get_client()

            # Count node types and get parent_ids for documents
            nodes_response = client.table("tree_nodes").select("node_type,parent_id").execute()
            nodes = nodes_response.data

            project_count = sum(1 for n in nodes if n["node_type"] == "project")
            document_count = sum(1 for n in nodes if n["node_type"] == "document")

            # Count unique parent folders that contain documents (folders with PDFs)
            document_parent_ids = set(
                n["parent_id"] for n in nodes
                if n["node_type"] == "document" and n["parent_id"]
            )
            folders_with_pdf_count = len(document_parent_ids)

            # Count file types
            files_response = client.table("node_files").select("file_type").execute()
            files = files_response.data

            pdf_count = sum(1 for f in files if f["file_type"] == "pdf")
            md_count = sum(1 for f in files if f["file_type"] == "result_md")

            return {
                "projects": project_count,
                "documents": document_count,
                "folders_with_pdf": folders_with_pdf_count,
                "pdf_files": pdf_count,
                "md_files": md_count,
            }

        return await asyncio.to_thread(_sync_fetch)
