# -*- coding: utf-8 -*-
"""
Obyektivka (ma'lumotnoma) — Word (.docx) va PDF ko'rinishida.

Tuzilishi obyektivka.uz sayti bilan bir xil:
  A5, hoshiya 40/60/40/60 pt, Times New Roman
  1-sahifa: MA'LUMOTNOMA, F.I.SH, sana + lavozim, 3x4 rasm,
            shaxsiy ma'lumotlar, MEHNAT FAOLIYATI
  2-sahifa: yaqin qarindoshlari haqida MA'LUMOT (5 ustunli jadval)
"""

import io
import re
from datetime import datetime


# ---------------------------------------------------------------------------
# 1. Shablon
# ---------------------------------------------------------------------------
TEMPLATE = """F.I.SH: 
Sana: 
Lavozim: 
Mehnat: 
"""


def template_text():
    return TEMPLATE


_KEYS = {
    "f.i.sh": "fio", "f.i.sh": "fio", "fish": "fio", "f.i.sh.": "fio", "fio": "fio",
    "familya": "fam", "familiya": "fam", "ism": "ism", "sharif": "sharif", "otasining ismi": "sharif",
    "sana": "sana", "joriy lavozim sanasi": "sana",
    "lavozim": "lavozim", "joriy lavozim": "lavozim", "joriy lavozim to'liq": "lavozim",
    "universitet": "universitet", "otm": "universitet", "o'qish joyi": "universitet",
    "yo'nalish": "yonalish", "yonalish": "yonalish", "ta'lim yo'nalishi": "yonalish",
    "tug'ilgan yili": "t_yil", "tugilgan yili": "t_yil", "tug'ilgan sana": "t_yil", "tug'ilgan yil": "t_yil",
    "tug'ilgan joyi": "t_joy", "tugilgan joyi": "t_joy",
    "millati": "millat", "millat": "millat",
    "partiyaviyligi": "partiya", "partiya": "partiya",
    "ma'lumoti": "malumot", "malumoti": "malumot", "malumot": "malumot",
    "tamomlagan": "tamomlagan",
    "mutaxassisligi": "mutaxassislik", "ma'lumoti bo'yicha mutaxassisligi": "mutaxassislik",
    "ilmiy darajasi": "ilmiy_daraja",
    "ilmiy unvoni": "ilmiy_unvon",
    "chet tillari": "tillar", "qaysi chet tillarini biladi": "tillar", "chet tillarini biladi": "tillar",
    "mukofot": "mukofot", "davlat mukofoti": "mukofot", "davlat mukofotlari": "mukofot",
    "deputat": "deputat", "kengash a'zosi": "deputat",
    "mehnat": "mehnat", "mehnat faoliyati": "mehnat", "ish joyi": "mehnat", "faoliyat": "mehnat",
}

# Bir nechta qator yoziladigan maydonlar
_MULTI = {"tamomlagan", "ilmiy_daraja", "ilmiy_unvon", "tillar", "mukofot"}

_ROLES = {
    "otasi": "Otasi", "onasi": "Onasi", "akasi": "Akasi", "ukasi": "Ukasi",
    "opasi": "Opasi", "singlisi": "Singlisi", "aka": "Akasi", "uka": "Ukasi",
    "opa": "Opasi", "singil": "Singlisi",
    "turmush o'rtog'i": "Turmush o'rtog'i", "o'g'li": "O'g'li", "qizi": "Qizi",
    "qaynotasi": "Qaynotasi", "qaynonasi": "Qaynonasi", "tog'asi": "Tog'asi",
    "amakisi": "Amakisi", "xolasi": "Xolasi", "ammasi": "Ammasi",
    "buvisi": "Buvisi", "buvasi": "Buvasi", "boshqa": "Boshqa qarindosh",
}

_SCALARS = ("fio", "sana", "lavozim", "universitet", "yonalish", "t_yil", "t_joy",
            "millat", "partiya", "malumot", "mutaxassislik", "deputat")


# ---------------------------------------------------------------------------
# 2. Matnni o'qish
# ---------------------------------------------------------------------------
def _clean(s):
    s = (s or "").replace("\u02bb", "'").replace("\u02bc", "'")
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    return re.sub(r"\s+", " ", s).strip()


def _norm_key(k):
    return _clean(k).lower().rstrip(".").replace("\u2019", "'")


def parse(text):
    """Matnni maydonlarga ajratadi."""
    data = {k: "" for k in _SCALARS}
    for k in _MULTI:
        data[k] = []
    data["mehnat"] = []
    data["qarindosh"] = []
    fam = ism = sharif = ""

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        head, val = (line.split(":", 1) + [""])[:2] if ":" in line else ("", "")
        key = _norm_key(head) if head else ""

        if "|" in val:
            parts = [_clean(p) for p in val.split("|")]
            if key in _ROLES:
                rel = {"role": _ROLES[key], "fio": "", "yil": "", "ish": "", "joy": "",
                       "dead": False, "dead_yil": ""}
                free = []
                for p in parts:
                    low = p.lower()
                    if "vafot" in low:
                        rel["dead"] = True
                        m = re.search(r"(19|20)\d{2}", p)
                        rel["dead_yil"] = m.group(0) if m else ""
                    elif p:
                        free.append(p)
                free = (free + ["", "", "", ""])[:4]
                rel["fio"], rel["yil"], rel["ish"], rel["joy"] = free
                data["qarindosh"].append(rel)
                continue
            if key in ("mehnat", "ish joyi", "faoliyat"):
                parts = (parts + ["", ""])[:2]
                data["mehnat"].append({"davr": parts[0], "ish": parts[1]})
                continue

        if key in _KEYS:
            field = _KEYS[key]
            v = _clean(val)
            if field in _MULTI:
                if v:
                    seps = r"[;,]" if field == "tillar" else ";"
                    data[field].extend([x.strip() for x in re.split(seps, v) if x.strip()])
            elif field == "fam":
                fam = v
            elif field == "ism":
                ism = v
            elif field == "sharif":
                sharif = v
            elif field == "mehnat":
                if v:
                    data["mehnat"].append({"davr": v, "ish": ""})
            else:
                data[field] = v
            continue

    if not data["fio"] and (fam or ism):
        data["fio"] = _clean(" ".join([fam, ism, sharif]))
    if not data["sana"]:
        months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
                  "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
        now = datetime.now()
        data["sana"] = "%d-yil %d-%s" % (now.year, now.day, months[now.month - 1])
    for k in _SCALARS:
        if not data[k]:
            data[k] = "-" if k != "lavozim" and k != "universitet" and k != "yonalish" else ""
    return data


def _multiline(items, default="-"):
    items = [x for x in (items or []) if x]
    return items or [default]


def _langs(items):
    items = [x for x in (items or []) if x]
    if not items:
        return "-"
    txt = ", ".join(items)
    return txt + (" tillari" if len(items) > 1 else " tili")


def _work_line(w):
    davr = _clean(w.get("davr") or "")
    ish = _clean(w.get("ish") or "")
    head = davr
    m = re.match(r"^(\d{4})\s*[-\u2013]\s*(\d{4})$", davr)
    if m:
        head = m.group(1) + "-" + m.group(2) + " yy."
    else:
        m2 = re.match(r"^(\d{4})\s*[-\u2013]\s*(now|hozir|h\.v\.?|davom)$", davr, re.I)
        if m2:
            head = m2.group(1) + " y. - h.v."
    if head and ish:
        return head + " - " + ish
    return ish or head


def _header_lines(data):
    """Sana / lavozim qatorlari."""
    lavozim = data.get("lavozim") or ""
    if not lavozim:
        uni = data.get("universitet") or ""
        yon = data.get("yonalish") or ""
        lavozim = uni
        extra = (yon + " yo'nalishi talabasi") if yon else ""
    else:
        extra = ""
    return lavozim or "-", extra


def _crop34(raw):
    """Rasmni 3:4 nisbatga (markazdan) kesadi."""
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    target = 3 / 4
    if w / h > target:
        nw = int(h * target)
        img = img.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
    else:
        nh = int(w / target)
        img = img.crop((0, (h - nh) // 2, w, (h + nh) // 2))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


# ---------------------------------------------------------------------------
# 3. Word
# ---------------------------------------------------------------------------
def build_docx(data, photo=None):
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width = Cm(14.8)
    sec.page_height = Cm(21)
    sec.left_margin = Cm(2.1)
    sec.right_margin = Cm(2.1)
    sec.top_margin = Cm(1.4)
    sec.bottom_margin = Cm(1.4)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(10)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    def para(text="", size=10, bold=False, center=False, space=0, after=2):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.space_before = Pt(space)
        pf.space_after = Pt(after)
        pf.line_spacing = 1.0
        if text:
            r = p.add_run(text)
            r.bold = bold
            r.font.size = Pt(size)
            r.font.name = "Times New Roman"
        return p

    fio = data.get("fio", "-")
    lavozim, extra = _header_lines(data)
    para("MA'LUMOTNOMA", size=12, bold=True, center=True, after=2)
    para(fio, size=11, bold=True, center=True, after=6)

    # --- sana + lavozim + rasm
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    t.columns[0].width = Cm(7.4)
    t.columns[1].width = Cm(3.2)
    left = t.cell(0, 0)
    left.width = Cm(7.4)
    lp = left.paragraphs[0]
    lp.paragraph_format.space_after = Pt(1)
    r = lp.add_run((data.get("sana") or "") + ":")
    r.font.size = Pt(9)
    p2 = left.add_paragraph()
    p2.paragraph_format.space_after = Pt(1)
    r2 = p2.add_run(lavozim)
    r2.bold = True
    r2.font.size = Pt(9.5)
    if extra:
        p3 = left.add_paragraph()
        r3 = p3.add_run(extra)
        r3.font.size = Pt(9)

    cell = t.cell(0, 1)
    cell.width = Cm(3.2)
    cp = cell.paragraphs[0]
    cp.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    def _frame():
        t2 = cell.add_table(rows=1, cols=1)
        t2.autofit = False
        c2 = t2.cell(0, 0)
        c2.width = Cm(2.9)
        tr = t2.rows[0]._tr
        trPr = tr.get_or_add_trPr()
        h = OxmlElement("w:trHeight")
        h.set(qn("w:val"), str(int(3.9 * 567)))
        trPr.append(h)
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right"):
            e = OxmlElement("w:" + edge)
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "6")
            e.set(qn("w:color"), "808080")
            borders.append(e)
        t2._tbl.tblPr.append(borders)
        c2.paragraphs[0].add_run("")

    if photo:
        try:
            cp.add_run().add_picture(io.BytesIO(_crop34(photo)), width=Cm(2.9), height=Cm(3.9))
        except Exception:  # noqa: BLE001
            _frame()
    else:
        _frame()

    para("", after=2)

    # --- maydonlar
    W2 = Cm(5.05)

    def field_table(rows):
        tb = doc.add_table(rows=len(rows), cols=2)
        tb.autofit = False
        for i, (a, b) in enumerate(rows):
            for j, (label, values) in enumerate((a, b)):
                c = tb.cell(i, j)
                c.width = W2
                pr = c.paragraphs[0]
                pr.paragraph_format.space_after = Pt(0)
                rl = pr.add_run(label)
                rl.bold = True
                rl.font.size = Pt(9)
                for val in _multiline(values):
                    pv = c.add_paragraph()
                    pv.paragraph_format.space_after = Pt(0.5)
                    rv = pv.add_run(val)
                    rv.font.size = Pt(9.5)
        return tb

    field_table([
        (("Tug'ilgan yili:", [data.get("t_yil")]), ("Tug'ilgan joyi:", [data.get("t_joy")])),
        (("Millati:", [data.get("millat")]), ("Partiyaviyligi:", [data.get("partiya")])),
    ])
    para("", after=2)
    para("Ma'lumoti:", size=9, bold=True, after=0)
    para(data.get("malumot") or "-", size=9.5, after=3)
    para("Tamomlagan:", size=9, bold=True, after=0)
    for v in _multiline(data.get("tamomlagan")):
        para(v, size=9.5, after=1)
    para("Ma'lumoti bo'yicha mutaxassisligi:", size=9, bold=True, space=2, after=0)
    para(data.get("mutaxassislik") or "-", size=9.5, after=4)

    field_table([
        (("Ilmiy darajasi:", data.get("ilmiy_daraja")), ("Ilmiy unvoni:", data.get("ilmiy_unvon"))),
    ])

    para("Qaysi chet tillarini biladi:", size=9, bold=True, space=4, after=0)
    para(_langs(data.get("tillar")), size=9.5, after=3)
    para("Davlat mukofoti bilan taqdirlanganmi:", size=9, bold=True, after=0)
    para(", ".join(_multiline(data.get("mukofot"), "yo'q")), size=9.5, after=3)
    para("Xalq deputatlari respublika, viloyat, shahar va tuman Kengashi deputatimi "
         "yoki boshqa saylanadigan organlarning a'zosimi:", size=9, bold=True, after=0)
    para(data.get("deputat") or "yo'q", size=9.5, after=6)

    para("MEHNAT FAOLIYATI", size=11, bold=True, center=True, after=3)
    if data.get("mehnat"):
        for w in data["mehnat"]:
            para(_work_line(w), size=9, after=2)
    else:
        para("-", size=9.5)

    # ---------------- 2-sahifa ----------------
    doc.add_page_break()
    para(fio + "ning yaqin qarindoshlari haqida", size=10.5, bold=True, center=True, after=0)
    para("MA'LUMOT", size=11, bold=True, center=True, after=6)

    heads = ["Qarindoshligi", "Familyasi, ismi va otasining ismi",
             "Tug'ilgan yili va joyi", "Ish joyi va lavozimi", "Turar joyi"]
    rows = data.get("qarindosh") or []
    tb = doc.add_table(rows=1 + max(1, len(rows)), cols=5)
    tb.style = "Table Grid"
    tb.autofit = False
    widths = [Cm(2.05), Cm(2.45), Cm(2.25), Cm(1.95), Cm(1.8)]
    for j, h in enumerate(heads):
        c = tb.cell(0, j)
        c.width = widths[j]
        pr = c.paragraphs[0]
        pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pr.paragraph_format.space_after = Pt(0)
        rr = pr.add_run(h)
        rr.bold = True
        rr.font.size = Pt(8)
    if rows:
        for i, w in enumerate(rows, start=1):
            whole = None
            if w.get("dead"):
                whole = (w.get("dead_yil") + "-yilda vafot etgan " if w.get("dead_yil")
                         else "Vafot etgan ")
                if w.get("ish"):
                    whole += "(" + w["ish"] + ")"
            for j, key in enumerate(("role", "fio", "yil")):
                c = tb.cell(i, j)
                c.width = widths[j]
                pr = c.paragraphs[0]
                pr.alignment = WD_ALIGN_PARAGRAPH.LEFT
                pr.paragraph_format.space_after = Pt(0)
                rr = pr.add_run(w.get(key) or "-")
                rr.bold = (j == 0)
                rr.font.size = Pt(8)
            if whole is not None:
                c = tb.cell(i, 3).merge(tb.cell(i, 4))
                pr = c.paragraphs[0]
                pr.paragraph_format.space_after = Pt(0)
                rr = pr.add_run(whole)
                rr.font.size = Pt(8)
            else:
                for j, key in ((3, "ish"), (4, "joy")):
                    c = tb.cell(i, j)
                    c.width = widths[j]
                    pr = c.paragraphs[0]
                    pr.paragraph_format.space_after = Pt(0)
                    rr = pr.add_run(w.get(key) or "-")
                    rr.font.size = Pt(8)
    else:
        c = tb.cell(1, 0)
        rr = c.paragraphs[0].add_run("-")
        rr.font.size = Pt(8)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# 4. PDF
# ---------------------------------------------------------------------------
def build_pdf(data, photo=None):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image as RLImage, PageBreak, Paragraph,
                                    SimpleDocTemplate, Spacer, Table, TableStyle)

    out = io.BytesIO()
    ss = getSampleStyleSheet()
    base = ParagraphStyle("b", parent=ss["Normal"], fontName="Times-Roman",
                          fontSize=9.2, leading=11.2, alignment=TA_LEFT)
    label = ParagraphStyle("l", parent=base, fontName="Times-Bold")
    title = ParagraphStyle("t", parent=base, fontName="Times-Bold", fontSize=12.5,
                           alignment=TA_CENTER, leading=15)
    name = ParagraphStyle("n", parent=base, fontName="Times-Bold", fontSize=11,
                          alignment=TA_CENTER, leading=14)
    small = ParagraphStyle("s", parent=base, fontSize=8, leading=9.5)
    cellc = ParagraphStyle("cc", parent=small, alignment=TA_CENTER)
    cellh = ParagraphStyle("ch", parent=base, fontName="Times-Bold", fontSize=8,
                           alignment=TA_CENTER, leading=9.5)
    mid = ParagraphStyle("m", parent=title, fontSize=11, leading=13)

    def _empty_frame():
        box = Table([[Paragraph("3x4", ParagraphStyle("f", parent=base, fontSize=7,
                                                      alignment=TA_CENTER,
                                                      textColor=colors.grey))]],
                    colWidths=[2.8 * cm], rowHeights=[3.7 * cm])
        box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
                                 ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
        return box

    doc = SimpleDocTemplate(out, pagesize=A5,
                            leftMargin=60, rightMargin=60, topMargin=40, bottomMargin=40,
                            title="Ma'lumotnoma — " + data.get("fio", ""))
    story = []
    fio = data.get("fio", "-")
    lavozim, extra = _header_lines(data)
    story.append(Paragraph("MA'LUMOTNOMA", title))
    story.append(Paragraph(fio, name))
    story.append(Spacer(1, 4))

    left_block = [Paragraph((data.get("sana") or "") + ":", small),
                  Paragraph("<b>" + lavozim + "</b>", base)]
    if extra:
        left_block.append(Paragraph(extra, base))
    if photo:
        try:
            img = RLImage(io.BytesIO(_crop34(photo)), width=2.8 * cm, height=3.7 * cm)
        except Exception:  # noqa: BLE001
            img = _empty_frame()
    else:
        img = _empty_frame()
    t1 = Table([[left_block, img]], colWidths=[7.3 * cm, 2.9 * cm])
    t1.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(t1)
    story.append(Spacer(1, 6))

    def fields(pairs):
        cells, cells2 = [], []
        for lab, vals in pairs:
            cells.append(Paragraph(lab, label))
            cells2.append([Paragraph(v, base) for v in _multiline(vals)])
        tb = Table([[cells[0], cells[1]], [cells2[0], cells2[1]]],
                   colWidths=[5.05 * cm, 5.05 * cm])
        tb.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 1), (-1, 1), 1),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
        ]))
        return tb

    story.append(fields([("Tug'ilgan yili:", [data.get("t_yil")]),
                         ("Tug'ilgan joyi:", [data.get("t_joy")])]))
    story.append(fields([("Millati:", [data.get("millat")]),
                         ("Partiyaviyligi:", [data.get("partiya")])]))

    def one(label_txt, vals, space_before=2, space_after=3):
        story.append(Spacer(1, space_before))
        story.append(Paragraph(label_txt, label))
        for v in _multiline(vals):
            story.append(Paragraph(v, base))
        story.append(Spacer(1, space_after))

    one("Ma'lumoti:", [data.get("malumot")])
    one("Tamomlagan:", data.get("tamomlagan"), space_before=0)
    one("Ma'lumoti bo'yicha mutaxassisligi:", [data.get("mutaxassislik")], space_before=0)
    story.append(fields([("Ilmiy darajasi:", data.get("ilmiy_daraja")),
                         ("Ilmiy unvoni:", data.get("ilmiy_unvon"))]))
    one("Qaysi chet tillarini biladi:", [_langs(data.get("tillar"))])
    one("Davlat mukofoti bilan taqdirlanganmi:",
        [", ".join(_multiline(data.get("mukofot"), "yo'q"))])
    one("Xalq deputatlari respublika, viloyat, shahar va tuman Kengashi deputatimi "
        "yoki boshqa saylanadigan organlarning a'zosimi:", [data.get("deputat") or "yo'q"],
        space_after=6)

    story.append(Paragraph("MEHNAT FAOLIYATI", mid))
    story.append(Spacer(1, 3))
    if data.get("mehnat"):
        for w in data["mehnat"]:
            story.append(Paragraph(_work_line(w), ParagraphStyle("w", parent=base,
                                                                 fontSize=9, leading=11)))
    else:
        story.append(Paragraph("-", base))

    story.append(PageBreak())
    story.append(Paragraph(fio + "ning yaqin qarindoshlari haqida",
                           ParagraphStyle("q", parent=name, fontSize=10, leading=12)))
    story.append(Paragraph("MA'LUMOT", ParagraphStyle("m2", parent=title, fontSize=10, leading=12)))
    story.append(Spacer(1, 6))

    heads = ["Qarindoshligi", "Familyasi, ismi va otasining ismi",
             "Tug'ilgan yili va joyi", "Ish joyi va lavozimi", "Turar joyi"]
    rows = [[Paragraph(h, cellh) for h in heads]]
    for w in data.get("qarindosh") or []:
        row = [Paragraph(w.get("role") or "-", ParagraphStyle("rb", parent=cellc, fontName="Times-Bold")),
               Paragraph(w.get("fio") or "-", small),
               Paragraph(w.get("yil") or "-", small)]
        if w.get("dead"):
            txt = ((w.get("dead_yil") + "-yilda vafot etgan ") if w.get("dead_yil")
                   else "Vafot etgan ")
            if w.get("ish"):
                txt += "(" + w["ish"] + ")"
            row.append(Paragraph(txt, small))
            row.append("")
        else:
            row.append(Paragraph(w.get("ish") or "-", small))
            row.append(Paragraph(w.get("joy") or "-", small))
        rows.append(row)
    if len(rows) == 1:
        rows.append([Paragraph("-", cellc)] + [Paragraph("", small) for _ in range(4)])
    tb2 = Table(rows, colWidths=[2.0 * cm, 2.3 * cm, 2.15 * cm, 1.85 * cm, 1.8 * cm], repeatRows=1)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]
    for i, w in enumerate(data.get("qarindosh") or [], start=1):
        if w.get("dead"):
            style_cmds.append(("SPAN", (i, 3), (i, 4)))
    tb2.setStyle(TableStyle(style_cmds))
    story.append(tb2)

    doc.build(story)
    return out.getvalue()


def build_all(data, photo=None):
    """(docx baytlari, pdf baytlari) — PDF xato bersa (docx, None)."""
    docx_bytes = build_docx(data, photo)
    try:
        pdf_bytes = build_pdf(data, photo)
    except Exception:  # noqa: BLE001
        pdf_bytes = None
    return docx_bytes, pdf_bytes