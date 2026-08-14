import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(root_path="/pos")


def ok(data, message="OK"):
    return JSONResponse({"success": True, "message": message, "data": data})


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    return ok(
        {
            "id": invoice_id,
            "invoice_number": "FV-2024-0001",
            "status": "PAID",
            "facility_id": "bb9d7ed-8b6d-4313-9da9-fd4ef5522c91",
            "order_id": "order-123",
            "gross_amount": 1000.0,
            "discount_amount": 50.0,
            "taxable_amount": 950.0,
            "service_charge_amount": 95.0,
            "order_discount_amount": 0.0,
            "vat_rate": 13.0,
            "vat_amount": 135.85,
            "total_amount": 1180.85,
            "currency": "NPR",
            "issuer_pan": "123456789",
            "buyer_name": "John Doe",
            "buyer_pan": "987654321",
            "is_cbms_synced": True,
            "cbms_qr_data": "aGVsbG8gd29ybGQ=",
            "issued_at": "2024-01-15T10:30:00",
            "total_print_generated": 0,
            "business_detail": {
                "company_name": "Test Restaurant",
                "pan_vat_number": "123456789",
                "address": "Kathmandu, Nepal",
                "phone": "9800000000",
                "email": "info@test.com",
                "footer_detail": [{"message": "Thank you for visiting!"}],
            },
            "payment": {"method": "CASH", "amount": 1180.85, "created_at": "2024-01-15T10:31:00"},
            "line_items": [
                {
                    "menu_item_name": "Momo",
                    "quantity": 2,
                    "unit_price": 300.0,
                    "line_total": 600.0,
                    "applied_discounts": [{"discount_name": "Happy Hour", "discount_amount": 30.0}],
                },
                {"menu_item_name": "Pizza", "quantity": 1, "unit_price": 400.0, "line_total": 400.0, "applied_discounts": []},
            ],
        }
    )


@app.get("/printer/get-printer-facility/{facility_id}")
def get_printers(facility_id: str):
    return ok(
        [
            {
                "id": "printer-1",
                "name": "Kitchen Thermal",
                "facility_id": facility_id,
                "connection_type": "NETWORK",
                "printer_type": "RECEIPT",
                "device_type": "THERMAL",
                "ip_address": "192.168.123.100",
                "port": "9100",
                "is_default": True,
            },
            {
                "id": "printer-2",
                "name": "USB Receipt",
                "facility_id": facility_id,
                "connection_type": "USB",
                "printer_type": "RECEIPT",
                "device_type": "THERMAL",
                "vendor_id": "0x1fc9",
                "product_id": "0x2016",
                "is_default": False,
            },
        ]
    )


@app.get("/printer/get-printer/{printer_id}")
def get_printer(printer_id: str):
    return ok(
        {
            "id": printer_id,
            "name": "Kitchen Thermal",
            "facility_id": "bb9d7ed-8b6d-4313-9da9-fd4ef5522c91",
            "connection_type": "NETWORK",
            "printer_type": "RECEIPT",
            "device_type": "THERMAL",
            "ip_address": "192.168.123.100",
            "port": "9100",
            "is_default": True,
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8003)
