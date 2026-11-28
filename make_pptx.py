# -*- coding: utf-8 -*-
"""
PowerPoint (.pptx) prezentatsiyasini yaratish moduli.
16:9 format, toza va akademik dizayn.
"""

import os
import re

from lxml import etree
import i18n
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

NAVY = RGBColor(0x10, 0x37, 0x5C)
NAVY_DARK = RGBColor(0x0A, 0x24, 0x40)
GOLD = RGBColor(0xF2, 0xA9, 0x3B)
GREY = RGBColor(0x5A, 0x67, 0x78)
LIGHT = RGBColor(0xF4, 0xF6, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT = "Arial"


def _safe_filename(text, limit=45):
    text = re.sub(r"[\\/:*?\"<>|]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    if len(text) > limit:
        cut = text[:limit]
        if "_" in cut:
            cut = cut[:cut.rfind("_")]
        text = cut
    return text.strip("_") or "prezentatsiya"


def _solid(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _alpha(shape, color, alpha_pct):
    """Shaffof to'ldirish (alpha 0-100)."""
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    solid = shape.fill._xPr.find(qn("a:solidFill"))
    if solid is not None:
        srgb = solid.find(qn("a:srgbClr"))
        if srgb is not None:
            alpha = etree.SubElement(srgb, qn("a:alpha"))
            alpha.set("val", str(int(alpha_pct * 1000)))


def _rect(slide, left, top, width, height, color, alpha_pct=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(left), Inches(top), Inches(width), Inches(height))
    if alpha_pct is None:
        _solid(s, color)
    else:
        _alpha(s, color, alpha_pct)
    return s


def _textbox(slide, left, top, width, height, text, size=18, bold=False,
             color=WHITE, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             spacing=1.0, italic=False):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    run = p.add_run()
    run.text = text
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    return box


def _picture(slide, path, caption="", credit="", left=7.1, top=1.7, max_w=5.4, max_h=4.55):
    """O'ng tomonga rasm va ostiga izoh joylaydi."""
    if not path or not os.path.exists(path):
        return False

    from PIL import Image

    try:
        with Image.open(path) as im:
            w, h = im.size
    except Exception:  # noqa: BLE001
        return False
    if not w or not h:
        return False

    ratio = h / w
    width = max_w
    height = width * ratio
    if height > max_h:
        height = max_h
        width = height / ratio

    x = left + (max_w - width) / 2
    y = top + (max_h - height) / 2

    try:
        pic = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(width), Inches(height))
    except Exception:  # noqa: BLE001
        return False

    # Ingichka ramka
    pic.line.color.rgb = RGBColor(0xD8, 0xDE, 0xE6)
    pic.line.width = Pt(0.75)

    if caption:
        text = caption if len(caption) <= 90 else caption[:88].rstrip() + "…"
        _textbox(slide, left, top + max_h + 0.06, max_w, 0.42, text,
                 size=10, color=GREY, align=PP_ALIGN.CENTER)
    return True


def _bullets(slide, items, left=0.95, top=1.65, width=11.4, height=4.9,
             size=20, color=NAVY_DARK, gap=12):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0

    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.15
        p.space_after = Pt(gap)
        p.level = 0

        ppr = p._p.get_or_add_pPr()
        ppr.set("marL", str(Emu(Inches(0.42))))
        ppr.set("indent", str(-Emu(Inches(0.42))))
        bu_font = etree.SubElement(ppr, qn("a:buFont"))
        bu_font.set("typeface", "Arial")
        bu_char = etree.SubElement(ppr, qn("a:buChar"))
        bu_char.set("char", "▪")

        run = p.add_run()
        run.text = item
        f = run.font
        f.name = FONT
        f.size = Pt(size)
        f.color.rgb = color
    return box


def _numbered(slide, items, left=0.95, top=1.75, width=11.4, size=19, gap=14):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(4.8))
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.1
        p.space_after = Pt(gap)
        run = p.add_run()
        run.text = f"{i:02d}   {item}"
        f = run.font
        f.name = FONT
        f.size = Pt(size)
        f.color.rgb = NAVY_DARK
        f.bold = False
    return box


def _header(slide, title, size=26):
    _rect(slide, 0, 0, 13.333, 1.15, NAVY)
    _rect(slide, 0.62, 0.32, 0.09, 0.52, GOLD)
    t = _textbox(slide, 0.9, 0.24, 11.6, 0.75, title, size=size, bold=True,
                 color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
    return t


def _footer(slide, topic, number):
    _rect(slide, 0.62, 6.92, 12.1, 0.015, RGBColor(0xD8, 0xDE, 0xE6))
    short = topic if len(topic) <= 95 else topic[:92] + "..."
    _textbox(slide, 0.62, 7.02, 9.8, 0.3, f"«{short}»", size=10, color=GREY)
    _textbox(slide, 11.6, 7.02, 1.1, 0.3, str(number), size=11, bold=True,
             color=NAVY, align=PP_ALIGN.RIGHT)


def _title_slide(prs, data, work_title, lang="uz"):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(slide, 0, 0, 13.333, 7.5, NAVY)
    _rect(slide, 0, 0, 13.333, 0.16, GOLD)
    _rect(slide, 9.4, -1.6, 6.0, 6.0, GOLD, alpha_pct=12, shape=MSO_SHAPE.OVAL)
    _rect(slide, -2.2, 4.6, 5.4, 5.4, GOLD, alpha_pct=8, shape=MSO_SHAPE.OVAL)

    info = data["info"]
    uni = (info.get("muassasa") or i18n.t(lang, "ministry")).upper()
    if len(uni) > 78:
        uni = uni[:75] + "..."
    _textbox(slide, 0.9, 0.85, 11.5, 0.4, uni, size=13, color=RGBColor(0xC7, 0xD3, 0xE0),
             align=PP_ALIGN.CENTER)

    _textbox(slide, 0.9, 1.75, 11.5, 0.5, work_title, size=16, bold=True, color=GOLD,
             align=PP_ALIGN.CENTER)

    topic = data["topic"]
    tsize = 40 if len(topic) <= 55 else (34 if len(topic) <= 80 else 28)
    _textbox(slide, 0.85, 2.4, 11.6, 2.2, topic, size=tsize, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05)

    _rect(slide, 6.17, 4.78, 1.0, 0.06, GOLD)

    lines = []
    if info.get("fish"):
        lines.append(info["fish"])
    if info.get("guruh"):
        lines.append(f"{i18n.t(lang, 'group')}: {info['guruh']}")
    if info.get("oqituvchi"):
        lines.append(f"{i18n.t(lang, 'supervisor')}: {info['oqituvchi']}")
    _textbox(slide, 0.9, 5.2, 11.5, 1.0, "\n".join(lines), size=15,
             color=RGBColor(0xDD, 0xE5, 0xEE), align=PP_ALIGN.CENTER, spacing=1.3)

    _textbox(slide, 0.9, 6.75, 11.5, 0.4,
             f"{info.get('shahar') or 'Toshkent'} — {info.get('yil') or '2026'}",
             size=13, color=RGBColor(0xB9, 0xC7, 0xD6), align=PP_ALIGN.CENTER)
    return slide


def create_presentation(data, out_dir, stamp=""):
    """Tayyor tuzilma asosida .pptx yaratadi va fayl yo'lini qaytaradi."""
    lang = data.get("lang", "uz")
    work_title = i18n.kind_title(lang, data.get("kind") or "prezentatsiya")
    topic = data["topic"]

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    _title_slide(prs, data, work_title, lang)
    number = 2

    # Reja
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _header(slide, i18n.t(lang, "plan"))
    _numbered(slide, data["plan_slide"]["bullets"])
    _footer(slide, topic, number)
    number += 1

    # Asosiy slaydlar
    for item in data["slides"]:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _header(slide, item["title"], size=26 if len(item["title"]) < 55 else 22)
        has_img = bool(item.get("image")) and os.path.exists(item.get("image", ""))
        if has_img:
            _bullets(slide, item["bullets"], left=0.95, top=1.7, width=5.85, size=16, gap=10)
            ok = _picture(slide, item["image"], item.get("image_caption", ""))
            if not ok:
                _bullets(slide, item["bullets"], left=0.95, top=1.65, width=11.4,
                         size=20 if len(item["bullets"]) <= 5 else 18)
        else:
            _bullets(slide, item["bullets"], size=20 if len(item["bullets"]) <= 5 else 18)
        _footer(slide, topic, number)
        number += 1

    # Xulosa
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _header(slide, i18n.t(lang, "conclusion"))
    _bullets(slide, data["conclusion"], size=19)
    _footer(slide, topic, number)
    number += 1

    # Adabiyotlar
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _header(slide, i18n.t(lang, "references"))
    refs = data.get("references", [])
    box = slide.shapes.add_textbox(Inches(0.95), Inches(1.7), Inches(11.4), Inches(4.9))
    tf = box.text_frame
    tf.word_wrap = True
    for i, ref in enumerate(refs, start=1):
        p = tf.paragraphs[0] if i == 1 else tf.add_paragraph()
        p.line_spacing = 1.15
        p.space_after = Pt(10)
        run = p.add_run()
        run.text = f"{i}. {ref}"
        run.font.name = FONT
        run.font.size = Pt(14)
        run.font.color.rgb = NAVY_DARK
    _footer(slide, topic, number)
    number += 1

    # Yakuniy slayd
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(slide, 0, 0, 13.333, 7.5, NAVY)
    _rect(slide, 0, 7.34, 13.333, 0.16, GOLD)
    _rect(slide, 10.2, 3.6, 4.6, 4.6, GOLD, alpha_pct=10, shape=MSO_SHAPE.OVAL)
    _textbox(slide, 0.9, 2.9, 11.5, 1.0, i18n.t(lang, "thanks"), size=42, bold=True,
             color=WHITE, align=PP_ALIGN.CENTER)
    _textbox(slide, 0.9, 4.1, 11.5, 0.6, i18n.t(lang, "thanks_sub"),
             size=16, color=RGBColor(0xC7, 0xD3, 0xE0), align=PP_ALIGN.CENTER)

    os.makedirs(out_dir, exist_ok=True)
    fname = f"{work_title.replace(' ', '_')}_{_safe_filename(topic)}_{stamp}.pptx".replace("__", "_")
    path = os.path.join(out_dir, fname)
    prs.save(path)
    return path
