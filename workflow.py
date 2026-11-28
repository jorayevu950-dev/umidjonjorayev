# -*- coding: utf-8 -*-
"""
Ish jarayonini boshqaruvchi modul.

1. AI (yoki zaxira: oflayn) orqali matn tuzilmasi
2. Mavzuga mos rasmlarni topish va yuklab olish
3. Natijani make_docx / make_pptx uchun tayyor holda qaytarish
"""

import os
import re
import shutil

import config
import image_finder
from ai_engine import AIError, ai_available, ai_document, ai_presentation
from content_engine import build_document, build_presentation

# Oflayn rejimda rasm qidirish uchun soha kalitlari (inglizcha)
DOMAIN_EN = {
    "it": "information technology computer",
    "iqtisod": "economy business finance",
    "pedagogika": "education classroom students",
    "tibbiyot": "medicine healthcare hospital",
    "huquq": "law justice court",
    "ekologiya": "environment nature ecology",
    "qurilish": "construction building site",
    "qishloq": "agriculture farming field",
    "umumiy": "science research university",
}


def _safe(text, limit=40):
    text = re.sub(r"[\\/:*?\"<>|]", "", text or "")
    text = re.sub(r"\s+", "_", text.strip())
    return text[:limit].strip("_") or "rasm"


def build_work(kind, topic, info, size, plan, use_images=True, stamp="", force_offline=False, lang="uz", img_target=None, source=""):
    """
    Qaytaradi: (data, mode, note)
      mode: 'ai' yoki 'offline'
      note: AI ishlamagan bo'lsa sabab matni (aks holda '')
    """
    mode = "offline"
    note = ""
    data = None
    info = dict(info or {})
    if source and str(source).strip():
        info["manba"] = str(source).strip()
    if ai_available() and not force_offline:
        try:
            if kind == "prezentatsiya":
                data = ai_presentation(topic, info, size, plan, lang=lang)
            else:
                data = ai_document(topic, info, size, plan, kind=kind, lang=lang)
            mode = "ai"
        except AIError as exc:
            note = str(exc)[:300]
        except Exception as exc:  # noqa: BLE001
            note = f"Kutilmagan xato: {exc}"[:300]

    if data is None:
        if lang and lang != "uz":
            raise AIError(
                "AI javob bermadi. Rus yoki ingliz tilida hujjat faqat AI rejimida "
                "tayyorlanadi (oflayn shablon faqat o'zbekcha). Qayta urinib ko'ring "
                "yoki /ai bilan kalitni tekshiring."
            )
        if kind == "prezentatsiya":
            data = build_presentation(topic, info, slides=size, plan=plan)
        else:
            data = build_document(topic, info, pages=size, plan=plan, kind=kind)
        data["source"] = "offline"
        if ai_available() and not note and not force_offline:
            note = "AI javob bermadi"

    data["kind"] = kind
    data["lang"] = lang or "uz"
    data["stamp"] = stamp

    if use_images and config.IMAGES_ENABLED:
        try:
            _attach_images(data, kind, topic, stamp, img_target)
        except Exception:  # noqa: BLE001
            pass
    return data, mode, note


# ---------------------------------------------------------------------------
def _attach_images(data, kind, topic, stamp, want=None):
    out_dir = os.path.join(config.IMG_DIR, _safe(stamp or "tmp", 30))
    os.makedirs(out_dir, exist_ok=True)

    want = 0 if want is None else int(want)          # -1 = hamma slayd
    if want > 6:
        want = 6

    if kind == "prezentatsiya":
        slides = data.get("slides") or []
        max_n = config.MAX_IMAGES_SLIDES if want <= 0 else want
        if want == -1:
            max_n = max(1, len(slides) + 1)
        targets = [s for i, s in enumerate(slides) if i % 2 == 0]
        if want == -1:
            targets = [s for i, s in enumerate(slides) if i != 0]
        elif want and len(targets) < want:
            # ko'proq rasm so'ralgan bo'lsa - qolgan slaydlarga ham qo'shamiz
            extra = [s for i, s in enumerate(slides) if i != 0 and s not in targets]
            targets = targets + extra
        pairs = []
        for s in targets:
            q = s.get("image_query") or _fallback_query(data.get("domain"), topic)
            pairs.append((q, s.get("image_caption") or s.get("title")))
        found = image_finder.fetch_for_queries(pairs[:max_n], out_dir, prefix="s")
        # Rasmni aynan o'z slaydiga bog'laymiz (topilmagan bo'lsa - siljimaydi)
        for img in found:
            idx = img.get("index")
            if idx is None or idx >= len(targets):
                continue
            slide = targets[idx]
            slide["image"] = img.get("path")
            slide["image_caption"] = img.get("caption")
            slide["image_credit"] = img.get("credit")
        data["images_found"] = len(found)
        data["images_planned"] = len(pairs[:max_n])
        return

    # Hujjat: har bir chapterdan bittadan kichik bo'lim tanlanadi
    subs = []
    for ci, ch in enumerate(data.get("chapters") or []):
        for sub in ch.get("subs") or []:
            subs.append((ci, sub))
    max_n = want or config.MAX_IMAGES_DOC
    picks = []
    seen_ch = set()
    for ci, sub in subs:            # birinchi navbatda har bobdan bittadan
        if ci not in seen_ch:
            seen_ch.add(ci)
            picks.append(sub)
    for ci, sub in subs:
        if len(picks) >= max_n:
            break
        if sub not in picks:
            picks.append(sub)
    picks = picks[:max_n]

    pairs = []
    for sub in picks:
        q = sub.get("image_query") or _fallback_query(data.get("domain"), topic)
        caption = sub.get("image_caption") or sub.get("title") or topic
        pairs.append((q, caption))

    found = image_finder.fetch_for_queries(pairs, out_dir, prefix="d")
    for img in found:
        idx = img.get("index")
        if idx is None or idx >= len(picks):
            continue
        sub = picks[idx]
        sub["image"] = img.get("path")
        sub["image_caption"] = img.get("caption")
        sub["image_credit"] = img.get("credit")
    data["images_found"] = len(found)
    data["images_planned"] = len(pairs)


def _fallback_query(domain_name, topic):
    key = (domain_name or "").lower()
    for k, en in DOMAIN_EN.items():
        if k in key:
            return en
    return "science research"


def cleanup_images(stamp):
    """Vaqtinchalik rasmlar papkasini o'chiradi."""
    path = os.path.join(config.IMG_DIR, _safe(stamp or "tmp", 30))
    shutil.rmtree(path, ignore_errors=True)
