# -*- coding: utf-8 -*-
"""
3x4 (3:4) rasmiy rasm tayyorlash moduli.

Foydalanuvchi yuborgan rasmdan:
  * fonni almashtiradi (oq / ko'k / kulrang),
  * kiyimni almashtiradi (kostyum / ko'ylak / oq xalat),
  * yuzni saqlab qoladi,
  * natijani 3:4 nisbatga keltirib, 35x45 mm (300 dpi) o'lchamda beradi.

Model: router.ai orqali gemini-2.5-flash-image (OpenAI-mos API).
Kalit: keys.txt dagi OPENAI_API_KEY.
"""

import base64
import io
import json
import re
import urllib.error
import urllib.request

import config

DEFAULT_MODEL = "gemini-2.5-flash-image"
TIMEOUT = 150

BACKGROUNDS = {
    "oq": "plain pure white background (#FFFFFF)",
    "kok": "plain light blue background (#4A90D9)",
    "kulrang": "plain light grey background (#E7E7E7)",
}

BG_RGB = {
    "oq": (255, 255, 255),
    "kok": (74, 144, 217),
    "kulrang": (231, 231, 231),
}

DRESSES = {
    "kostyum": "a formal dark navy business suit with a white shirt and a dark tie",
    "koylak": "a clean white classic collared shirt",
    "xalat": "a white medical coat over a light shirt",
}


def _model():
    return getattr(config, "PHOTO_MODEL", "") or DEFAULT_MODEL


def _key():
    """Rasm kaliti: PHOTO_API_KEY bo'lsa o'sha, aks holda OPENAI_API_KEY."""
    return (getattr(config, "PHOTO_API_KEY", "") or
            getattr(config, "OPENAI_API_KEY", "") or "")


def _base_url():
    base = (getattr(config, "PHOTO_BASE_URL", "") or
            getattr(config, "OPENAI_BASE_URL", "") or "")
    return base.rstrip("/")


def available():
    """Rasm har holatda tayyorlanadi: AI kaliti bo'lsa sifatli, bo'lmasa oddiy kesish."""
    return True


def _prompt(bg_key, dress_key, has_ref=False):
    bg = BACKGROUNDS.get(bg_key, BACKGROUNDS["oq"])
    dress = DRESSES.get(dress_key, DRESSES["kostyum"])
    if has_ref:
        cloth = (
            "Use the clothing from the SECOND image exactly as provided - keep its colour, "
            "cut, collar and fabric; fit it naturally to this person's body with realistic "
            "folds, lighting and shadows. Do not copy the background or the face of the "
            "second image. "
        )
    else:
        cloth = (
            f"Replace the current clothing with {dress}; fit it naturally with realistic "
            "fabric texture, accurate folds, lighting and shadows. "
        )
    return (
        "Edit this photo into an official 3x4 passport / ID photo. "
        "The FIRST image is the person. "
        "Keep the person's face, facial features, skin tone, hairstyle, pose and camera angle "
        "exactly the same - do not change identity, body proportions or expression. "
        + cloth +
        f"Replace the background with {bg} - completely clean, no shadows, gradients, objects "
        "or patterns. "
        "Head centered with appropriate space above the head, shoulders visible, straight "
        "posture, looking at the camera. "
        "Photorealistic, ultra sharp focus, natural skin texture, studio lighting, print-ready, "
        "no text, no watermark, no artifacts, vertical 3:4 framing."
    )


def _extract_image(data):
    """Javobdan rasm baytlarini ajratib oladi (data URL yoki base64)."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("AI javobini o'qib bo'lmadi")

    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and str(part.get("type", "")).endswith("image_url"):
                url = (part.get("image_url") or {}).get("url", "")
                if "base64," in url:
                    return base64.b64decode(url.split("base64,", 1)[1])

    if isinstance(content, str):
        match = re.search(r"data:image/\w+;base64,([A-Za-z0-9+/=\s]+)", content)
        if match:
            return base64.b64decode(re.sub(r"\s+", "", match.group(1)))

    raise RuntimeError("AI rasm qaytarmadi")


def _crop34(img, out_w=354, out_h=472):
    """PIL rasmni 3:4 nisbatga kesib, berilgan o'lchamga keltiradi."""
    from PIL import Image

    w, h = img.size
    target = 3 / 4
    if w / h > target:
        new_w = int(h * target)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target)
        top = max(0, int((h - new_h) * 0.35))
        img = img.crop((0, top, w, top + new_h))
    return img.resize((out_w, out_h), Image.LANCZOS)


def _to_3x4(raw):
    """Rasmni 3:4 nisbatga keltiradi va 413x531 (35x45 mm, 300 dpi) qiladi."""
    from PIL import Image

    img = _crop34(Image.open(io.BytesIO(raw)).convert("RGB"), 413, 531)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=95, optimize=True)
    return out.getvalue()


def make_sheet(raw_photo, dpi=300, cols=4, rows=2,
               paper_w_cm=15.0, paper_h_cm=10.0,
               photo_w_cm=3.0, photo_h_cm=4.0, border_px=8):
    """
    10x15 sm (300 dpi) varaqqa 8 ta bir xil 3x4 rasmni terib beradi.
    Har bir rasm atrofida kesish uchun yupqa qora hoshiya qo'yiladi.
    Qaytaradi: JPEG baytlari (chop etishga tayyor).
    """
    from PIL import Image, ImageDraw

    pw = int(round(photo_w_cm * dpi / 2.54))
    ph = int(round(photo_h_cm * dpi / 2.54))
    W = int(round(paper_w_cm * dpi / 2.54))
    H = int(round(paper_h_cm * dpi / 2.54))

    src = Image.open(io.BytesIO(raw_photo)).convert("RGB")
    one = _crop34(src, pw - 2 * border_px, ph - 2 * border_px)

    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    gap_x = (W - cols * pw) // (cols + 1)
    gap_y = (H - rows * ph) // (rows + 1)
    if gap_x < 2:
        gap_x = 2
    if gap_y < 2:
        gap_y = 2

    for r in range(rows):
        for c in range(cols):
            x = gap_x + c * (pw + gap_x)
            y = gap_y + r * (ph + gap_y)
            draw.rectangle([x, y, x + pw - 1, y + ph - 1], outline=(0, 0, 0), width=border_px)
            sheet.paste(one, (x + border_px, y + border_px))

    out = io.BytesIO()
    sheet.save(out, "JPEG", quality=95, optimize=True, dpi=(dpi, dpi))
    return out.getvalue()


def _content(b64, bg, dress, ref=None):
    """Xabarlar mazmuni: 1-rasm - portret, 2-rasm (bo'lsa) - kiyim namunasi."""
    parts = [{"type": "text", "text": _prompt(bg, dress, bool(ref))},
             {"type": "image_url",
              "image_url": {"url": "data:image/jpeg;base64," + b64}}]
    if ref:
        parts.append({"type": "image_url",
                      "image_url": {"url": "data:image/jpeg;base64," + ref}})
    return parts


def _make_ai(raw_photo, bg="oq", dress="kostyum", ref=None):
    """
    Xom rasm baytlaridan 3x4 tayyor rasm qaytaradi (JPEG baytlari).
    Xato bo'lsa RuntimeError ko'taradi (matni foydalanuvchiga ko'rsatiladi).
    """
    if not _key():
        raise RuntimeError("ai_off")

    b64 = base64.b64encode(raw_photo).decode("ascii")
    payload = {
        "model": _model(),
        "messages": [
            {
                "role": "user",
                "content": _content(b64, bg, dress, ref),
            }
        ],
        "modalities": ["image", "text"],
    }

    req = urllib.request.Request(
        _base_url() + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + _key(),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200]
        if exc.code == 402 or "Insufficient balance" in detail or "\u4f59\u989d" in detail:
            raise RuntimeError("Hisob balansi tugagan - rasm uchun balans kerak") from exc
        raise RuntimeError(f"AI xatosi {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("AI bilan aloqa yo'q (internet yoki vaqt tugadi)") from exc

    return _to_3x4(_extract_image(data))


def _near(px, target, tol):
    return all(abs(int(px[i]) - target[i]) <= tol for i in range(3))


_REMBG_SESSION = None


def _rembg_session():
    """rembg modelini bir marta yuklaydi (u2netp - kichik va tez)."""
    global _REMBG_SESSION
    if _REMBG_SESSION is not None:
        return _REMBG_SESSION
    from rembg import new_session

    try:
        _REMBG_SESSION = new_session("u2netp")
    except Exception:  # noqa: BLE001
        _REMBG_SESSION = new_session("u2net")
    return _REMBG_SESSION


def _cut_person(img):
    """Odamni fondan ajratadi (RGBA). rembg bo'lmasa None."""
    from PIL import Image
    from rembg import remove

    buf = io.BytesIO()
    img.save(buf, "PNG")
    cut = Image.open(io.BytesIO(remove(buf.getvalue(), session=_rembg_session()))).convert("RGBA")
    if cut.size != img.size:
        cut = cut.resize(img.size, Image.LANCZOS)
    return cut


def _remove_bg_plain(img, target, thresh=26):
    """
    Oddiy zaxira: faqat BIR XIL rangli fon bo'lsa chetlardan to'ldiradi.
    Fon murakkab bo'lsa tegm(z)maydi (rasm buzilmasin).
    Qaytaradi: (img, almashtirildi?)
    """
    from statistics import median

    w, h = img.size
    step = max(8, min(w, h) // 40)
    edge = []
    for x in range(0, w, step):
        edge.append(img.getpixel((x, 2)))
        edge.append(img.getpixel((x, h - 3)))
    for y in range(0, h, step):
        edge.append(img.getpixel((2, y)))
        edge.append(img.getpixel((w - 3, y)))

    med = tuple(int(median([p[i] for p in edge])) for i in range(3))
    spread = max(max(p[i] for p in edge) - min(p[i] for p in edge) for i in range(3))
    if spread > 40:
        return img, False

    from PIL import ImageDraw

    seeds = [(x, 2) for x in range(0, w, step)] + [(x, h - 3) for x in range(0, w, step)]
    seeds += [(2, y) for y in range(0, h, step)] + [(w - 3, y) for y in range(0, h, step)]
    changed = False
    for pt in seeds:
        try:
            if not _near(img.getpixel(pt), med, 18):
                continue
            if _near(img.getpixel(pt), target, 12):
                changed = True
                continue
            ImageDraw.floodfill(img, pt, target, thresh=thresh)
            changed = True
        except Exception:  # noqa: BLE001
            continue
    return img, changed


def _simple(raw_photo, bg="oq"):
    """
    AI siz zaxira: odamni fondan ajratib, tanlangan rangli fonga qo'yadi,
    so'ng 3:4 (413x531) qilib kesadi. Qaytaradi: (baytlar, fon_almashtirildi?)
    """
    from PIL import Image

    img = Image.open(io.BytesIO(raw_photo)).convert("RGB")
    if max(img.size) > 1600:
        img.thumbnail((1600, 1600), Image.LANCZOS)

    target = BG_RGB.get(bg, BG_RGB["oq"])
    done = False
    try:
        cut = _cut_person(img)
        canvas = Image.new("RGB", img.size, target)
        canvas.paste(cut, (0, 0), cut)
        img = canvas
        done = True
    except Exception:  # noqa: BLE001
        img, done = _remove_bg_plain(img, target)

    img = _crop34(img, 413, 531)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=95, optimize=True)
    return out.getvalue(), done


def make_ex(raw_photo, bg="oq", dress="kostyum", ref=None):
    """
    (jpeg_baytlar, izoh) qaytaradi.
    izoh: "" - AI bilan tayyorlandi, aks holda foydalanuvchiga ko'rsatiladigan qisqa matn.
    """
    try:
        return _make_ai(raw_photo, bg, dress, ref), ""
    except RuntimeError as exc:
        low = str(exc).lower()
        soft = ("ai_off", "402", "insufficient", "balance", "quota", "balans")
        if any(k in low for k in soft):
            out, bg_done = _simple(raw_photo, bg)
            if bg_done:
                note = "Fon o'chirildi va almashtirildi."
            else:
                note = "Fon o'chirilmadi - rasm o'z foni bilan qoldi."
            note += " Kiyim o'zgartirilmadi (AI balansi yo'q)."
            if ref:
                note += " Kiyim namunasi ishlatilmadi."
            return out, note
        raise


def make(raw_photo, bg="oq", dress="kostyum", ref=None):
    """Eski chaqiruvlar uchun: faqat JPEG baytlari."""
    return make_ex(raw_photo, bg, dress, ref)[0]
