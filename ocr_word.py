# -*- coding: utf-8 -*-
"""
Rasm -> Word (.docx) — rasmning KO'RINISHINI saqlab o'giradi.

- rapidocr (oflayn) matn va harflar koordinatalarini beradi
- so'z oraliqlari rasmdagi bo'sh ustunlar bo'yicha aniqlanadi
- matn markazga/o'ngga/chetga tekislangan holda, o'lchami va
  satr orasi bilan Word faylga yoziladi (A4, Times New Roman)
"""

import io
import os
import re
import statistics
import tempfile
import uuid


def _available():
    try:
        import importlib.util

        return importlib.util.find_spec("rapidocr_onnxruntime") is not None
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# 1. OCR va so'zlarni tiklash
# ---------------------------------------------------------------------------
def _fix_chars(text):
    text = text.replace("\u00b0", "'").replace("\u2019", "'")
    text = re.sub(r"(?<=[A-Za-z\u0400-\u04FF])'(?=[A-Za-z\u0400-\u04FF])", "'", text)
    text = re.sub(r"(?<=[a-z\u0430-\u044f\u0451'])(?=[0-9])", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _word_bounds(px, W, H, x0, x1, y0, y1):
    """Satr ichidagi bo'sh ustunlar -> so'z chegaralari."""
    top = int(max(0, y0)) + 1
    bot = int(min(H - 1, y1)) - 1
    left = int(max(0, x0))
    right = int(min(W - 1, x1))
    if right - left < 8 or bot - top < 4:
        return []
    blanks = []
    for x in range(left, right + 1):
        ink = 0
        for y in range(top, bot, 2):
            if px[x, y] < 150:
                ink = 1
                break
        blanks.append(0 if ink else 1)
    runs, s = [], None
    for i, b in enumerate(blanks):
        if b and s is None:
            s = i
        elif not b and s is not None:
            runs.append((s, i - 1))
            s = None
    if s is not None:
        runs.append((s, len(blanks) - 1))
    need = max(4.0, 0.30 * (y1 - y0))
    bounds = []
    for a, b in runs:
        if a == 0 or b == len(blanks) - 1:
            continue
        if (b - a + 1) >= need:
            bounds.append(left + (a + b) / 2.0)
    return bounds


def _read_lines(img):
    from rapidocr_onnxruntime import RapidOCR

    tmp = os.path.join(tempfile.gettempdir(), "_ocr_word_%s.png" % uuid.uuid4().hex[:10])
    try:
        img.save(tmp)
    except Exception:  # noqa: BLE001
        return []
    engine = RapidOCR()
    try:
        res, _ = engine(tmp, return_word_box=True)
    except Exception:  # noqa: BLE001
        res, _ = engine(tmp)

    gray = img.convert("L")
    W, H = gray.size
    px = gray.load()

    items = []
    for row in res or []:
        poly, text = row[0], str(row[1])
        boxes = row[3] if len(row) > 3 else None
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        text = _fix_chars(text)
        if boxes and len(boxes) == len(str(row[1]).strip()) and " " not in str(row[1]):
            if len(text) > 8 and text.upper() == text or len(text) > 14:
                bounds = _word_bounds(px, W, H, x0, x1, y0, y1)
                if bounds:
                    chars, rebuilt, prev = [], "", None
                    for ch, bx in zip(str(row[1]).strip(), boxes):
                        cx = (bx[0][0] + bx[1][0]) / 2.0
                        seg = sum(1 for b in bounds if cx > b)
                        if prev is not None and seg != prev:
                            rebuilt += " "
                        rebuilt += ch
                        prev = seg
                    text = _fix_chars(rebuilt)
        if not text.strip():
            continue
        items.append(dict(x0=x0, x1=x1, y0=y0, y1=y1, text=text))
    items.sort(key=lambda d: (d["y0"] + d["y1"]) / 2)
    return items


# ---------------------------------------------------------------------------
# 2. Word fayl
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Qo'shimcha: o'tkazib yuborilgan satrlar va tagchiziqlar
# ---------------------------------------------------------------------------
def _bands(gray):
    """Gorizontal proyeksiya bo'yicha satr polosalari."""
    W, H = gray.size
    px = gray.load()
    bands, s = [], None
    for y in range(H):
        ink = 0
        for x in range(0, W, 2):
            if px[x, y] < 165:
                ink += 1
                if ink >= 3:
                    break
        if ink >= 3 and s is None:
            s = y
        elif ink < 3 and s is not None:
            if y - s >= 6:
                bands.append([s, y - 1])
            s = None
    if s is not None and H - s >= 6:
        bands.append([s, H - 1])
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] <= 2:
            merged[-1][1] = b[1]
        else:
            merged.append(b)
    return merged


def _rules(gray):
    """Uzun gorizontal chiziqlar (______) -> [(y, x0, x1)]."""
    W, H = gray.size
    px = gray.load()
    rows = {}
    for y in range(H):
        best = cur = 0
        start = bstart = 0
        for x in range(W):
            if px[x, y] < 165:
                if cur == 0:
                    start = x
                cur += 1
                if cur > best:
                    best, bstart = cur, start
            else:
                cur = 0
        if best >= max(24, int(0.09 * W)):
            rows[y] = (bstart, bstart + best)
    out, ys = [], sorted(rows)
    i = 0
    while i < len(ys):
        j, x0, x1 = i, rows[ys[i]][0], rows[ys[i]][1]
        while j + 1 < len(ys) and ys[j + 1] - ys[j] <= 2:
            j += 1
            a, b = rows[ys[j]]
            x0, x1 = min(x0, a), max(x1, b)
        out.append({"y": (ys[i] + ys[j]) / 2.0, "x0": x0, "x1": x1})
        i = j + 1
    return out


def _fill_missing(img, gray, items):
    """Proyeksiyada bor, lekin o'qilmagan satrlarni alohida o'qiydi."""
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR

    W, H = gray.size
    px = gray.load()
    engine = None
    extra = []
    for y0, y1 in _bands(gray):
        if any(not (it["y1"] < y0 - 4 or it["y0"] > y1 + 4) for it in items):
            continue
        xs = [x for x in range(W) if any(px[x, y] < 165 for y in range(y0, y1 + 1, 2))]
        if not xs:
            continue
        x0, x1 = min(xs), max(xs)
        crop = img.crop((max(0, x0 - 30), max(0, y0 - 12), min(W, x1 + 30), min(H, y1 + 12)))
        p = os.path.join(tempfile.gettempdir(), "_ocr_band_%s.png" % uuid.uuid4().hex[:10])
        if engine is None:
            engine = RapidOCR()
        text = ""
        for factor in (2, 3):
            big = crop.resize((crop.width * factor, crop.height * factor), Image.LANCZOS)
            big.save(p)
            try:
                res, _ = engine(p)
            except Exception:  # noqa: BLE001
                res = None
            text = " ".join(str(r[1]).strip() for r in (res or []) if str(r[1]).strip())
            if text:
                break
        if text:
            extra.append({"x0": x0, "x1": x1, "y0": y0, "y1": y1, "text": _fix_chars(text)})
    return items + extra


def _attach_rules(img, items):
    W, H = img.size
    for rule in _rules(img.convert("L")):
        target = None
        for it in items:
            if it["y0"] - 6 <= rule["y"] <= it["y1"] + max(16, (it["y1"] - it["y0"]) * 0.9):
                if target is None or abs(rule["y"] - it["y1"]) < abs(rule["y"] - target["y1"]):
                    target = it
        n = max(4, min(40, int((rule["x1"] - rule["x0"]) / W * 340)))
        if target is not None:
            target["text"] = target["text"].rstrip(" _") + " " + "_" * n
            target["x1"] = max(target["x1"], rule["x1"])
        else:
            items.append({"x0": rule["x0"], "x1": rule["x1"], "y0": rule["y"],
                          "y1": rule["y"] + 4, "text": "_" * n})
    items.sort(key=lambda d: (d["y0"] + d["y1"]) / 2)
    return items


def build_docx(img, items, title=""):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt

    W, H = img.size
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3)
    sec.right_margin = Cm(1.5)
    sec.top_margin = Cm(2)
    sec.bottom_margin = Cm(2)

    usable_w = 21 - 4.5
    usable_h_pt = (29.7 - 4) / 2.54 * 72.0
    scale = usable_h_pt / H

    heights = [max(6.0, it["y1"] - it["y0"]) for it in items]
    med_h = statistics.median(heights) if heights else 24.0
    # Matn o'lchamini nisbatan hisoblaymiz (asosiy matn = 14 pt)
    sizes = [max(9.0, min(20.0, 14.0 * h / med_h)) for h in heights]
    med = 14.0

    prev_bottom = None
    for it, sz in zip(items, sizes):
        size = max(9.0, min(20.0, sz))
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.line_spacing = 1.0

        cx = ((it["x0"] + it["x1"]) / 2) / W
        if 0.42 <= cx <= 0.58:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif it["x1"] / W > 0.88 and it["x0"] / W > 0.5:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf.left_indent = Cm(max(0.0, it["x0"] / W * usable_w))

        if prev_bottom is not None:
            gap = (it["y0"] - prev_bottom) * scale
            if gap > 3:
                pf.space_before = Pt(min(60.0, gap))
        prev_bottom = it["y1"]

        run = p.add_run(it["text"])
        run.font.name = "Times New Roman"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        run.font.size = Pt(round(size * 2) / 2.0)
        t = it["text"].replace("_", "").strip()
        if t and t.upper() == t and len(t) > 3:
            run.bold = True
        elif p.alignment == WD_ALIGN_PARAGRAPH.CENTER and size >= med * 1.08:
            run.bold = True

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def image_to_docx(raw):
    """Rasm baytlaridan layout saqlangan .docx baytlarini qaytaradi."""
    from PIL import Image

    if not _available():
        raise RuntimeError("ocr_off")
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) < 1400:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    items = _read_lines(img)
    if not items:
        raise RuntimeError("Rasmda matn topilmadi")
    return build_docx(img, items)


def image_to_text(raw):
    """Faqat matn (zaxira variant)."""
    from PIL import Image

    if not _available():
        raise RuntimeError("ocr_off")
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) < 1400:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    return "\n".join(it["text"] for it in _read_lines(img))


def _rows(raw):
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) < 1400:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    gray = img.convert("L")
    items = _read_lines(img)
    items = _fill_missing(img, gray, items)
    items = _attach_rules(img, items)
    return img, items


def image_to_docx_and_text(raw):
    """Bir marta OCR qilib: (docx baytlari, matn) qaytaradi."""
    if not _available():
        raise RuntimeError("ocr_off")
    img, items = _rows(raw)
    if not items:
        raise RuntimeError("Rasmda matn topilmadi")
    text = "\n".join(it["text"] for it in items)
    return build_docx(img, items), text


def image_to_docx(raw):
    return image_to_docx_and_text(raw)[0]
