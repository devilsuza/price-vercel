import json
import os
import re
import time
from datetime import datetime
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "print_bridge_config.json")
POLL_SECONDS = 3
NORMAL_SIZE = (512, 244)
S3_SIZE = (812, 512)
DEFAULT_QR_URL = "https://price-gamek.vercel.app"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    portal_url = str(config.get("portal_url", "")).strip().rstrip("/")
    bridge_key = str(config.get("bridge_key", "")).strip()
    printer_name = str(config.get("printer_name", "EPSON TM-T88VII Receipt")).strip()
    if not portal_url.startswith(("http://", "https://")):
        raise ValueError("Set portal_url in print_bridge_config.json.")
    if not bridge_key:
        raise ValueError("Set bridge_key in print_bridge_config.json.")
    if not printer_name:
        raise ValueError("Set printer_name in print_bridge_config.json.")
    return portal_url, bridge_key, printer_name


def api_json(method, url, key, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urlrequest.Request(url, data=data, method=method)
    request.add_header("X-Print-Bridge-Key", key)
    request.add_header("X-Print-Bridge-Id", "printer1")
    request.add_header("Content-Type", "application/json")
    with urlrequest.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def font(size, bold=False):
    paths = (
        (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf")
        if bold
        else (r"C:\Windows\Fonts\arial.ttf",)
    )
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_font(draw, text, max_width, starting_size, minimum_size=14, bold=False):
    for size in range(starting_size, minimum_size - 1, -1):
        candidate = font(size, bold)
        if draw.textbbox((0, 0), text, font=candidate)[2] <= max_width:
            return candidate
    return font(minimum_size, bold)


def price_and_unit(job):
    raw_price = str(job.get("price", "")).strip().upper()
    unit = str(job.get("unit", "UN")).strip().upper() or "UN"
    match = re.match(r"^(.*?)\s*/\s*([A-Z]+)\s*$", raw_price)
    if match:
        raw_price, unit = match.group(1).strip(), match.group(2).strip()

    unit = {"PC": "UN", "PC/KGM": "UN", "KG": "KGM"}.get(unit, unit)
    normalized_price = raw_price.replace("KZ", "").replace("AOA", "").strip()
    numeric_price = normalized_price.replace(" ", "")
    if "," in numeric_price and "." in numeric_price:
        numeric_price = numeric_price.replace(",", "")
    elif "," in numeric_price:
        decimal_places = len(numeric_price.rsplit(",", 1)[1])
        numeric_price = (
            numeric_price.replace(",", ".")
            if decimal_places in (1, 2)
            else numeric_price.replace(",", "")
        )
    try:
        amount = float(numeric_price)
        price = f"{int(amount):,}" if amount.is_integer() else f"{amount:,.2f}"
    except ValueError:
        price = normalized_price
    return price, unit


def unit_label(unit):
    return "KZ/" + ("KG" if unit in {"KG", "KGM"} else unit)


def draw_product_name(draw, name, max_width, top, max_lines=2):
    words = " ".join(str(name or "ARTICLE").upper().split()).split()
    text_font = font(22, True)
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=text_font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    for index, line in enumerate(lines[:max_lines]):
        draw.text((12, top + index * 27), line, font=text_font, fill=0)


def make_qr_image(job, size):
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError(
            "QR formats need qrcode. Install it with: py -m pip install qrcode[pil]"
        ) from exc
    qr_value = str(
        job.get("qr_url")
        or job.get("app_url")
        or job.get("portal_url")
        or DEFAULT_QR_URL
    ).strip()
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=3,
        border=1,
    )
    qr.add_data(qr_value)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("1")
    return qr_image.resize((size, size), Image.Resampling.NEAREST)


def make_ticket(job, include_qr=False):
    image = Image.new("1", NORMAL_SIZE, 1)
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, NORMAL_SIZE[0] - 2, NORMAL_SIZE[1] - 2), outline=0, width=2)

    draw_product_name(draw, job.get("item_name"), 310 if include_qr else 480, 10)
    price, unit = price_and_unit(job)
    draw.text((12, 82), price, font=fit_font(draw, price, 300, 72, 42, True), fill=0)
    label = unit_label(unit)
    label_font = fit_font(draw, label, 185, 26, 17, True)
    draw.text((12, 166), label, font=label_font, fill=0)
    draw.text((12, 216), str(job.get("article_code") or ""), font=font(14), fill=0)
    draw.text(
        (370, 216),
        str(job.get("date") or datetime.now().strftime("%d/%m/%Y")),
        font=font(14),
        fill=0,
    )

    if include_qr:
        image.paste(make_qr_image(job, 70), (407, 7))
    return image


def make_s3_ticket(job, include_qr=False):
    image = Image.new("1", S3_SIZE, 1)
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, S3_SIZE[0] - 2, S3_SIZE[1] - 2), outline=0, width=2)
    product_width = S3_SIZE[0] - 154 if include_qr else S3_SIZE[0] - 36
    draw_product_name(draw, job.get("item_name"), product_width, 20, max_lines=3)
    if include_qr:
        image.paste(make_qr_image(job, 104), (S3_SIZE[0] - 126, 16))

    price, unit = price_and_unit(job)
    price_font = fit_font(draw, price, 500, 112, 62, True)
    price_width = draw.textbbox((0, 0), price, font=price_font)[2]
    draw.text((S3_SIZE[0] - price_width - 28, 265), price, font=price_font, fill=0)
    draw.text((S3_SIZE[0] - 220, 420), unit_label(unit), font=font(30, True), fill=0)
    draw.text((24, 458), str(job.get("article_code") or ""), font=font(18), fill=0)
    draw.text(
        (24, 420),
        str(job.get("date") or datetime.now().strftime("%d/%m/%Y")),
        font=font(18),
        fill=0,
    )
    return image.rotate(90, expand=True)


def print_image(image, printer_name, copies):
    try:
        import win32print
        import win32ui
        from PIL import ImageWin
    except ImportError as exc:
        raise RuntimeError(
            "Printing requires Windows and pywin32. Install with: py -m pip install pywin32"
        ) from exc

    printer = win32print.OpenPrinter(printer_name)
    dc = win32ui.CreateDC()
    try:
        dc.CreatePrinterDC(printer_name)
        for copy_number in range(copies):
            dc.StartDoc(f"Price label {copy_number + 1}")
            page_started = False
            try:
                dc.StartPage()
                page_started = True
                ImageWin.Dib(image).draw(dc.GetHandleOutput(), (0, 0, image.width, image.height))
            finally:
                if page_started:
                    dc.EndPage()
                dc.EndDoc()
    finally:
        dc.DeleteDC()
        win32print.ClosePrinter(printer)


def print_job(job, printer_name):
    mode = re.sub(
        r"[^A-Z0-9]", "", str(job.get("print_format", "THERMAL")).upper()
    )
    if mode in {"NORMALQRS3", "QRS3NORMAL", "S3NORMALQR"}:
        image = make_s3_ticket(job, include_qr=True)
    elif mode in {"NORMALQR", "QRNORMAL", "NORMALQRCODE", "QR"}:
        image = make_ticket(job, include_qr=True)
    elif mode in {"S3", "A6S3", "S3A6", "POSTCARDS3"}:
        image = make_s3_ticket(job)
    elif mode in {"THERMAL", "NORMAL"}:
        image = make_ticket(job)
    else:
        raise ValueError(f"Unsupported Epson print format: {mode}")

    copies = int(job.get("copies", 1))
    if copies < 1 or copies > 100:
        raise ValueError("Print copies must be between 1 and 100.")
    print_image(image, printer_name, copies)


def main():
    portal_url, bridge_key, printer_name = load_config()
    print(f"Epson print bridge connected to {portal_url}; printer: {printer_name}")
    while True:
        try:
            result = api_json(
                "GET", portal_url + "/api/print-jobs/next", bridge_key
            )
            job = result.get("job")
            if job:
                try:
                    print_job(job, printer_name)
                    api_json(
                        "POST",
                        portal_url + f"/api/print-jobs/{job['id']}/complete",
                        bridge_key,
                        {"success": True},
                    )
                    print(f"Printed job {job['id']}")
                except Exception as exc:
                    api_json(
                        "POST",
                        portal_url + f"/api/print-jobs/{job['id']}/complete",
                        bridge_key,
                        {"success": False, "error": str(exc)},
                    )
                    print(f"Print error for job {job['id']}: {exc}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            print(f"Portal connection error: {exc}")
        except Exception as exc:
            print(f"Bridge error: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
