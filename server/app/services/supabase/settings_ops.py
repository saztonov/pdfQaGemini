"""Settings operations for Supabase repository (server)"""

import asyncio
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class SettingsOpsMixin:
    """Mixin for app settings operations"""

    async def get_all_settings(self) -> dict[str, Any]:
        """Get all settings as a dictionary with type conversion"""

        def _sync_get_all():
            client = self._get_client()
            response = client.table("qa_app_settings").select("*").execute()

            settings = {}
            for row in response.data:
                key = row["key"]
                value = row["value"]
                value_type = row.get("value_type", "string")

                # Type conversion
                if value is None:
                    settings[key] = None
                elif value_type == "int":
                    settings[key] = int(value) if value else 0
                elif value_type == "bool":
                    settings[key] = value.lower() in ("true", "1", "yes")
                elif value_type == "json":
                    import json

                    settings[key] = json.loads(value) if value else {}
                else:
                    settings[key] = value

            return settings

        return await asyncio.to_thread(_sync_get_all)

    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a single setting value with type conversion"""

        def _sync_get():
            client = self._get_client()
            response = (
                client.table("qa_app_settings")
                .select("*")
                .eq("key", key)
                .limit(1)
                .execute()
            )

            if not response.data:
                return default

            row = response.data[0]
            value = row["value"]
            value_type = row.get("value_type", "string")

            if value is None:
                return default

            # Type conversion
            if value_type == "int":
                return int(value) if value else default
            elif value_type == "bool":
                return value.lower() in ("true", "1", "yes")
            elif value_type == "json":
                import json

                return json.loads(value) if value else default
            else:
                return value

        return await asyncio.to_thread(_sync_get)

    async def set_setting(self, key: str, value: Any) -> bool:
        """Set a setting value (converts to string for storage)"""

        def _sync_set():
            client = self._get_client()

            # Convert value to string
            if isinstance(value, bool):
                str_value = "true" if value else "false"
            elif isinstance(value, (dict, list)):
                import json

                str_value = json.dumps(value)
            else:
                str_value = str(value) if value is not None else None

            response = (
                client.table("qa_app_settings")
                .update({"value": str_value, "updated_at": "now()"})
                .eq("key", key)
                .execute()
            )

            return len(response.data) > 0

        return await asyncio.to_thread(_sync_set)

    async def set_settings_batch(self, settings: dict[str, Any]) -> int:
        """Set multiple settings at once. Returns count of updated settings."""

        def _sync_set_batch():
            client = self._get_client()
            updated = 0

            for key, value in settings.items():
                # Convert value to string
                if isinstance(value, bool):
                    str_value = "true" if value else "false"
                elif isinstance(value, (dict, list)):
                    import json

                    str_value = json.dumps(value)
                else:
                    str_value = str(value) if value is not None else None

                response = (
                    client.table("qa_app_settings")
                    .update({"value": str_value, "updated_at": "now()"})
                    .eq("key", key)
                    .execute()
                )

                if response.data:
                    updated += 1

            return updated

        return await asyncio.to_thread(_sync_set_batch)

    async def get_settings_for_client(self) -> dict[str, Any]:
        """Get settings that should be sent to client (excludes sensitive keys)"""
        all_settings = await self.get_all_settings()

        # Keys that are safe to send to client
        client_safe_keys = {
            "default_model",
            "max_history_pairs",
            "r2_public_url",
        }

        return {k: v for k, v in all_settings.items() if k in client_safe_keys}

    async def get_settings_for_worker(self) -> dict[str, Any]:
        """Get settings needed by the worker"""
        all_settings = await self.get_all_settings()

        worker_keys = {
            "gemini_api_key",
            "default_model",
            "max_history_pairs",
            "worker_max_jobs",
            "worker_job_timeout",
            "worker_max_retries",
        }

        return {k: v for k, v in all_settings.items() if k in worker_keys}
