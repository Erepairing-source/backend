"""
OEM warranty sync service
"""
from typing import Optional
import httpx

from app.models.integration import Integration, IntegrationStatus


class OEMWarrantyService:
    async def fetch_warranty(self, integration: Integration, serial_number: str):
        if not integration or not integration.api_endpoint:
            return {"error": "OEM warranty integration is not configured"}

        headers = integration.config.get("headers") if integration.config else {}
        api_key = integration.config.get("api_key") if integration.config else None
        if api_key:
            headers = {**headers, "Authorization": f"Bearer {api_key}"}

        params = {}
        query_param = integration.config.get("serial_param", "serial") if integration.config else "serial"
        params[query_param] = serial_number

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(integration.api_endpoint, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        mapping = integration.config.get("field_mapping", {}) if integration.config else {}
        def get_field(name, fallback=None):
            key = mapping.get(name, name)
            return data.get(key, fallback)

        return {
            "warranty_type": get_field("warranty_type", "standard"),
            "start_date": get_field("start_date"),
            "end_date": get_field("end_date"),
            "covered_parts": get_field("covered_parts", []),
            "covered_services": get_field("covered_services", []),
            "warranty_number": get_field("warranty_number"),
        }
