import asyncio
import base64
import http.client
import platform
import socket
import struct
import time
from datetime import datetime
from typing import Any

from num2words import num2words

from config import settings

_DOTS_PER_MM = 8
_LABEL_WIDTH_MM = 80
_PRINTABLE_DOTS = _LABEL_WIDTH_MM * _DOTS_PER_MM
_MARGIN = 20
_CONTENT_DOTS = _PRINTABLE_DOTS - 2 * _MARGIN

_BODY_FONT = "2"
_BOLD_FONT = "3"
_BODY_CHAR_W = 16
_BOLD_CHAR_W = 24
_BODY_LINE_H = 32
_BOLD_LINE_H = 48

W = 30
SEP = "-" * 40


# ---------------------------------------------------------------------------
# Receipt layout
# ---------------------------------------------------------------------------


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    result = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip() if current else w
        if len(test) <= width:
            current = test
        else:
            if current:
                result.append(current)
            current = w
    if current:
        result.append(current)
    return result or [""]


def _fmt_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _amount_in_words(total: float) -> str:
    total = round(total, 2)
    rupees = int(total)
    paisa = round((total - rupees) * 100)

    rupees_words = num2words(rupees, lang="en")

    if paisa > 0:
        paisa_words = num2words(paisa, lang="en")
        return f"Rs: {str(rupees_words).capitalize()} and {paisa_words} paisa"

    return f"Rs: {rupees_words}"


def build_receipt(payload: dict) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []

    def c(text: str, bold: bool = False):
        lines.append((text, "center_bold" if bold else "center"))

    def l(text: str, bold: bool = False):
        lines.append((text, "left_bold" if bold else "left"))

    business = payload.get("business_detail") or {}
    company = business.get("company_name") or payload.get("company_name")
    if company:
        c(company)
    addr = business.get("address") or payload.get("address")
    if addr:
        c(addr)
    issuer_pan = business.get("pan_vat_number") or payload.get("issuer_pan", "")
    if issuer_pan:
        c(f"VAT No: {issuer_pan}")
    if payload.get("bill_type") == "TAX":
        c("TAX INVOICE")

    copy_number = payload.get("copy_number")
    if copy_number:
        c(f"COPY OF ORIGINAL - {copy_number}")

    invoice_number = payload.get("invoice_number") or "N/A"
    l(f"Bill NO : {invoice_number}")

    if payload.get("transaction_date"):
        l(f"Transaction Date : {payload['transaction_date']}")
    if payload.get("transaction_time"):
        l(f"Transaction Time : {payload['transaction_time']}")

    issued = _fmt_dt(payload.get("issued_at"))
    if issued:
        l(f"Invoice Date     : {issued.strftime('%d-%b-%Y')}")
        l(f"Invoice Time     : {issued.strftime('%I:%M %p')}")
    elif payload.get("issued_at"):
        for wl in _wrap(f"Invoice Date     : {payload['issued_at']}", W):
            l(wl)

    if payload.get("buyer_name"):
        name_lines = _wrap(payload["buyer_name"], 19)
        l(f"Name     : {name_lines[0]}")
        for extra in name_lines[1:]:
            l("           " + extra)
    if payload.get("buyer_pan"):
        l(f"TPIN     : {payload['buyer_pan']}")
    if addr:
        l(f"Address  : {addr}")
    phone = business.get("phone") or payload.get("phone")
    if phone:
        l(f"Tel No   : {phone}")

    pm = payload.get("payment_method")
    payment_mode = {"CASH": "Cash", "QR": "QR", "CARD": "Card"}.get(
        pm, pm or "Cash"
    )
    l(f"Payment Mode : {payment_mode}")

    voided = _fmt_dt(payload.get("voided_at"))
    if voided:
        l(f"VOIDED: {voided.strftime('%d-%b-%Y %I:%M %p')}")
    elif payload.get("voided_at"):
        l(f"VOIDED: {payload['voided_at']}")
    if payload.get("void_reason"):
        for wl in _wrap(f"Reason: {payload['void_reason']}", W):
            l(wl)

    l(SEP)
    l(f"{'Sn':<3}{'Items':<13}{'Qty':>5}{'Rate':>8}{'Amount':>11}")
    l(SEP)

    total_qty = 0
    items = payload.get("line_items") or payload.get("items") or []
    for idx, item in enumerate(items, start=1):
        name = item.get("menu_item_name") or item.get("name") or ""
        qty = item.get("quantity", 0) or 0
        total_qty += qty
        unit_price = item.get("unit_price", 0) or 0
        subtotal = qty * unit_price
        desc = name[:13]
        l(f"{idx:<3}{desc:<13}{qty:>5}{unit_price:>8.0f}{subtotal:>11.2f}")
        l("   HSC:")
        for d in item.get("applied_discounts", []):
            dname = d.get("discount_name") or d.get("name") or "Discount"
            damount = d.get("discount_amount") or d.get("amount") or 0
            l(f"{'   '}{dname[:14]:<14}{-damount:>23.2f}")

    for od in payload.get("order_discounts", []):
        label = od.get("reason") or "Order Discount"
        od_amount = od.get("amount", 0) or 0
        l(f"{'   '}{label[:14]:<14}{-od_amount:>23.2f}")

    l(SEP)

    gross = payload.get("gross_amount", 0) or 0
    discount = (payload.get("discount_amount", 0) or 0) + (
        payload.get("order_discount_amount", 0) or 0
    )
    taxable = payload.get("taxable_amount", 0) or 0
    vat_rate = payload.get("vat_rate", 0) or 0
    vat_amount = payload.get("vat_amount", 0) or 0
    total = payload.get("total_amount", 0) or 0
    non_taxable = max(0, gross - taxable - discount)

    l(f"{'             Gross Amount :':<18}{gross:>12.2f}")
    if discount > 0:
        l(f"{'             Discount     :':<18}{-discount:>12.2f}")
    l(f"{'             Taxable      :':<18}{taxable:>12.2f}")
    sc = payload.get("service_charge_amount", 0) or 0
    if sc > 0:
        l(f"{'             Service Charge:':<18}{sc:>12.2f}")
    l(f"{'             NonTaxable   :':<18}{non_taxable:>12.2f}")
    l(f"{'             VAT ' + str(int(vat_rate)) + '%      :':<18}{vat_amount:>12.2f}")
    l(f"{'             Net Amount   :':<18}{total:>12.2f}")

    l(SEP)

    l(f"{'Total Quantity :':<18}{total_qty:>12}")

    for wl in _wrap(_amount_in_words(total), W):
        l(wl)

    l(SEP)

    footer_msgs = list(payload.get("footer_messages", []))
    if not footer_msgs:
        footer_msgs = list(business.get("footer_detail", []))
    if not footer_msgs:
        footer_msgs = list(payload.get("footer_detail", []))
    for msg in footer_msgs:
        if isinstance(msg, dict):
            msg = msg.get("message") or msg.get("text") or ""
        for wl in _wrap(msg, W):
            l(wl)

    l(SEP)

    return lines


# ---------------------------------------------------------------------------
# TSPL label generation (USB + IP thermal printers)
# ---------------------------------------------------------------------------


def _escape_tspl(text: str) -> str:
    text = text.encode("ascii", "replace").decode("ascii")
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _qr_text(value) -> str:
    try:
        decoded = base64.b64decode(value, validate=True)
        text = decoded.decode("utf-8", "replace")
        if text.isprintable() and text:
            return text
    except Exception:
        pass
    return value


def _build_tspl(payload: dict) -> bytes:
    lines = build_receipt(payload)

    cmds = []
    y = _MARGIN

    for text, style in lines:
        if style in ("center", "left"):
            font, char_w, line_h = _BODY_FONT, _BODY_CHAR_W, _BODY_LINE_H
        else:
            font, char_w, line_h = _BOLD_FONT, _BOLD_CHAR_W, _BOLD_LINE_H

        line_dots = len(text) * char_w

        if style in ("left", "left_bold"):
            x = _MARGIN
        else:
            x = _MARGIN + max(0, (_CONTENT_DOTS - line_dots) // 2)

        cmds.append(
            f'TEXT {x},{y},"{font}",0,1,1,"{_escape_tspl(text)}"'
        )
        y += line_h

    qr = payload.get("cbms_qr_data")
    if qr:
        qr_size = 140
        qr_x = (_PRINTABLE_DOTS - qr_size) // 2
        qr_y = y + _MARGIN
        cmds.append(
            f'QRCODE {qr_x},{qr_y},H,4,A,0,"{_escape_tspl(_qr_text(qr))}"'
        )
        y = qr_y + qr_size + _MARGIN

    y += _MARGIN
    height_mm = (y + _DOTS_PER_MM - 1) // _DOTS_PER_MM

    header = (
        f"SIZE {_LABEL_WIDTH_MM} mm,{height_mm} mm\r\n"
        "GAP 0 mm,0\r\n"
        "CLS\r\n"
    )

    data = bytearray(header.encode())
    for cmd in cmds:
        data += (cmd + "\r\n").encode()
    data += b"PRINT 1\r\n"

    return bytes(data)


# ---------------------------------------------------------------------------
# USB printer (pyusb / libusb)
# ---------------------------------------------------------------------------


def _get_usb_backend():
    import usb.backend.libusb1
    import libusb_package

    backend = usb.backend.libusb1.get_backend(
        find_library=libusb_package.find_library
    )
    if backend:
        return backend

    if platform.system() == "Darwin":
        paths = [
            "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib",
            "/usr/local/opt/libusb/lib/libusb-1.0.dylib",
        ]
        for path in paths:
            backend = usb.backend.libusb1.get_backend(
                find_library=lambda _: path
            )
            if backend:
                return backend

    return None


class USBPrinter:
    def __init__(self):
        self.device = None
        self.endpoint = None

    def discover(self):
        import usb.core
        import usb.util

        backend = _get_usb_backend()
        if backend is None:
            return []

        printers = []
        for dev in usb.core.find(find_all=True, backend=backend):
            try:
                manufacturer = usb.util.get_string(dev, dev.iManufacturer)
                product = usb.util.get_string(dev, dev.iProduct)
                printers.append(
                    {
                        "vid": hex(dev.idVendor),
                        "pid": hex(dev.idProduct),
                        "manufacturer": manufacturer,
                        "product": product,
                    }
                )
            except Exception:
                pass
        return printers

    def connect(self, vid, pid):
        import usb.core
        import usb.util

        backend = _get_usb_backend()
        if backend is None:
            raise Exception(
                "libusb backend not found. Install libusb "
                "(see mac.sh / ubuntu.sh / windows.ps1)."
            )

        vid = int(vid, 16)
        pid = int(pid, 16)

        self.device = usb.core.find(
            idVendor=vid, idProduct=pid, backend=backend
        )
        if self.device is None:
            raise Exception("Printer not found")

        if platform.system() == "Linux" and self.device.is_kernel_driver_active(0):
            self.device.detach_kernel_driver(0)

        try:
            self.device.set_configuration()
        except usb.core.USBError:
            pass

        cfg = self.device.get_active_configuration()
        intf = cfg[(0, 0)]

        self.endpoint = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_OUT
            ),
        )
        if self.endpoint is None:
            raise Exception("No OUT endpoint found")

    def print_raw(self, data: bytes):
        if self.endpoint is None:
            raise Exception("Printer not connected")
        self.endpoint.write(data)

    def print_invoice(self, payload: dict):
        self.print_raw(_build_tspl(payload))


# ---------------------------------------------------------------------------
# IP / network printer (TCP 9100)
# ---------------------------------------------------------------------------


class IPPrinter:
    def __init__(self):
        self.sock = None
        self.ip = None
        self.port = 9100

    def connect(self, ip, port=9100):
        self.ip = ip
        self.port = int(port)
        self.sock = socket.create_connection((self.ip, self.port), timeout=10)

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def print_raw(self, data: bytes):
        if self.sock is None:
            raise Exception("Printer not connected")
        self.sock.sendall(data)

    def print_tspl(self, text):
        cmd = (
            "SIZE 60 mm,40 mm\r\n"
            "GAP 0 mm,0\r\n"
            "CLS\r\n"
            f'TEXT 30,30,"3",0,1,1,"{text}"\r\n'
            "PRINT 1\r\n"
        )
        self.print_raw(cmd.encode())

    def print_invoice(self, payload: dict):
        data = _build_tspl(payload)
        for chunk in (data[i : i + 512] for i in range(0, len(data), 512)):
            self.print_raw(chunk)
            time.sleep(0.02)


# ---------------------------------------------------------------------------
# Normal (A4 / POS) printer via IPP
# ---------------------------------------------------------------------------


def _encode_ipp(tag: int, name: str, value: str | bytes) -> bytes:
    name_bytes = name.encode("utf-8")
    value_bytes = value.encode("utf-8") if isinstance(value, str) else value
    return (
        struct.pack("!B", tag)
        + struct.pack("!H", len(name_bytes))
        + name_bytes
        + struct.pack("!H", len(value_bytes))
        + value_bytes
    )


def _render_invoice_image(payload: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    width = 800
    line_height = 22
    margin = 40

    estimated_lines = (
        20 + len(payload.get("items", [])) * 2 + len(payload.get("footer_messages", []))
    )
    height = max(400, margin * 2 + estimated_lines * line_height)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16
        )
        font_bold = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 16
        )
    except OSError:
        font = ImageFont.load_default()
        font_bold = font

    y = margin

    def draw_centered(text: str, bold: bool = False):
        nonlocal y
        f = font_bold if bold else font
        bbox = draw.textbbox((0, 0), text, font=f)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) / 2, y), text, fill="black", font=f)
        y += line_height

    def draw_left(text: str, bold: bool = False):
        nonlocal y
        f = font_bold if bold else font
        draw.text((margin, y), text, fill="black", font=f)
        y += line_height

    def draw_line():
        nonlocal y
        draw.line([(margin, y), (width - margin, y)], fill="black", width=1)
        y += line_height // 2

    company_name = payload.get("company_name")
    if company_name:
        draw_centered(company_name, bold=True)
        if payload.get("address"):
            draw_centered(payload["address"])
        if payload.get("phone"):
            draw_centered(f"Phone: {payload['phone']}")
        if payload.get("email"):
            draw_centered(payload["email"])

    issuer_pan = payload.get("issuer_pan", "")
    if issuer_pan:
        draw_centered(f"Issuer PAN: {issuer_pan}")

    draw_centered(f"Invoice: {payload.get('invoice_number') or 'N/A'}")
    draw_centered(f"Status: {payload.get('status') or 'ISSUED'}")
    if payload.get("order_id"):
        draw_centered(f"Order: {payload['order_id']}")
    if payload.get("issued_at"):
        draw_centered(payload["issued_at"])
    if payload.get("issued_time"):
        draw_centered(payload["issued_time"])

    if payload.get("bill_type") == "TAX":
        draw_centered("TAX INVOICE", bold=True)

    copy_number = payload.get("copy_number")
    if copy_number:
        draw_centered(f"COPY OF ORIGINAL - {copy_number}", bold=True)

    if payload.get("voided_at"):
        draw_centered(f"VOIDED: {payload['voided_at']}")
    if payload.get("void_reason"):
        draw_centered(f"Reason: {payload['void_reason']}")

    draw_line()

    if payload.get("buyer_name") or payload.get("buyer_pan"):
        if payload.get("buyer_name"):
            draw_left(f"Customer: {payload['buyer_name']}")
        if payload.get("buyer_pan"):
            draw_left(f"PAN/VAT: {payload['buyer_pan']}")
        draw_line()

    draw_left(f"{'Desc':<28}{'Qty':>5}{'Rate':>10}{'Amt':>10}", bold=True)
    for item in payload.get("items", []):
        desc = item["name"][:28]
        draw_left(
            f"{desc:<28}{item['quantity']:>5}"
            f"{item['unit_price']:>10.2f}{item['line_total']:>10.2f}"
        )
        for d in item.get("discounts", []):
            draw_left(f"  ({d['name']}: -{d['amount']:.2f})")
    y += line_height // 2

    draw_left(f"{'Subtotal':.<42}{payload.get('gross_amount', 0):>10.2f}")
    if payload.get("discount_amount", 0) > 0:
        draw_left(f"{'Discount':.<42}{-payload['discount_amount']:>10.2f}")
    if payload.get("order_discount_amount", 0) > 0:
        draw_left(f"{'Order Disc':.<42}{-payload['order_discount_amount']:>10.2f}")
    draw_left(f"{'Taxable':.<42}{payload.get('taxable_amount', 0):>10.2f}")
    if payload.get("service_charge_amount", 0) > 0:
        draw_left(f"{'Service Charge':.<42}{payload['service_charge_amount']:>10.2f}")
    if payload.get("vat_amount", 0) > 0:
        vat_label = f"VAT @ {int(payload['vat_rate'])}%"
        draw_left(f"{vat_label:<42}{payload['vat_amount']:>10.2f}")
    draw_left(f"{'TOTAL':.<42}{payload.get('total_amount', 0):>10.2f}", bold=True)
    draw_left(f"{'Currency':.<42}{payload.get('currency', 'NPR')}")

    draw_line()

    for msg in payload.get("footer_messages", []):
        draw_centered(msg)

    img = img.crop((0, 0, width, y + margin))
    import io

    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def _send_ipp(ip: str, data: bytes, port: int = 631) -> bool:
    conn = http.client.HTTPConnection(ip, port, timeout=30)
    try:
        conn.request(
            "POST",
            "/ipp/print",
            body=data,
            headers={"Content-Type": "application/ipp"},
        )
        resp = conn.getresponse()
        body = resp.read()
        if len(body) >= 8:
            _, _, status = struct.unpack_from("!BBH", body)
            return status == 0
        return False
    except Exception:
        return False
    finally:
        conn.close()


class NormalPrinter:
    def __init__(self, ip: str, port: int = 631):
        self.ip = ip
        self.port = int(port)

    def print_invoice(self, payload: dict) -> dict:
        try:
            image_data = _render_invoice_image(payload)
            printer_uri = f"ipp://{self.ip}/ipp/print"
            msg = struct.pack("!BB", 2, 0)
            msg += struct.pack("!H", 0x0002)  # Print-Job
            msg += struct.pack("!I", 1)
            msg += struct.pack("!B", 0x01)  # operation-attributes
            msg += _encode_ipp(0x47, "attributes-charset", "utf-8")
            msg += _encode_ipp(0x48, "attributes-natural-language", "en")
            msg += _encode_ipp(0x45, "printer-uri", printer_uri)
            msg += _encode_ipp(0x49, "document-format", "image/jpeg")
            msg += struct.pack("!B", 0x03)  # end-of-attributes
            msg += image_data
            success = _send_ipp(self.ip, msg, port=self.port)
            if success:
                return {
                    "success": True,
                    "message": "Invoice printed successfully on normal printer",
                }
            return {"success": False, "message": "IPP print job failed"}
        except Exception as e:
            return {"success": False, "message": f"Normal print error: {e}"}


# ---------------------------------------------------------------------------
# Print service
# ---------------------------------------------------------------------------


class PrintService:
    def __init__(self, printer: dict):
        self.printer = printer

    async def print_invoice(self, payload: dict) -> dict:
        return await asyncio.to_thread(self._print_invoice_sync, payload)

    def _print_invoice_sync(self, payload: dict) -> dict:
        printer = self.printer
        connection_type = printer.get("connection_type")

        try:
            if connection_type == "NETWORK":
                ip = printer.get("ip_address")
                if not ip:
                    return {"success": False, "message": "ip_address is required"}
                port = int(printer.get("port") or 9100)

                if port == 631:
                    printer_obj = NormalPrinter(ip=ip, port=port)
                    return printer_obj.print_invoice(payload)

                ip_printer = IPPrinter()
                ip_printer.connect(ip, port)
                try:
                    ip_printer.print_invoice(payload)
                finally:
                    ip_printer.close()
                return {"success": True, "message": "Invoice printed successfully"}

            if connection_type == "USB":
                usb_printer = USBPrinter()
                vid = printer.get("vendor_id") or settings.printer_vid
                pid = printer.get("product_id") or settings.printer_pid
                usb_printer.connect(vid, pid)
                usb_printer.print_invoice(payload)
                return {"success": True, "message": "Invoice printed successfully"}

            return {"success": False, "message": "Unsupported printer configuration"}
        except Exception as e:
            return {"success": False, "message": f"Print error: {e}"}
