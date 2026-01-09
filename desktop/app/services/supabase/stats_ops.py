"""Statistics operations for Supabase repository"""

import asyncio


class StatsOpsMixin:
    """Mixin for statistics operations"""

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
                n["parent_id"] for n in nodes if n["node_type"] == "document" and n["parent_id"]
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
