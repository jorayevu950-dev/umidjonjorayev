# -*- coding: utf-8 -*-
"""
Word (.docx) hujjatini yaratish moduli.

Standard talab talablari: A4, Times New Roman 14, 1,5 interval,
3 sm chap hoshiya, sahifa raqamlari, mundarija.
"""

import os
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import i18n
from docx.shared import Cm, Pt, RGBColor

FONT = "Times New Roman"
SIZE = 14


def _set_run_font(run, size=SIZE, bold=False, name=FONT):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)


def _style_font(style, size=SIZE, bold=False):
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), FONT)


def _para(doc, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=True,
          before=0, after=0, bold=False, size=SIZE, spacing=1.5):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.line_spacing = spacing
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.first_line_indent = Cm(1.25) if indent else Cm(0)
    if text:
        run = p.add_run(text)
        _set_run_font(run, size=size, bold=bold)
    return p


def _add_image(doc, path, number, caption, credit="", lang="uz"):
    """Rasmni markazga joylaydi va ostiga izoh yozadi."""
    import os as _os

    from PIL import Image

    if not path or not _os.path.exists(path):
        return False

    width = Cm(11.5)
    try:
        with Image.open(path) as im:
            w, h = im.size
        # Baland rasm sahifadan chiqib ketmasligi uchun kenglikni cheklaymiz
        if h > w:
            width = Cm(9.0)
    except Exception:  # noqa: BLE001
        pass

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run()
    try:
        run.add_picture(path, width=width)
    except Exception:  # noqa: BLE001
        return False

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.first_line_indent = Cm(0)
    cap.paragraph_format.space_before = Pt(4)
    cap.paragraph_format.space_after = Pt(10)
    cap.paragraph_format.line_spacing = 1.0
    cap_run = cap.add_run(i18n.t(lang, "figure", n=number, cap=caption))
    _set_run_font(cap_run, size=12)

    if credit:
        cr = cap.add_run(f"  ({credit})")
        _set_run_font(cr, size=10)
        cr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    return True


def _add_page_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)
    return p


def _add_field(paragraph, instr, placeholder=""):
    """Word maydonini (field) qo'shadi - sahifa raqami, mundarija uchun."""
    run = paragraph.add_run()
    _set_run_font(run, size=SIZE)
    r = run._r

    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")

    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = instr

    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")

    text = OxmlElement("w:t")
    text.text = placeholder

    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")

    for el in (fld_begin, instr_text, fld_sep, text, fld_end):
        r.append(el)


def _page_numbers(section):
    """Pastki kolontitulga sahifa raqamini qo'yadi."""
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    _add_field(p, "PAGE", "1")


def _update_fields_on_open(doc):
    """Word ochilganda mundarijani avtomatik yangilashni so'raydi."""
    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)


def _safe_filename(text, limit=40):
    text = re.sub(r"[\\/:*?\"<>|]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    if len(text) > limit:
        cut = text[:limit]
        if "_" in cut:
            cut = cut[:cut.rfind("_")]
        text = cut
    return text.strip("_") or "hujjat"


def _title_page(doc, data, work_title):
    info = data["info"]
    lang = data.get("lang", "uz")
    uni = (info.get("muassasa") or "").strip()

    _para(doc, i18n.t(lang, "ministry"),
          align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, bold=True, spacing=1.0)
    if uni:
        _para(doc, uni.upper(), align=WD_ALIGN_PARAGRAPH.CENTER, indent=False,
              bold=True, before=6, spacing=1.0)
    if info.get("fan"):
        _para(doc, i18n.t(lang, "chair", fan=info["fan"]), align=WD_ALIGN_PARAGRAPH.CENTER,
              indent=False, before=6, spacing=1.0)

    for _ in range(4):
        _para(doc, "", indent=False, spacing=1.0)

    _para(doc, work_title, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, bold=True,
          size=20, spacing=1.0)
    _para(doc, i18n.t(lang, "topic_word"), align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, before=6, spacing=1.0)
    _para(doc, f"«{data['topic']}»", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False,
          bold=True, size=16, before=12, spacing=1.5)

    for _ in range(4):
        _para(doc, "", indent=False, spacing=1.0)

    # 3x4 rasm (agar yuborilgan bo'lsa) - o'ng tomonda
    photo = info.get("photo")
    if photo and os.path.exists(photo):
        ph = doc.add_paragraph()
        ph.paragraph_format.first_line_indent = Cm(0)
        ph.paragraph_format.space_before = Pt(0)
        ph.paragraph_format.space_after = Pt(8)
        ph.paragraph_format.line_spacing = 1.0
        ph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        try:
            ph.add_run().add_picture(photo, width=Cm(3), height=Cm(4))
        except Exception:  # noqa: BLE001
            pass

    lines = []
    if info.get("fish"):
        lines.append(f"{i18n.t(lang, 'student')}: {info['fish']}")
    if info.get("guruh"):
        lines.append(f"{i18n.t(lang, 'group')}: {info['guruh']}")
    if info.get("oqituvchi"):
        lines.append(f"{i18n.t(lang, 'supervisor')}: {info['oqituvchi']}")
    for line in lines:
        _para(doc, line, align=WD_ALIGN_PARAGRAPH.RIGHT, indent=False, spacing=1.5)

    for _ in range(5):
        _para(doc, "", indent=False, spacing=1.0)

    city = info.get("shahar") or "Toshkent"
    year = info.get("yil") or "2026"
    _para(doc, f"{city} — {year}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, spacing=1.0)


# ---------------------------------------------------------------------------

def create_document(data, out_dir):
    """Tayyor tuzilma asosida .docx fayl yaratadi va fayl yo'lini qaytaradi."""
    topic = data["topic"]
    info = data["info"]
    kind = data.get("kind", "referat")
    lang = data.get("lang", "uz")
    work_title = i18n.kind_title(lang, kind)

    doc = Document()

    # Sahifa sozlamalari: A4
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(1.5)
    section.different_first_page_header_footer = True

    # Asosiy uslub
    normal = doc.styles["Normal"]
    _style_font(normal, SIZE, bold=False)
    npf = normal.paragraph_format
    npf.line_spacing = 1.5
    npf.space_before = Pt(0)
    npf.space_after = Pt(0)
    npf.first_line_indent = Cm(1.25)
    npf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    h1 = doc.styles["Heading 1"]
    _style_font(h1, SIZE, bold=True)
    h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1.paragraph_format.first_line_indent = Cm(0)
    h1.paragraph_format.space_before = Pt(0)
    h1.paragraph_format.space_after = Pt(12)
    h1.paragraph_format.line_spacing = 1.5
    h1.paragraph_format.keep_with_next = True

    h2 = doc.styles["Heading 2"]
    _style_font(h2, SIZE, bold=True)
    h2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h2.paragraph_format.first_line_indent = Cm(1.25)
    h2.paragraph_format.space_before = Pt(12)
    h2.paragraph_format.space_after = Pt(6)
    h2.paragraph_format.line_spacing = 1.5
    h2.paragraph_format.keep_with_next = True

    # Mualliflik ma'lumotlari
    cp = doc.core_properties
    cp.title = topic
    cp.author = info.get("fish") or "Talaba"
    cp.comments = "OreateAI talaba yordamchisi tomonidan tayyorlandi"

    # 1. Titul varaq (foydalanuvchi xohlamasa - o'tkazib yuboriladi)
    no_title = bool((data.get("info") or {}).get("no_title"))
    if not no_title:
        _title_page(doc, data, work_title)

    # 2. Mundarija
    _add_page_break(doc)
    _para(doc, i18n.t(lang, "toc"), align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, bold=True, after=12)
    toc_para = doc.add_paragraph()
    toc_para.paragraph_format.first_line_indent = Cm(0)
    _add_field(toc_para, 'TOC \\o "1-2" \\h \\z \\u',
               i18n.t(lang, "toc_note"))

    # 3. Kirish
    _add_page_break(doc)
    doc.add_heading(i18n.t(lang, "intro"), level=1)
    for text in data["intro"]:
        _para(doc, text)

    # 4. Asosiy qism (rasmlar bilan)
    fig_no = 0
    for chapter in data["chapters"]:
        h = doc.add_heading(chapter["title"], level=1)
        h.paragraph_format.page_break_before = True
        for sub in chapter["subs"]:
            doc.add_heading(sub["title"], level=2)
            for pi, text in enumerate(sub["paras"]):
                _para(doc, text)
                if pi == 0 and sub.get("image"):
                    fig_no += 1
                    ok = _add_image(
                        doc,
                        sub["image"],
                        fig_no,
                        sub.get("image_caption") or sub["title"],
                        sub.get("image_credit", ""),
                        lang,
                    )
                    if not ok:
                        fig_no -= 1

    # 5. Xulosa
    h = doc.add_heading(i18n.t(lang, "conclusion"), level=1)
    h.paragraph_format.page_break_before = True
    for text in data["conclusion"]:
        _para(doc, text)

    # 6. Adabiyotlar
    h = doc.add_heading(i18n.t(lang, "references"), level=1)
    h.paragraph_format.page_break_before = True
    for i, ref in enumerate(data["references"], start=1):
        p = _para(doc, f"{i}. {ref}", indent=False)
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.75)

    # Sahifa raqamlari
    _page_numbers(section)
    _update_fields_on_open(doc)

    # Saqlash
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{work_title.replace(' ', '_')}_{_safe_filename(topic)}_{data.get('stamp', '')}.docx"
    fname = fname.replace("__", "_").replace("_.docx", ".docx")
    path = os.path.join(out_dir, fname)
    doc.save(path)
    return path
