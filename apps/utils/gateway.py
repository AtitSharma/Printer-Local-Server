import httpx

from config import settings
from utils import BadRequest


class POSGateway:
    """Client for the fvr-pos (Food Verse POS) API."""

    def __init__(self):
        self.base_url = settings.pos_url.rstrip("/")
        self.token = settings.pos_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.base_url or not self.token:
            raise BadRequest(
                message="POS_URL or POS_TOKEN not set in .env",
                exception_type="pos.missing_config",
            )

        url = f"{self.base_url}/pos{path}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url, headers=self._headers(), params=params
                )
        except httpx.HTTPError as e:
            raise BadRequest(
                message=f"Could not reach POS at {self.base_url}: {e}",
                exception_type="pos.unreachable",
            )

        if resp.status_code != 200:
            raise BadRequest(
                message=f"POS request failed: HTTP {resp.status_code} - {resp.text}",
                exception_type="pos.request_failed",
            )

        data = resp.json()

        if not data.get("success"):
            raise BadRequest(
                message=f"POS request failed: {data.get('message')}",
                exception_type="pos.request_failed",
            )

        return data.get("data")

    async def fetch_invoice(self, invoice_id: str) -> dict:
        """Fetch a single invoice from the POS."""
        return await self._get(f"/invoices/{invoice_id}")

    async def get_printer_of_facility(self, facility_id: str) -> list[dict]:
        """List printers configured for a facility in the POS."""
        return await self._get(f"/printer/get-printer-facility/{facility_id}")

    async def get_printer(self, printer_id: str) -> dict:
        """Fetch a single printer config from the POS."""
        return await self._get(f"/printer/get-printer/{printer_id}")
