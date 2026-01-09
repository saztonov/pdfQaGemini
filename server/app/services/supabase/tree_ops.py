"""Tree operations for Supabase repository (server)"""

import asyncio
from typing import Optional


class TreeOpsMixin:
    """Mixin for tree operations"""

    async def fetch_roots(self, client_id: str = "default") -> list[dict]:
        """Fetch root tree nodes"""

        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("tree_nodes")
                .select("*")
                .is_("parent_id", "null")
                .order("sort_order")
                .order("name")
                .execute()
            )
            return response.data

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_children(self, parent_id: str) -> list[dict]:
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
            return response.data

        return await asyncio.to_thread(_sync_fetch)

    async def get_descendant_documents(
        self, client_id: str, root_ids: list[str], node_types: Optional[list[str]] = None
    ) -> list[dict]:
        """Get descendant nodes via RPC"""

        def _sync_fetch():
            client = self._get_client()
            params = {
                "p_client_id": client_id or "default",
                "p_root_ids": root_ids,
            }
            if node_types:
                params["p_node_types"] = node_types

            response = client.rpc("qa_get_descendants", params).execute()
            cid = client_id or "default"
            return [{**row, "client_id": cid} for row in response.data]

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_node_files(self, node_ids: list[str]) -> list[dict]:
        """Fetch files for multiple nodes (chunked)"""
        if not node_ids:
            return []

        def _sync_fetch(chunk: list[str]):
            client = self._get_client()
            response = client.table("node_files").select("*").in_("node_id", chunk).execute()
            return response.data

        chunk_size = 200
        chunks = [node_ids[i : i + chunk_size] for i in range(0, len(node_ids), chunk_size)]

        tasks = [asyncio.to_thread(_sync_fetch, chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks)

        all_files = []
        for result in results:
            all_files.extend(result)
        return all_files

    async def fetch_node_files_single(self, node_id: str) -> list[dict]:
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
            return response.data

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_document_bundle_files(self, document_node_id: str) -> dict:
        """Fetch bundle files for document node"""

        def _sync_fetch():
            client = self._get_client()
            response = (
                client.table("node_files").select("*").eq("node_id", document_node_id).execute()
            )
            files = response.data

            text_types = {"ocr_html", "result_json", "pdf"}
            return {
                "text_files": [f for f in files if f.get("file_type") in text_types],
                "crop_files": [f for f in files if f.get("file_type") == "crop"],
                "annotation_files": [f for f in files if f.get("file_type") == "annotation"],
            }

        return await asyncio.to_thread(_sync_fetch)
