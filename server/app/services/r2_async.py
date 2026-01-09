"""Cloudflare R2 async client for server"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for shared imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from shared.services.r2_client_base import R2AsyncClientBase


class R2AsyncClient(R2AsyncClientBase):
    """Server async client for Cloudflare R2 storage"""

    async def save_artifact(
        self,
        conversation_id: str,
        artifact_type: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Save artifact to R2. Returns R2 key."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        r2_key = f"chats/{conversation_id}/artifacts/{artifact_type}_{timestamp}_{file_name}"
        await self.upload_bytes(r2_key, data, content_type=content_type)
        return r2_key
