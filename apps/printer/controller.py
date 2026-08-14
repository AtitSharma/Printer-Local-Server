from fastapi import APIRouter, Depends

from apps.printer.schemas import (
    PrinterDiscoverSchema,
    PrinterPrintSchema,
    PrinterResponseSchema,
)
from apps.printer.services import PrinterService
from utils import response_ok

printer_router = APIRouter(prefix="/printer", tags=["Printer"])


@printer_router.get(
    "/list/{facility_id}",
    response_model=dict,
    summary="PRINT-01",
    description="List printers configured for a facility (fetched from POS).",
)
async def list_printers(
    facility_id: str,
    service: PrinterService = Depends(PrinterService),
):
    printers = await service.list_printers(facility_id)
    return response_ok(
        data=printers,
        message="Printer Fetched Successfully",
    )


@printer_router.get(
    "/discover",
    response_model=dict,
    summary="PRINT-02",
    description="Discover USB printers connected to this machine.",
)
async def discover_printers(
    service: PrinterService = Depends(PrinterService),
):
    printers = await service.discover_printers()
    return response_ok(
        data=printers,
        message="Printer Discovered Successfully",
    )


@printer_router.get(
    "/{printer_id}",
    response_model=dict,
    summary="PRINT-03",
    description="Fetch a single printer config from POS.",
)
async def get_printer(
    printer_id: str,
    service: PrinterService = Depends(PrinterService),
):
    printer = await service.get_printer(printer_id)
    return response_ok(
        data=printer,
        message="Printer Fetched Successfully",
    )


@printer_router.post(
    "/print-invoice",
    response_model=dict,
    summary="PRINT-04",
    description="Fetch invoice from POS and trigger the printer.",
)
async def print_invoice(
    data: PrinterPrintSchema,
    service: PrinterService = Depends(PrinterService),
):
    result = await service.print_invoice(
        invoice_id=data.invoice_id,
        printer_id=data.printer_id,
        facility_id=data.facility_id,
    )
    return response_ok(
        data=result,
        message=result.get("message", "Printed"),
    )