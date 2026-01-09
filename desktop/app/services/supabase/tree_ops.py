"""Tree operations for Supabase repository"""

import asyncio
import logging
from typing import Optional
from app.models.schemas import TreeNode, NodeFile

logger = logging.getLogger(__name__)


class TreeOpsMixin:
    """Mixin for tree operations"""

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
