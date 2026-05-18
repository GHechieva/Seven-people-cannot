import io
import re
import logging
import aiohttp
import base64
import config

logger = logging.getLogger(__name__)


async def extract_from_receipt(photo_bytes: bytes) -> dict:
    """
    Attempt OCR on receipt image.
    Returns dict with keys: amount (float|None), merchant (str|None), raw_text (str)
    """
    raw_text = ""

    if config.OCR_SPACE_API_KEY:
        raw_text = await _ocr_space(photo_bytes)
    else:
        # Try pytesseract locally
        raw_text = await _pytesseract(photo_bytes)

    amount = _extract_amount(raw_text)
    merchant = _extract_merchant(raw_text)

    return {"amount": amount, "merchant": merchant, "raw_text": raw_text}


async def _ocr_space(photo_bytes: bytes) -> str:
    b64 = base64.b64encode(photo_bytes).decode("utf-8")
    payload = {
        "base64Image": f"data:image/jpeg;base64,{b64}",
        "language": "eng",
        "isTable": True,
        "OCREngine": 2,
    }
    headers = {"apikey": config.OCR_SPACE_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.ocr.space/parse/image",
                data=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()
                if data.get("OCRExitCode") == 1:
                    results = data.get("ParsedResults", [])
                    if results:
                        return results[0].get("ParsedText", "")
    except Exception as e:
        logger.warning(f"OCR.space failed: {e}")
    return ""


async def _pytesseract(photo_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(photo_bytes))
        return pytesseract.image_to_string(image)
    except ImportError:
        logger.warning("pytesseract not installed")
    except Exception as e:
        logger.warning(f"pytesseract failed: {e}")
    return ""


def _extract_amount(text: str) -> float | None:
    """
    Heuristic: find the largest monetary amount in the text (likely the total).
    Matches patterns like: 24.50, €24,50, 24.50 EUR, TOTAL 24.50
    """
    patterns = [
        r"(?:total|sum|amount|due|pay)[:\s]*[€$£¥]?\s*(\d+[.,]\d{2})",
        r"[€$£¥]\s*(\d+[.,]\d{2})",
        r"(\d+[.,]\d{2})\s*(?:EUR|USD|GBP|CHF)",
        r"(\d+[.,]\d{2})",
    ]
    candidates = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                val = float(m.replace(",", "."))
                candidates.append(val)
            except ValueError:
                pass

    if not candidates:
        return None
    # Return the largest candidate (most likely the total)
    return max(candidates)


def _extract_merchant(text: str) -> str | None:
    """
    Heuristic: first non-empty line of the receipt is usually the merchant name.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        # Skip very short lines or lines that are just numbers
        for line in lines[:5]:
            if len(line) > 3 and not re.match(r"^[\d\s\-\+\*\/\.]+$", line):
                return line[:64]
    return None
