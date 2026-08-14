from datetime import datetime

from fastapi import Depends, Request

from apps.printer.utils import PrintService
from apps.utils.gateway import POSGateway
from config import settings
from utils import BadRequest, NotFound


class PrinterService:
    def __init__(
        self,
        request: Request,
        gateway: POSGateway = Depends(POSGateway),
    ):
        self.request = request
        self.gateway = gateway

    async def list_printers(self, facility_id: str) -> list[dict]:
        return await self.gateway.get_printer_of_facility(facility_id)

    async def get_printer(self, printer_id: str) -> dict:
        return await self.gateway.get_printer(printer_id)

    async def discover_printers(self) -> list[dict]:
        from apps.printer.utils import USBPrinter

        return USBPrinter().discover()

    async def print_invoice(
        self,
        invoice_id: str,
        printer_id: str | None = None,
        facility_id: str | None = None,
    ) -> dict:
        if not invoice_id:
            raise BadRequest(message="invoice_id is required")

        invoice = await self.gateway.fetch_invoice(invoice_id)
        if not invoice:
            raise NotFound(message="Invoice not found")

        printer = await self._resolve_printer(printer_id, facility_id, invoice)
        payload = await self._build_payload(invoice)

        copy_number = (invoice.get("total_print_generated") or 0) + 1
        payload["copy_number"] = copy_number if copy_number > 1 else None

        print_service = PrintService(printer)
        result = await print_service.print_invoice(payload)

        if result.get("success"):
            try:
                await self.gateway.increment_print_count(invoice_id)
                result["print_count_incremented"] = True
            except Exception as e:
                result["print_count_incremented"] = False
                result["print_count_error"] = str(e)

        result["invoice_id"] = str(invoice.get("id"))
        result["invoice_number"] = invoice.get("invoice_number")
        result["printer"] = printer.get("name") or printer.get("ip_address")

        return result

    async def _resolve_printer(
        self,
        printer_id: str | None,
        facility_id: str | None,
        invoice: dict,
    ) -> dict:
        if printer_id:
            return await self.gateway.get_printer(printer_id)

        fac_id = facility_id or invoice.get("facility_id")
        if fac_id:
            printers = await self.gateway.get_printer_of_facility(fac_id)
            if printers:
                default = next(
                    (p for p in printers if p.get("is_default")),
                    printers[0],
                )
                return default

        return self._default_printer()

    def _default_printer(self) -> dict:
        if settings.printer_ip:
            return {
                "name": "Default Network Printer",
                "connection_type": "NETWORK",
                "device_type": "THERMAL",
                "ip_address": settings.printer_ip,
                "port": str(settings.printer_port),
            }
        return {
            "name": "Default USB Printer",
            "connection_type": "USB",
            "device_type": "THERMAL",
            "vendor_id": settings.printer_vid,
            "product_id": settings.printer_pid,
        }

    async def _build_payload(self, invoice: dict) -> dict:
        business = invoice.get("business_detail") or {}
        payment = invoice.get("payment") or {}

        issued_at = None
        issued_time = None
        if invoice.get("issued_at"):
            issued_at = invoice["issued_at"]
            issued_time = None

        transaction_date = None
        transaction_time = None
        payment_method = None
        if payment:
            payment_method = payment.get("method")
            created_at = payment.get("created_at")
            if created_at:
                try:
                    dt = datetime.fromisoformat(str(created_at))
                    transaction_date = dt.strftime("%d/%m/%Y")
                    transaction_time = dt.strftime("%I:%M %p")
                except ValueError:
                    pass

        items = []
        for item in invoice.get("line_items", []):
            discounts = []
            for d in item.get("applied_discounts", []):
                discounts.append(
                    {
                        "name": d.get("discount_name"),
                        "amount": d.get("discount_amount"),
                    }
                )
            items.append(
                {
                    "name": item.get("menu_item_name"),
                    "quantity": item.get("quantity"),
                    "unit_price": item.get("unit_price"),
                    "line_total": item.get("line_total"),
                    "discounts": discounts,
                }
            )

        footer_messages = []
        for fb in business.get("footer_detail", []) or []:
            if isinstance(fb, dict):
                footer_messages.append(fb.get("message"))
            else:
                footer_messages.append(str(fb))

        order_discounts = []
        for od in invoice.get("order_discounts", []) or []:
            order_discounts.append(
                {
                    "reason": od.get("reason"),
                    "amount": od.get("amount") or invoice.get("order_discount_amount", 0),
                }
            )

        return {
            "issuer_pan": business.get("pan_vat_number") or invoice.get("issuer_pan", ""),
            "company_name": business.get("company_name") or invoice.get("company_name"),
            "address": business.get("address") or invoice.get("address"),
            "phone": business.get("phone") or invoice.get("phone"),
            "email": business.get("email") or invoice.get("email"),
            "business_detail": business,
            "invoice_number": invoice.get("invoice_number"),
            "status": invoice.get("status"),
            "facility_id": str(invoice.get("facility_id")) if invoice.get("facility_id") else None,
            "order_id": str(invoice.get("order_id")) if invoice.get("order_id") else None,
            "issued_at": issued_at,
            "issued_time": issued_time,
            "transaction_date": transaction_date,
            "transaction_time": transaction_time,
            "payment_method": payment_method,
            "bill_type": invoice.get("bill_type"),
            "buyer_name": invoice.get("buyer_name"),
            "buyer_pan": invoice.get("buyer_pan"),
            "items": items,
            "line_items": invoice.get("line_items", []),
            "gross_amount": invoice.get("gross_amount"),
            "discount_amount": invoice.get("discount_amount"),
            "order_discount_amount": invoice.get("order_discount_amount"),
            "order_discounts": order_discounts,
            "taxable_amount": invoice.get("taxable_amount"),
            "service_charge_amount": invoice.get("service_charge_amount"),
            "vat_rate": invoice.get("vat_rate"),
            "vat_amount": invoice.get("vat_amount"),
            "total_amount": invoice.get("total_amount"),
            "currency": invoice.get("currency") or "NPR",
            "cbms_qr_data": invoice.get("cbms_qr_data"),
            "footer_messages": footer_messages,
            "voided_at": invoice.get("voided_at"),
            "void_reason": invoice.get("void_reason"),
        }
