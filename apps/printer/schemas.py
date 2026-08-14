from pydantic import BaseModel, Field

from apps.printer.enums import (
    PrinterConnectionType,
    PrinterDeviceType,
    PrinterType,
)


class PrinterResponseSchema(BaseModel):
    id: str
    name: str
    facility_id: str
    model: str | None = None
    connection_type: PrinterConnectionType
    printer_type: PrinterType
    device_type: PrinterDeviceType
    ip_address: str | None = None
    port: str | None = None
    vendor_id: str | None = None
    product_id: str | None = None
    is_default: bool = False

    model_config = {"from_attributes": True}


class PrinterPrintSchema(BaseModel):
    invoice_id: str
    printer_id: str | None = None
    facility_id: str | None = None


class PrinterDiscoverSchema(BaseModel):
    vid: str
    pid: str
    manufacturer: str | None = None
    product: str | None = None
