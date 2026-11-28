# -*- coding: utf-8 -*-
"""
Qo'shimcha vositalar: rasm -> PDF, fayllarni ZIP qilish, ZIP ochish, rasm -> matn (OCR).
Hammasi oflayn ishlaydi (OCR uchun rapidocr moduli kerak).
"""

import io
import os
import uuid
import zipfile

import config


# ---------------------------------------------------------------------------
# Rasm -> PDF
# ---------------------------------------------------------------------------
def images_to_pdf(images):
    """Baytlar ro'yxatini bitta A4 PDF ga jamlaydi. Qaytaradi: PDF baytlari."""
    from PIL import Image

    pages = []
    for raw in images:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        # A4 o'lchamiga (300 dpi) sig'diramiz, nisbatni saqlab
        aw, ah = 2480, 3508
        scale = min(aw / img.width, ah / img.height)
        if scale < 1:
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        page = Image.new("RGB", (aw, ah), (255, 255, 255))
        page.paste(img, ((aw - img.width) // 2, (ah - img.height) // 2))
        pages.append(page)

    if not pages:
        raise RuntimeError("Rasm topilmadi")

    out = io.BytesIO()
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=300.0)
    return out.getvalue()


def images_to_pdf_file(images, path):
    data = images_to_pdf(images)
    with open(path, "wb") as f:
        f.write(data)
    return path


# ---------------------------------------------------------------------------
# ZIP
# ---------------------------------------------------------------------------
def make_zip(files, arcname_prefix=""):
    """
    files: [(filename, bytes), ...]
    Qaytaradi: zip baytlari.
    """
    if not files:
        raise RuntimeError("Fayl topilmadi")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        used = set()
        for name, data in files:
            base = os.path.basename(name or "fayl")
            name2 = (arcname_prefix + base) if arcname_prefix else base
            # bir xil nom bo'lsa - 2, 3, ...
            n = 1
            stem, ext = os.path.splitext(name2)
            while name2 in used:
                n += 1
                name2 = f"{stem}_{n}{ext}"
            used.add(name2)
            zf.writestr(name2, data)
    return out.getvalue()


def unzip_files(raw):
    """ZIP ichidagi fayllarni qaytaradi: [(nom, baytlar), ...]."""
    out = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if info.file_size > 40 * 1024 * 1024:
                    continue
                out.append((os.path.basename(info.filename), zf.read(info)))
    except zipfile.BadZipFile:
        raise RuntimeError("Bu fayl ZIP emas. RAR bo'lsa - ZIP qilib yuboring.")
    return out[:30]


# ---------------------------------------------------------------------------
# OCR (rasm -> matn)
# ---------------------------------------------------------------------------
_OCR = None


def ocr_available():
    try:
        import importlib.util

        return importlib.util.find_spec("rapidocr_onnxruntime") is not None
    except Exception:  # noqa: BLE001
        return False


def _ocr_engine():
    global _OCR
    if _OCR is not None:
        return _OCR
    from rapidocr_onnxruntime import RapidOCR

    _OCR = RapidOCR()
    return _OCR


def image_to_text(raw):
    """Rasmdagi matnni o'qiydi. rapidocr bo'lmasa RuntimeError('ocr_off')."""
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
    except Exception:  # noqa: BLE001
        raise RuntimeError("ocr_off")

    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) < 1200:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)

    tmp = os.path.join(config.DATA_DIR, "_ocr_tmp_%s.png" % uuid.uuid4().hex[:10])
    os.makedirs(config.DATA_DIR, exist_ok=True)
    img.save(tmp, "PNG")
    try:
        engine = _ocr_engine()
        result, _ = engine(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    if not result:
        return ""
    lines = [str(item[1]).strip() for item in result if len(item) > 1 and str(item[1]).strip()]
    return "\n".join(lines)


def image_to_docx(raw):
    """Rasm -> Word (.docx) ko'rinishini saqlab. (docx baytlari, matn)."""
    import ocr_word

    return ocr_word.image_to_docx_and_text(raw)
