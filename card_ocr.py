import base64
import io
import json
import re
from pathlib import Path

import anthropic
from PIL import Image

_PROMPT_SINGLE = """Extract graded trading card data from this image. Return ONLY a JSON array, one object per card visible:
[{"grader":"PSA/BGS/SGC/etc","grade":"exact grade shown","cert_number":"cert/serial number","year":"year on card","player_name":"player or subject name","set_name":"set or manufacturer","card_number":"card number","variation":"parallel/variation if noted or null","sport_category":"Baseball/Football/Pokemon/etc"}]
Use null for any field not visible. No explanation, no markdown."""

_PROMPT_MULTI = """This image contains multiple graded trading card slabs. Carefully examine each card individually and extract its data.

For EVERY card visible, read the label text closely — grader name, grade number, cert/serial number, year, player name, set name, card number, and any variation or parallel noted.

Return ONLY a JSON array with one object per card:
[{"grader":"PSA/BGS/SGC/etc","grade":"exact grade shown","cert_number":"cert/serial number","year":"year on card","player_name":"player or subject name","set_name":"set or manufacturer","card_number":"card number","variation":"parallel/variation if noted or null","sport_category":"Baseball/Football/Pokemon/etc"}]

Be precise — do not guess or mix up fields between cards. Use null for anything genuinely not visible. No explanation, no markdown."""


def _resize_image(image_path: str, max_dim: int, quality: int) -> tuple[bytes, str]:
    img = Image.open(image_path)
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue(), "image/jpeg"


def extract_card_data(image_path: str, api_key: str, multi: bool = False) -> list[dict]:
    client = anthropic.Anthropic(api_key=api_key)

    if multi:
        image_bytes, media_type = _resize_image(image_path, max_dim=1600, quality=92)
        max_tokens = 1024
        prompt = _PROMPT_MULTI
    else:
        image_bytes, media_type = _resize_image(image_path, max_dim=1000, quality=85)
        max_tokens = 400
        prompt = _PROMPT_SINGLE

    model = "claude-sonnet-4-6"

    b64_image = base64.standard_b64encode(image_bytes).decode("utf-8")

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": media_type, "data": b64_image}},
                {"type": "text", "text": prompt}
            ]
        }])

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    return result if isinstance(result, list) else [result]
