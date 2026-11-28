# -*- coding: utf-8 -*-
"""
Talaba Yordamchisi - Telegram bot (2-versiya).

Yangi imkoniyatlar:
  * AI orqali aniq, mavzuga oid matn (Gemini / OpenAI-mos)
  * Rejani bot o'zi tuzadi va tasdiqlashga beradi
  * Mavzuga mos rasmlarni topib, izoh bilan joylaydi
  * AI kaliti bo'lmasa - oflayn shablon rejimida ishlaydi

Ishga tushirish:  python bot.py
"""

import asyncio
import datetime
import io
import logging
import os
import re
import socket
import time

from telegram import (
    Document,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import ai_engine
import config
import i18n
import obyektivka
import photo3x4
import tools
import workflow
from ai_engine import (
    ai_available,
    ai_plan,
    last_error,
    provider_name,
    status_info,
    test_connection,
)
from content_engine import CHAPTERS_DEFAULT
from make_docx import create_document
from make_pptx import create_presentation
from storage import Storage
import batch_fast

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

storage = Storage(config.DB_PATH)

async def _safe_answer(query, text=""):
    try:
        await query.answer(text=text or None)
    except Exception:
        pass


_LOCK_SOCKET = None

VERSION = "v8.7"
MENU, TOPIC, FAN, SIZE, TITUL, INFO, PLAN, R_PHOTO, R_BG, R_DRESS, R_REF, FEEDBACK, \
    BOOK_ASK, BOOK_TEXT, SOLVE_SUB, SOLVE_TEXT, OCR_PHOTO, PDF_PHOTO, ZIP_FILES, OBY_ASK, OBY_WORK, OBY_REL, OBY_PHOTO = range(23)


def _admin_id():
    """Administrator ID: keys.txt dagi ADMIN_ID yoki birinchi /start qilgan egasi."""
    aid = int(getattr(config, "ADMIN_ID", 0) or 0)
    if aid:
        return aid
    try:
        val = storage.get_meta("admin_id", "")
        return int(val) if str(val).strip() else 0
    except Exception:  # noqa: BLE001
        return 0


def _claim_admin(user):
    """Agar admin hali belgilanmagan bo'lsa - shu foydalanuvchini admin qiladi."""
    if _admin_id():
        return False
    try:
        storage.set_meta("admin_id", str(user.id))
        return True
    except Exception:  # noqa: BLE001
        return False


async def _notify_admin(context, text):
    """Xabarni faqat administratorning shaxsiy chatiga yuboradi."""
    aid = _admin_id()
    if not aid:
        return
    try:
        await context.bot.send_message(
            chat_id=aid, text=text[:4000], parse_mode=ParseMode.HTML
        )
    except Exception:  # noqa: BLE001
        log.exception("Admin xabari yuborilmadi")


def _stats_text():
    s = storage.stats()
    lines = [
        "📊 <b>Bot statistikasi</b>",
        "",
        f"👥 Jami foydalanuvchilar: <b>{s['users']}</b>",
        f"🆕 Bugun qo'shilgan: <b>{s['new_today']}</b>",
        f"🔥 Bugun faol: <b>{s['active_today']}</b>",
        f"🕑 Oxirgi 24 soatda faol: <b>{s['active_24h']}</b>",
        f"📅 Oxirgi 7 kunda faol: <b>{s['active_week']}</b>",
        "",
        f"📄 Jami yaratilgan ishlar: <b>{s['works']}</b>",
        f"📆 Bugun yaratilgan: <b>{s['works_today']}</b>",
        f"🗓 7 kunda yaratilgan: <b>{s['works_week']}</b>",
    ]
    kinds = s.get("kinds") or []
    if kinds:
        lines += ["", "<b>Turlar bo'yicha:</b>"]
        for r in kinds[:6]:
            lines.append(f"• {KIND_TITLES.get(r['kind'], r['kind'])}: {r['c']}")
    top = s.get("top_users") or []
    if top:
        lines += ["", "<b>Eng faol foydalanuvchilar:</b>"]
        for r in top:
            name = r["full_name"] or (("@" + r["username"]) if r["username"] else "-")
            lines.append(f"• {name} — {r['works']} ish")
    lines += ["", f"🤖 AI: {provider_name()}"]
    return "\n".join(lines)


def _feedback_intro():
    return (
        "✍️ <b>Talab va takliflar</b>" + "\n" + "\n"
        + "Bot haqidagi fikringizni yozib yuboring — xatolik, g'oya yoki minnatdorchilik."
        + "\n"
        + "Xabar to'g'ridan-to'g'ri administratorning shaxsiy chatiga boradi, "
        + "boshqa foydalanuvchilar uni ko'rmaydi." + "\n" + "\n"
        + "Bekor qilish uchun /cancel"
    )


KIND_TITLES = {
    "prezentatsiya": "Prezentatsiya",
    "referat": "Referat",
    "mustaqil": "Mustaqil ish",
    "amaliy": "Amaliy hisobot",
    "tezis": "Tezis",
    "maqola": "Ilmiy maqola",
}

# Pastdagi doimiy tugmalar (matn -> amal)
BOTTOM_LABELS = {
    "📄 Referat": "referat",
    "📝 Mustaqil ish": "mustaqil",
    "📚 Amaliy hisobot": "amaliy",
    "📰 Tezis": "tezis",
    "📄 Ilmiy maqola": "maqola",
    "📊 Prezentatsiya": "prezentatsiya",
    "🧮 Misol yechish": "solve",
    "🖼 Rasmdan matn": "ocr",
    "🖼 Rasmdan PDF": "topdf",
    "🗜 Arxiv (ZIP)": "zip",
    "🌐 Til / Язык / Language": "lang",
    "✍️ Talab va takliflar": "feedback",
    "📁 Mening ishlarim": "my",
    "ℹ️ Yordam": "help",
    "📋 Obyektivka": "obyektivka",
    "🌐 Sayt": "site",
}


def bottom_menu():
    """Pastda doimiy turadigan tugmalar (BOTTOM_LABELS tartibida)."""
    labels = list(BOTTOM_LABELS.keys())
    rows = []
    for i in range(0, len(labels), 2):
        rows.append([KeyboardButton(lbl) for lbl in labels[i:i + 2]])
    return ReplyKeyboardMarkup(
        rows, resize_keyboard=True, is_persistent=True, input_field_placeholder="Mavzuni yozing..."
    )


SITE_URL = config.SITE_URL.rstrip("/")
SITE_IS_LOCAL = ("127.0.0.1" in SITE_URL) or ("localhost" in SITE_URL)


def _site_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("\U0001f310 Saytni ochish", url=SITE_URL)]]
    )


def site_text():
    out = (
        "\U0001f310 <b>Talaba yordamchisi \u2014 sayt</b>\n\n"
        "Botdagi xizmatlar saytda ham bor. Saytdan ham buyurtma berish mumkin.\n\n"
        "Manzil: <code>" + SITE_URL + "</code>"
    )
    if SITE_IS_LOCAL:
        out += (
            "\n\n<i>Eslatma: sayt hozir faqat shu kompyuterda ochiladi. "
            "Sayt internetga chiqarilgach, manzil avtomatik hammada ishlaydi.</i>"
        )
    return out


async def site_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        site_text(), reply_markup=_site_kb(), parse_mode=ParseMode.HTML
    )


KIND_HINTS = {
    "prezentatsiya": "Masalan: <i>Sun'iy intellekt va uning ta'limdagi o'rni</i>",
    "referat": "Masalan: <i>Yoshlar bandligini ta'minlashning iqtisodiy mexanizmlari</i>",
    "mustaqil": "Masalan: <i>Kichik biznesni rivojlantirish yo'llari</i>",
    "amaliy": "Masalan: <i>Korxonada buxgalteriya hisobini yuritish amaliyoti</i>",
    "tezis": "Masalan: <i>Raqamli iqtisodiyotda elektron to'lov tizimlari</i>",
    "maqola": "Masalan: <i>Ta'limda sun'iy intellekt texnologiyalarini qo'llash istiqbollari</i>",
}

HELLO = (
    "<b>Assalomu alaykum!</b> 👋\n\n"
    "Men talabalar uchun o'quv ishlarini tayyorlayman:\n\n"
    "📊 <b>Prezentatsiya</b> — tayyor .pptx slaydlar (har slaydda rasm)\n"
    "📄 <b>Referat</b> — reja, kirish, bo'limlar, xulosa bilan .docx\n"
    "📝 <b>Mustaqil ish</b> — titul varaq va mundarija bilan .docx\n"
    "📚 <b>Amaliy hisobot</b>, 📰 <b>Tezis</b>, 📄 <b>Ilmiy maqola</b> — .docx\n"
    "🧮 <b>Misol yechish</b> — matematika, fizika, kimyo va boshqa fanlar\n"
    "🖼 <b>Rasmdan matn</b>, 🖼 <b>Rasmdan PDF</b>, 🗜 <b>Arxiv (ZIP)</b>\n"
    "📋 <b>Obyektivka</b> — ma'lumotnoma (Word + PDF, 3x4 rasm bilan)\n\n"
    "Pastdagi tugmalardan birini bosib boshlang.\n"
    "\U0001f310 Hujjat tilini o'zgartirish: \"Til / Язык / Language\" tugmasi.\n\n"
    "Mavzuni yozasiz — men rejani tuzaman, matnni yozaman va "
    "mavzuga mos rasmlarni joylayman.\n\n"
    "Nimadan boshlaymiz?"
)


def main_menu(user_id=None):
    """Asosiy menyu (inline). Statistika tugmasi faqat admin uchun ko'rinadi."""
    rows = [
        [InlineKeyboardButton("📊 Prezentatsiya", callback_data="kind:prezentatsiya")],
        [InlineKeyboardButton("📄 Referat", callback_data="kind:referat")],
        [InlineKeyboardButton("📝 Mustaqil ish", callback_data="kind:mustaqil")],
        [InlineKeyboardButton("📚 Amaliy hisobot", callback_data="kind:amaliy")],
        [InlineKeyboardButton("📰 Tezis", callback_data="kind:tezis")],
        [InlineKeyboardButton("📄 Ilmiy maqola", callback_data="kind:maqola")],
        [
            InlineKeyboardButton("✍️ Talab va takliflar", callback_data="feedback"),
            InlineKeyboardButton("ℹ️ Yordam", callback_data="help"),
        ],
        [InlineKeyboardButton("🌐 Til / Язык / Language", callback_data="lang_menu")],
        [InlineKeyboardButton("📁 Mening ishlarim", callback_data="my")],
        [InlineKeyboardButton("🌐 Saytni ochish", url=SITE_URL)],
    ]
    if user_id and int(user_id) == _admin_id():
        rows.append([InlineKeyboardButton("📊 Statistika (admin)", callback_data="stats")])
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# 1. Boshlash
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = storage.add_user(user.id, user.username, user.full_name)
    storage.touch(user.id)
    claimed = _claim_admin(user)

    context.user_data.clear()
    await update.message.reply_text(
        HELLO, reply_markup=bottom_menu(), parse_mode=ParseMode.HTML
    )

    if claimed:
        await update.message.reply_text(
            "🔐 Siz <b>administrator</b> etib belgilandingiz.\n\n"
            "Statistika va takliflar faqat shu chatga keladi — boshqa "
            "foydalanuvchilar ko'rmaydi.\n"
            "Statistikani ko'rish: /stats",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(user.id),
        )
    elif is_new:
        st = storage.stats()
        uname = ("@" + user.username) if user.username else "username yo'q"
        await _notify_admin(
            context,
            "🆕 <b>Yangi foydalanuvchi</b>\n"
            + (user.full_name or "-") + " " + uname + "\n"
            + "ID: <code>" + str(user.id) + "</code>\n"
            + "Jami foydalanuvchilar: <b>" + str(st["users"]) + "</b>",
        )
    return MENU


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)

    if query.data == "help":
        mode = f"🤖 AI: <b>{provider_name()}</b>" if ai_available() else "📦 AI kaliti yo'q — oflayn rejim"
        await query.message.reply_text(
            "<b>Qanday ishlaydi?</b>\n\n"
            "1️⃣ Ish turini tanlaysiz\n"
            "2️⃣ Mavzuni yozasiz\n"
            "3️⃣ Fan nomini yozasiz\n"
            "4️⃣ Bet/slayd sonini o'zingiz yozasiz (5-30)\n"
            "5️⃣ Bot rejani taklif qiladi — tasdiqlaysiz (yoki o'zgartirasiz)\n\n"
            "Natijada rasmlar bilan tayyor <b>.pptx</b> yoki <b>.docx</b> fayl keladi.\n\n"
            f"{mode}\n"
            f"Kuniga bepul limit: <b>{config.DAILY_LIMIT} ta</b> ish.\n"
            "Bekor qilish uchun /cancel",
            reply_markup=main_menu(),
            parse_mode=ParseMode.HTML,
        )
        return MENU

    if query.data == "lang_menu":
        uid = update.effective_user.id
        await query.message.reply_text(
            _lang_text(storage.get_lang(uid)),
            reply_markup=_lang_keyboard(storage.get_lang(uid)),
            parse_mode=ParseMode.HTML,
        )
        return MENU

    if query.data == "feedback":
        await query.message.reply_text(
            _feedback_intro(),
            reply_markup=bottom_menu(),
            parse_mode=ParseMode.HTML,
        )
        return FEEDBACK

    if query.data == "stats":
        aid = _admin_id()
        if update.effective_user.id != aid:
            await query.message.reply_text("Bu bolim faqat administrator uchun.")
            return MENU
        await query.message.reply_text(
            _stats_text(), parse_mode=ParseMode.HTML, reply_markup=main_menu(update.effective_user.id)
        )
        return MENU

    if query.data == "my":
        rows = storage.user_works(update.effective_user.id)
        if not rows:
            text = "Siz hali ish yaratmagansiz."
        else:
            lines = ["<b>So'nggi ishlaringiz:</b>", ""]
            for r in rows:
                kind = KIND_TITLES.get(r["kind"], r["kind"])
                lines.append(f"• {kind} — {r['topic']} <i>({r['created_at'][:10]})</i>")
            text = "\n".join(lines)
        await query.message.reply_text(text, reply_markup=main_menu(), parse_mode=ParseMode.HTML)
        return MENU

    return MENU


# ---------------------------------------------------------------------------
# 2. Ish turi -> mavzu
# ---------------------------------------------------------------------------
async def choose_kind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)

    kind = query.data.split(":", 1)[1]
    context.user_data.clear()
    context.user_data["kind"] = kind

    await query.message.reply_text(
        _kind_prompt(kind), parse_mode=ParseMode.HTML
    )
    return TOPIC


def _kind_prompt(kind):
    return (
        f"<b>{KIND_TITLES.get(kind, kind)}</b> tanlandi.\n\n"
        f"Endi ish mavzusini yozing.\n{KIND_HINTS.get(kind, '')}\n\n"
        "Bekor qilish uchun /cancel"
    )


_BTN_FILTER = filters.Text(list(BOTTOM_LABELS.keys()))
_PHOTO_FILTER = filters.PHOTO | filters.Document.IMAGE


async def save_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Taklif/shikoyatni administratorning shaxsiy chatiga yuboradi."""
    text = (update.message.text or "").strip()
    if len(text) < 3:
        await update.message.reply_text("Iltimos, fikringizni to'liqroq yozing.")
        return FEEDBACK

    admin_id = _admin_id()
    if not admin_id:
        await update.message.reply_text(
            "✅ Fikringiz qabul qilindi, rahmat!\n"
            "<i>Eslatma: administrator ID si sozlanmagan (keys.txt dagi ADMIN_ID), "
            "shuning uchun xabar saqlanib qoldi, lekin yuborilmadi.</i>",
            reply_markup=bottom_menu(),
            parse_mode=ParseMode.HTML,
        )
        log.warning("ADMIN_ID sozlanmagan, feedback yuborilmadi: %s", text[:120])
        return MENU

    user = update.effective_user
    who = "@" + user.username if user.username else "(username yo'q)"
    body = (
        "💬 <b>Yangi talab / taklif</b>\n"
        "Kimdan: <b>" + (user.full_name or "-") + "</b> " + who + "\n"
        "ID: <code>" + str(user.id) + "</code>\n"
        "Sana: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + "\n\n"
        + text
    )
    try:
        await context.bot.send_message(chat_id=admin_id, text=body[:4000], parse_mode=ParseMode.HTML)
        reply = "✅ Fikringiz administratorga yuborildi. Rahmat!"
    except Exception:  # noqa: BLE001
        log.exception("Feedback yuborilmadi")
        reply = "Fikringiz saqlandi, lekin yuborishda xatolik bo'ldi. Keyinroq urinib ko'ring."

    await update.message.reply_text(reply, reply_markup=bottom_menu())
    return MENU


def _lang_keyboard(current="uz"):
    rows = []
    for code in i18n.LANGS:
        mark = "✅ " if code == current else ""
        rows.append(
            [
                InlineKeyboardButton(
                    mark + i18n.LANG_FLAGS[code] + " " + i18n.LANG_NAMES[code],
                    callback_data="lang:" + code,
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def _lang_text(current="uz"):
    return (
        "\U0001f310 <b>Til / Язык / Language</b>\n\n"
        "Hujjat va slaydlar qaysi tilda tayyorlanadi?\n"
        "На каком языке готовить документы?\n"
        "In which language should documents be prepared?\n\n"
        "Hozirgi til: <b>" + i18n.LANG_NAMES.get(i18n.norm(current), "O'zbekcha") + "</b>"
    )


async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    lang = i18n.norm(query.data.split(":", 1)[1])
    storage.set_lang(update.effective_user.id, lang)
    await query.message.edit_text(
        _lang_text(lang), reply_markup=_lang_keyboard(lang), parse_mode=ParseMode.HTML
    )
    thanks = {
        "uz": "Tayyor! Endi hujjatlar o'zbek tilida tayyorlanadi.",
        "ru": "Готово! Документы будут готовиться на русском языке.",
        "en": "Done! Documents will be prepared in English.",
    }
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=i18n.LANG_FLAGS[lang] + " " + thanks[lang],
    )


async def menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pastdagi doimiy tugmalar bosilganda ishlaydi."""
    text = (update.message.text or "").strip()
    action = BOTTOM_LABELS.get(text)
    if not action:
        return MENU

    if action == "solve":
        await update.message.reply_text(
            "🧮 <b>Misol / masala yechish</b>\n\nFanni tanlang:",
            reply_markup=_subject_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return SOLVE_SUB

    if action == "ocr":
        await update.message.reply_text(
            "🖼 <b>Rasmdan matn</b>\n\n"
            "Matn yozilgan rasmni (skan, kitob sahifasi, konspekt) yuboring — "
            "bot matnni ajratib, Word (.docx) fayl qilib beradi — ko'rinishi rasmdagidek bo'ladi.\n\nBekor qilish: /cancel",
            parse_mode=ParseMode.HTML,
        )
        return OCR_PHOTO

    if action == "topdf":
        context.user_data["pdf_imgs"] = []
        await update.message.reply_text(
            "🖼 <b>Rasmdan PDF</b>\n\n"
            "Rasmlarni yuboring (bir nechta bo'lsa — ketma-ket). "
            "Tugagach pastdagi «PDF yaratish» tugmasini bosing.",
            reply_markup=_pdf_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return PDF_PHOTO

    if action == "obyektivka":
        return await oby_start(update, context)

    if action == "zip":
        context.user_data["zip_files"] = []
        await update.message.reply_text(
            "🗜 <b>Arxiv (ZIP)</b>\n\n"
            "Fayllarni yuboring — bot ularni bitta ZIP qilib beradi. "
            "Yoki tayyor ZIP faylni yuboring — ichidagilarni ochib beradi.",
            reply_markup=_zip_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return ZIP_FILES

    if action == "lang":
        uid = update.effective_user.id
        await update.message.reply_text(
            _lang_text(storage.get_lang(uid)),
            reply_markup=_lang_keyboard(storage.get_lang(uid)),
            parse_mode=ParseMode.HTML,
        )
        return MENU

    if action == "feedback":
        await update.message.reply_text(
            _feedback_intro(),
            reply_markup=bottom_menu(),
            parse_mode=ParseMode.HTML,
        )
        return FEEDBACK

    if action == "help":
        mode = f"🤖 AI: <b>{provider_name()}</b>" if ai_available() else "📦 AI kaliti yo'q — oflayn rejim"
        await update.message.reply_text(
            "<b>Qanday ishlaydi?</b>\n\n"
            "1️⃣ Pastdagi tugmadan ish turini tanlaysiz\n"
            "2️⃣ Mavzuni yozasiz\n"
            "3️⃣ Fan nomini yozasiz\n"
            "4️⃣ Bet/slayd sonini o'zingiz yozasiz (5-30)\n"
            "5️⃣ Titul varaq kerakmi — tanlaysiz\n"
            "6️⃣ Rejani tasdiqlaysiz\n\n"
            "Natijada rasmlar bilan tayyor <b>.docx</b> yoki <b>.pptx</b> fayl keladi.\n\n"
            f"{mode}\n"
            f"Kuniga limit: <b>{config.DAILY_LIMIT} ta</b> ish.\n"
            "Bekor qilish uchun /cancel",
            reply_markup=bottom_menu(),
            parse_mode=ParseMode.HTML,
        )
        return MENU

    if action == "site":
        await update.message.reply_text(
            site_text(), reply_markup=_site_kb(), parse_mode=ParseMode.HTML
        )
        return MENU

    if action == "my":
        rows = storage.user_works(update.effective_user.id)
        if not rows:
            text_out = "Siz hali ish yaratmagansiz."
        else:
            lines = ["<b>So'nggi ishlaringiz:</b>", ""]
            for r in rows:
                lines.append(
                    f"• {KIND_TITLES.get(r['kind'], r['kind'])} — {r['topic']} "
                    f"<i>({r['created_at'][:10]})</i>"
                )
            text_out = "\n".join(lines)
        await update.message.reply_text(
            text_out, reply_markup=bottom_menu(), parse_mode=ParseMode.HTML
        )
        return MENU

    context.user_data.clear()
    context.user_data["kind"] = action
    await update.message.reply_text(
        _kind_prompt(action), reply_markup=bottom_menu(), parse_mode=ParseMode.HTML
    )
    return TOPIC


async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = (update.message.text or "").strip()
    if len(topic) < 5:
        await update.message.reply_text(
            "Mavzu juda qisqa. Iltimos, mavzuni to'liqroq yozing (kamida 5 belgi)."
        )
        return TOPIC
    if len(topic) > 200:
        await update.message.reply_text("Mavzu juda uzun. 200 belgidan oshmasin.")
        return TOPIC

    if topic.strip().lower() in ("mustaqil ish", "referat", "prezentatsiya", "amaliy hisobot", "tezis", "ilmiy maqola"):
        await update.message.reply_text("Bu ish turi nomi, mavzu emas. Mavzuni yozing, masalan: Vagonlar tuzilishi", parse_mode=ParseMode.HTML)
        return TOPIC
    context.user_data["topic"] = topic
    kind = context.user_data.get("kind", "referat")

    if kind in ("referat", "mustaqil", "prezentatsiya"):
        await update.message.reply_text(
            "Mavzu qabul qilindi ✅\n\n"
            "<b>Manba (kitob, maqola, konspekt) bormi?</b>\n\n"
            "📚 Bo'lsa — matnini yoki .docx/.txt faylini yuborasiz, "
            "bot asosiy mazmunni shundan oladi.\n"
            "🤖 Bo'lmasa — AI o'zi yozadi.",
            reply_markup=_book_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return BOOK_ASK

    await _ask_fan(update.message)
    return FAN


async def get_fan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text and not text.startswith("/"):
        context.user_data["fan"] = text[:120]
        await update.message.reply_text(
            "Fan: <b>" + context.user_data["fan"] + "</b> ✅", parse_mode=ParseMode.HTML
        )
    return await _ask_pages(update.message, context)


async def skip_fan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("fan", None)
    return await _ask_pages(update.message, context)


async def _ask_pages(message, context):
    """Bet/slayd sonini foydalanuvchi o'zi yozadi (5-30)."""
    unit = "slayd" if context.user_data.get("kind") == "prezentatsiya" else "bet"
    await message.reply_text(
        "<b>Nechi " + unit + " kerak?</b>\n\n"
        "5 dan 30 gacha raqam yozing (masalan: <code>12</code> yoki <code>30</code>).\n"
        "Tugma yo'q — faqat o'zingiz xohlagan sonni yozasiz.",
        parse_mode=ParseMode.HTML,
    )
    return SIZE


# ---------------------------------------------------------------------------
# 3. Ma'lumotlarni o'qish
# ---------------------------------------------------------------------------
LABELS = {
    "fish": [
        "f.i.sh", "f.i.o", "f i sh", "fish", "fio", "ism familiya",
        "ism-familiya", "bajaruvchi", "talaba", "muallif",
    ],
    "guruh": ["guruh", "guruh raqami", "guruh nomi"],
    "fan": ["fan", "fan nomi"],
    "oqituvchi": ["oqituvchi", "o'qituvchi", "tekshiruvchi", "rahbar", "murabbiy"],
    "muassasa": ["muassasa", "otm", "universitet", "institut", "kollej", "texnikum"],
    "shahar": ["shahar", "shahar nomi"],
    "yil": ["yil"],
    "taklif": ["taklif", "taklif va tavsiyalar", "tavsiya", "shikoyat"],
}


def _norm_key(text):
    text = text.lower().replace("‘", "'").replace("’", "'")
    text = re.sub(r"[^a-zа-я' ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_info(text):
    info = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
        elif "-" in line and line.count("-") == 1:
            key, value = line.split("-", 1)
        else:
            continue
        key_n = _norm_key(key)
        value = value.strip()
        if not value:
            continue
        for field, variants in LABELS.items():
            if any(_norm_key(v) in key_n or v in key_n for v in variants):
                info[field] = value
                break
    return info


def _photo_dir():
    path = os.path.join(config.DATA_DIR, "photos")
    os.makedirs(path, exist_ok=True)
    return path


def _photo_path(user_id):
    return os.path.join(_photo_dir(), f"{user_id}.jpg")


def _save_photo(user_id, raw):
    """Rasmni 3:4 nisbatga keltirib saqlaydi (titul varaq uchun)."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        target = 3 / 4  # eni / bo'yi
        if w / h > target:
            new_w = int(h * target)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        img = img.resize((600, 800), Image.LANCZOS)
        path = _photo_path(user_id)
        img.save(path, "JPEG", quality=92, optimize=True)
        return path
    except Exception:  # noqa: BLE001
        log.exception("Rasmni saqlashda xatolik")
        return None


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """3x4 rasm qabul qilish (istalgan qadamda)."""
    if not context.user_data.get("topic"):
        await update.message.reply_text(
            "Avval ish mavzusini yozing, keyin rasm yuborishingiz mumkin.",
            reply_markup=bottom_menu(),
        )
        return TOPIC

    photos = update.message.photo or []
    file_id = None
    if photos:
        file_id = photos[-1].file_id
    else:
        doc = update.message.document
        if doc is not None and (doc.mime_type or "").startswith("image/"):
            file_id = doc.file_id
    if not file_id:
        return None
    try:
        tg_file = await context.bot.get_file(file_id)
        raw = bytes(await tg_file.download_as_bytearray())
    except Exception:  # noqa: BLE001
        log.exception("Rasmni yuklab olishda xatolik")
        await update.message.reply_text(
            "Rasmni yuklab bo'lmadi. Qayta yuborib ko'ring yoki rasmni tashlab ketsangiz ham bo'ladi."
        )
        return INFO

    path = await asyncio.to_thread(_save_photo, update.effective_user.id, raw)
    if not path:
        await update.message.reply_text("Rasm formati mos kelmadi. Boshqa rasm yuboring.")
        return INFO

    info = context.user_data.get("info") or {}
    info["photo"] = path
    context.user_data["info"] = info
    await update.message.reply_text(
        "✅ Rasm qabul qilindi (3x4 qilib kesildi). Titul varaqqa o'ng tomondan qo'yiladi.",
        parse_mode=ParseMode.HTML,
    )
    if context.user_data.get("size"):
        return await _make_plan_step(update.message, context)
    return await _ask_pages(update.message, context)


# ---------------------------------------------------------------------------
# 3x4 rasmiy rasm tayyorlash
# ---------------------------------------------------------------------------
def _bg_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬜ Oq fon", callback_data="bg:oq")],
            [InlineKeyboardButton("🟦 Ko'k fon", callback_data="bg:kok")],
            [InlineKeyboardButton("⬛ Kulrang fon", callback_data="bg:kulrang")],
        ]
    )


def _dress_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🤵 Kostyum + galstuk", callback_data="dress:kostyum")],
            [InlineKeyboardButton("👔 Oq ko'ylak", callback_data="dress:koylak")],
            [InlineKeyboardButton("🥼 Oq xalat", callback_data="dress:xalat")],
        ]
    )


def _ref_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📷 Kiyim rasmini yuboraman", callback_data="ref:yes")],
            [InlineKeyboardButton("⏭ Yo'q, davom etish", callback_data="ref:no")],
        ]
    )


def _r_intro():
    return (
        "🪪 <b>3x4 rasmiy rasm tayyorlash</b>\n\n"
        "Yaxshi sifatli, yuzingiz to'liq ko'ringan rasm yuboring "
        "(selfie yoki portret, yorug' joyda, ko'zoynaksiz).\n\n"
        "Bot: fonni almashtiradi, kiyimni kostyumga o'giradi, yuzni saqlab qoladi "
        "va 3x4 (35x45 mm) rasmiy rasm qilib beradi.\n\n"
        "Bekor qilish: /cancel"
    )


async def r_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not photo3x4.available():
        await update.message.reply_text(
            "Rasm tayyorlash uchun AI kaliti topilmadi (keys.txt).",
            reply_markup=bottom_menu(),
        )
        return MENU

    photos = update.message.photo or []
    file_id = photos[-1].file_id if photos else None
    if not file_id:
        doc = update.message.document
        if doc is not None and (doc.mime_type or "").startswith("image/"):
            file_id = doc.file_id
    if not file_id:
        await update.message.reply_text("Rasm (jpg yoki png) yuboring.")
        return R_PHOTO

    try:
        tg_file = await context.bot.get_file(file_id)
        raw = bytes(await tg_file.download_as_bytearray())
    except Exception:  # noqa: BLE001
        log.exception("3x4 rasmni yuklab olishda xatolik")
        await update.message.reply_text("Rasmni yuklab bo'lmadi. Qayta yuborib ko'ring.")
        return R_PHOTO

    context.user_data["r_raw"] = raw
    context.user_data.pop("r_ref", None)
    await update.message.reply_text(
        "✅ Rasm qabul qilindi.\n\n<b>Fon rangini tanlang:</b>",
        reply_markup=_bg_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return R_BG


async def r_bg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    context.user_data["r_bg"] = query.data.split(":", 1)[1]
    await query.message.edit_text(
        "🎨 Fon tanlandi.\n\n<b>Qanday kiyimda bo'lsin?</b>",
        reply_markup=_dress_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return R_DRESS


async def r_dress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    context.user_data["r_dress"] = query.data.split(":", 1)[1]
    if not context.user_data.get("r_raw"):
        await query.message.edit_text("Rasm yo'qolib qoldi. Pastdagi tugmadan qayta boshlang.")
        return MENU

    await query.message.edit_text(
        "👔 <b>Kiyim rasmi bormi?</b>\n\n"
        "Tayyor kostyum yoki ko'ylak rasmi bo'lsa yuboring - AI shu kiyimni qo'yadi "
        "(foni shaffof yoki oq bo'lsa yaxshi).\n\n"
        "Bo'lmasa <b>\"Yo'q\"</b> tugmasini bosing.",
        reply_markup=_ref_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return R_REF


async def r_ref_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiyim rasmini yuborishni tanlash."""
    query = update.callback_query
    await _safe_answer(query)
    if query.data == "ref:yes":
        await query.message.edit_text(
            "📷 Kiyim (kostyum/ko'ylak) rasmini yuboring.\nBekor qilish: /cancel"
        )
        return R_REF
    return await _r_make(update, context, query.message)


async def r_ref_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiyim namunasini qabul qilib, rasmni tayyorlashga o'tadi."""
    photos = update.message.photo or []
    file_id = photos[-1].file_id if photos else None
    if not file_id:
        doc = update.message.document
        if doc is not None and (doc.mime_type or "").startswith("image/"):
            file_id = doc.file_id
    if not file_id:
        await update.message.reply_text("Kiyim rasmini (jpg yoki png) yuboring.")
        return R_REF
    try:
        tg_file = await context.bot.get_file(file_id)
        context.user_data["r_ref"] = bytes(await tg_file.download_as_bytearray())
    except Exception:  # noqa: BLE001
        log.exception("Kiyim rasmini yuklab olishda xatolik")
        await update.message.reply_text("Rasmni yuklab bo'lmadi. Qayta yuboring.")
        return R_REF
    return await _r_make(update, context, update.message)


async def _say(message, text, **kwargs):
    """Xabarni tahrirlash imkoni bo'lsa tahrirlaydi, bo'lmasa yangi xabar yuboradi."""
    try:
        return await message.edit_text(text, **kwargs)
    except Exception:  # noqa: BLE001  (oddiy xabar -> tahrirlab bo'lmaydi)
        try:
            return await message.reply_text(text, **kwargs)
        except Exception:  # noqa: BLE001
            return None


async def _r_make(update: Update, context: ContextTypes.DEFAULT_TYPE, message):
    """3x4 rasmni tayyorlab yuboradi."""
    raw = context.user_data.get("r_raw")
    if not raw:
        await message.reply_text("Rasm yo'qolib qoldi. Pastdagi tugmadan qayta boshlang.")
        return MENU

    bg = context.user_data.get("r_bg", "oq")
    dress = context.user_data.get("r_dress", "kostyum")
    ref = context.user_data.get("r_ref")
    await message.reply_text(
        "⏳ Rasm tayyorlanmoqda...\n<i>20-40 soniya kutib turing.</i>",
        parse_mode=ParseMode.HTML,
    )
    try:
        out, photo_note = await asyncio.wait_for(
            asyncio.to_thread(photo3x4.make_ex, raw, bg, dress, ref), timeout=175
        )
    except asyncio.TimeoutError:
        await _say(message, "⏳ Vaqt tugadi. Pastdagi tugmadan qayta urinib ko'ring.")
        return MENU
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        low = err.lower()
        if "402" in low or "insufficient" in low or "balance" in low or "quota" in low:
            msg_txt = (
                "⚠️ AI hisob balansi yetarli emas.\n"
                "<i>Rasm yaratish pullik modelda ishlaydi.</i>\n\n"
                "Kalit egasi hisobni $1–2 ga to'ldirsa, rasm shu zahoti ishlaydi."
            )
        elif "413" in low or "too large" in low:
            msg_txt = "⚠️ Rasm hajmi juda katta. Kichikroq (2 MB gacha) rasm yuboring."
        elif "timeout" in low or "timed out" in low:
            msg_txt = "⏳ AI javob bermadi. Bir daqiqadan so'ng qayta urinib ko'ring."
        else:
            msg_txt = "❌ Rasmni tayyorlab bo'lmadi.\n<code>" + err[:160] + "</code>"
        await _say(message, 
            msg_txt + "\n\nQayta urinish: pastdagi tugma", parse_mode=ParseMode.HTML
        )
        return MENU

    try:
        with open(_photo_path(update.effective_user.id), "wb") as f:
            f.write(out)
    except OSError:
        log.exception("3x4 rasmni saqlashda xatolik")

    await _say(message, "✅ Tayyor!")
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=out,
            caption=(
                "🪪 3x4 (35x45 mm) rasmiy rasm\n"
                "Keyingi hujjatlarda titul varaqqa avtomatik qo'yiladi."
                + (("\n\nℹ️ " + photo_note) if photo_note else "")
            ),
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=InputFile(io.BytesIO(out), filename="3x4_rasm.jpg"),
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        sheet = await asyncio.to_thread(photo3x4.make_sheet, out)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=InputFile(io.BytesIO(sheet), filename="3x4_8ta_varaq.jpg"),
            caption=(
                "🖨 <b>Chop etish uchun varaq</b>\n"
                "8 ta bir xil 3x4 rasm, 10x15 sm qog'oz, 300 dpi.\n"
                "Qora hoshiyalar bo'ylab qirqib olasiz."
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception:  # noqa: BLE001
        log.exception("8 talik varaq tayyorlanmadi")

    for key in ("r_raw", "r_ref", "r_bg", "r_dress"):
        context.user_data.pop(key, None)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Yana kerakmi? Pastdagi tugmalardan tanlang.",
        reply_markup=bottom_menu(),
    )
    return MENU


async def rasm_ochir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saqlangan 3x4 rasmni o'chiradi (titul varaqqa qo'yilmasin)."""
    path = _photo_path(update.effective_user.id)
    if os.path.exists(path):
        try:
            os.remove(path)
            text = "🗑 3x4 rasm o'chirildi. Endi titul varaqqa qo'yilmaydi."
        except OSError:
            text = "Rasmni o'chirib bo'lmadi."
    else:
        text = "Saqlangan 3x4 rasm topilmadi."
    await update.message.reply_text(text, reply_markup=bottom_menu())
    return MENU


def _titul_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Titul varaq bilan", callback_data="titul:ha")],
            [InlineKeyboardButton("⬜ Titul varaqsiz (faqat matn)", callback_data="titul:yoq")],
        ]
    )


async def get_pages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi o'zi yozgan bet/slayd sonini qabul qiladi (5-30)."""
    text = (update.message.text or "").strip()
    m = re.search("[0-9]+", text)
    if not m:
        await update.message.reply_text("Faqat raqam yozing, masalan: 12")
        return SIZE
    size = int(m.group())
    if not (5 <= size <= 30):
        await update.message.reply_text("Hajm 5 dan 30 gacha bo'lishi kerak. Qayta yozing:")
        return SIZE
    context.user_data["size"] = size
    await update.message.reply_text(
        "Hajm: <b>" + str(size) + "</b> ✅\n\n<b>Titul varaq kerakmi?</b>\n"
        "Titul varaq — muassasa, F.I.Sh va guruh yoziladigan birinchi sahifa.\n"
        "Kerak bo'lmasa — to'g'ridan-to'g'ri matn boshlanadi.",
        reply_markup=_titul_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return TITUL


async def titul_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    choice = query.data.split(":", 1)[1]
    fan = context.user_data.get("fan", "")

    if choice == "ha":
        await query.message.edit_text(
            "<b>Titul varaq uchun ma'lumotlarni yuboring.</b>\n"
            "Har biri yangi qatorda (keraksizini tashlab ketsangiz ham bo'ladi):\n\n"
            "<code>F.I.Sh: Karimov Ali\n"
            "Guruh: 21-01\n"
            "O'qituvchi: Rahimov B.\n"
            "Muassasa: Toshkent davlat texnika universiteti\n"
            "Shahar: Toshkent\n"
            "Yil: 2026</code>\n\n"
            "📷 Xohlasangiz, 3x4 rasmingizni ham yuboring.",
            parse_mode=ParseMode.HTML,
        )
        return INFO

    info = {"no_title": True}
    if fan:
        info["fan"] = fan
    context.user_data["info"] = info
    return await _make_plan_step(query.message, context)


async def get_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    info = parse_info(text)

    if not info:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        order = ["fish", "guruh", "fan", "oqituvchi", "muassasa", "shahar", "yil"]
        for i, line in enumerate(lines[: len(order)]):
            info[order[i]] = line

    # Fan: avval yozilgan fan nomi, bo'lmasa shu yerda yozilgani
    fan = context.user_data.get("fan") or info.get("fan")
    if fan:
        info["fan"] = fan
        context.user_data["fan"] = fan

    if not info.get("taklif"):
        for line in text.splitlines():
            low = line.strip().lower()
            if low.startswith("taklif") and ":" in low:
                info["taklif"] = line.split(":", 1)[1].strip()[:600]
                break

    photo = context.user_data.get("info", {}).get("photo") or _photo_path(update.effective_user.id)
    if photo and os.path.exists(photo):
        info["photo"] = photo
    context.user_data["info"] = info

    return await _make_plan_step(update.message, context)


# ---------------------------------------------------------------------------
# 4. Hajm -> reja taklifi
# ---------------------------------------------------------------------------
def _offline_plan():
    return [c for c, _ in CHAPTERS_DEFAULT]


def _subject_keyboard():
    subjects = [
        ("➕ Matematika", "math"), ("⚛️ Fizika", "fizika"),
        ("🧪 Kimyo", "kimyo"), ("🧬 Biologiya", "bio"),
        ("📐 Geometriya", "geom"), ("💻 Informatika", "it"),
        ("📈 Iqtisodiyot", "econ"), ("🇬🇧 Ingliz tili", "eng"),
    ]
    rows = []
    for i in range(0, len(subjects), 2):
        rows.append([
            InlineKeyboardButton(lbl, callback_data="subj:" + code)
            for lbl, code in subjects[i:i + 2]
        ])
    return InlineKeyboardMarkup(rows)


def _pdf_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📄 PDF yaratish", callback_data="pdf:go")]]
    )


_OBY_TEXT_FILTER = filters.TEXT & ~filters.COMMAND

# Obyektivka qadamlari: (kalit, savol, namuna, majburiy)
OBY_STEPS = [
    ("F.I.SH", "Familiya, ism, otasining ismi", "Masalan: Jorayev Navro'zbek Ikromovich", True),
    ("Tug'ilgan yili", "Tug'ilgan yili", "Kun.oy.yil ko'rinishida. Masalan: 20.03.2007", True),
    ("Tug'ilgan joyi", "Tug'ilgan joyi", "Masalan: Buxoro viloyati Olot tumani", True),
    ("Millati", "Millati", "Masalan: o'zbek", True),
    ("Ma'lumoti", "Ma'lumoti", "Oliy / O'rta maxsus / O'rta", True),
    ("Partiyaviyligi", "Partiyaviyligi", "A'zo bo'lmasa: -", False),
    ("Tamomlagan", "Tamomlagan (o'qish joyi va yili)", "Masalan: 2025-yil 26-maktab (11-sinf)", False),
    ("Mutaxassisligi", "Ma'lumoti bo'yicha mutaxassisligi", "Bilmasangiz: -", False),
    ("Ilmiy darajasi", "Ilmiy darajasi", "Bo'lmasa: yo'q", False),
    ("Ilmiy unvoni", "Ilmiy unvoni", "Bo'lmasa: yo'q", False),
    ("Chet tillari", "Qaysi chet tillarini biladi", "Masalan: ingliz, rus", False),
    ("Mukofot", "Davlat mukofoti bilan taqdirlanganmi", "Bo'lmasa: yo'q", False),
    ("Deputat", "Kengash deputatimi yoki boshqa saylanadigan organ a'zosimi", "Bo'lmasa: yo'q", False),
    ("Sana", "Joriy lavozim sanasi", "Masalan: 2026-yil 7-sentabrdan", True),
    ("Lavozim", "Joriy lavozim (to'liq)",
     "O'qish joyi bo'lsa: universitet + yo'nalish.\nMasalan: Toshkent davlat transport "
     "universiteti yurispridensiya yo'nalishi talabasi", True),
]

_OBY_TOTAL = len(OBY_STEPS) + 2

_OBY_ROLES = [
    "Otasi", "Onasi", "Akasi", "Ukasi", "Opasi", "Singlisi",
    "Turmush o'rtog'i", "O'g'li", "Qizi", "Qaynotasi", "Qaynonasi", "Tog'asi",
    "Amakisi", "Xolasi", "Ammasi", "Buvisi", "Buvasi",
]


def _oby_new():
    return {"lines": [], "mehnat": [], "qarindosh": [], "idx": 0, "rel": ""}


def _oby_state(context):
    st = context.user_data.get("oby")
    if not isinstance(st, dict):
        st = _oby_new()
        context.user_data["oby"] = st
    return st


def _oby_done_kb(action, label):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=action)]])


def _oby_role_kb(extra="⏭ Qarindoshlarni tugatish"):
    rows, row = [], []
    for r in _OBY_ROLES:
        row.append(InlineKeyboardButton(r, callback_data="obyrole:" + r))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(extra, callback_data="oby:reldone")])
    return InlineKeyboardMarkup(rows)


async def oby_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📋 Obyektivka — har bir maydonni bitta-bitta so'raydi."""
    context.user_data["oby"] = _oby_new()
    await update.message.reply_text(
        "📋 <b>Obyektivka (ma'lumotnoma)</b>\n\n"
        "Ma'lumotlarni bitta-bitta so'rayman. Har savolga javob yozib yuboring.\n"
        "Majburiy bo'lmagan savolni <b>/skip</b> bilan o'tkazib yuborsangiz, "
        "o'sha joyga «-» qo'yiladi.\n\n"
        "Bekor qilish: /cancel",
        parse_mode=ParseMode.HTML,
    )
    return await _oby_ask_step(update.message, context)


async def _oby_ask_step(message, context):
    st = _oby_state(context)
    i = st["idx"]
    if i >= len(OBY_STEPS):
        return await _oby_ask_work(message, context)
    _key, title, hint, req = OBY_STEPS[i]
    txt = ("<b>" + str(i + 1) + "/" + str(_OBY_TOTAL) + " — " + title + "</b>\n\n" + hint)
    txt += "\n\nO'tkazib yuborish: /skip" if not req else ""
    await message.reply_text(txt, parse_mode=ParseMode.HTML)
    return OBY_ASK


async def oby_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _oby_state(context)
    i = st["idx"]
    if i >= len(OBY_STEPS):
        return await _oby_ask_work(update.message, context)
    key, _title, _hint, req = OBY_STEPS[i]
    val = (update.message.text or "").strip()
    if not val:
        await update.message.reply_text("❗️ Bo'sh bo'lmasin. Javobni yozing.")
        return OBY_ASK
    st["lines"].append(key + ": " + val)
    st["idx"] = i + 1
    return await _oby_ask_step(update.message, context)


async def oby_skip_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _oby_state(context)
    i = st["idx"]
    if i >= len(OBY_STEPS):
        return await oby_work_done(update, context)
    key, _title, _hint, req = OBY_STEPS[i]
    if req:
        await update.message.reply_text("❗️ Bu maydon majburiy — javob yozing.")
        return OBY_ASK
    st["lines"].append(key + ": -")
    st["idx"] = i + 1
    return await _oby_ask_step(update.message, context)


async def _oby_ask_work(message, context):
    st = _oby_state(context)
    n = len(st["mehnat"]) + 1
    await message.reply_text(
        "<b>" + str(len(OBY_STEPS) + 1) + "/" + str(_OBY_TOTAL) + " — MEHNAT FAOLIYATI</b>\n\n"
        + str(n) + "-qator: yillari va ish joyi\n"
        "<code>2013-2024 | Olot tumani 26-maktab o'quvchisi</code>\n"
        "Hozir ishlayotgan bo'lsa: <code>2026-now | universitet talabasi</code>\n\n"
        "Tugatish: pastdagi tugma yoki /skip",
        reply_markup=_oby_done_kb("oby:workdone", "⏭ Mehnatni tugatish"),
        parse_mode=ParseMode.HTML,
    )
    return OBY_WORK


async def oby_work_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _oby_state(context)
    val = (update.message.text or "").strip()
    parts = [p.strip() for p in val.split("|")]
    davr = parts[0] if parts else ""
    ish = " | ".join(parts[1:]) if len(parts) > 1 else ""
    if not ish:
        await update.message.reply_text(
            "❗️ Ko'rinishi: <code>yillari | ish joyi</code>\n"
            "Masalan: <code>2026-now | Toshkent davlat transport universiteti talabasi</code>",
            parse_mode=ParseMode.HTML,
        )
        return OBY_WORK
    st["mehnat"].append({"davr": davr, "ish": ish})
    return await _oby_ask_work(update.message, context)


async def oby_work_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message if getattr(update, "message", None) else update.callback_query.message
    if getattr(update, "callback_query", None):
        await update.callback_query.answer()
    st = _oby_state(context)
    await msg.reply_text(
        "<b>" + str(len(OBY_STEPS) + 2) + "/" + str(_OBY_TOTAL) + " — QARINDOSHLAR</b>\n\n"
        "Qarindosh turini tanlang (yoki tugatish):"
        + ("\n\nKiritilgan: " + str(len(st["qarindosh"])) + " ta" if st["qarindosh"] else ""),
        reply_markup=_oby_role_kb(),
        parse_mode=ParseMode.HTML,
    )
    return OBY_REL


async def oby_rel_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    role = (query.data or "").split(":", 1)[-1]
    st = _oby_state(context)
    st["rel"] = role
    await query.message.edit_text(
        "<b>" + role + "</b> ma'lumotini yozing:\n\n"
        "<code>F.I.SH | tug'ilgan yili va joyi | ish joyi | turar joyi</code>\n\n"
        "Masalan: <code>Bozorov Ikrom Jo'rayevich | 1983-yil 12-aprel, Buxoro viloyati "
        "Olot tumani | Usta | Buxoro viloyati Olot tumani</code>\n\n"
        "Vafot etgan bo'lsa: <code>F.I.SH | yili va joyi | vafot 2019 | sobiq ishi</code>",
        parse_mode=ParseMode.HTML,
    )
    return OBY_REL


async def oby_rel_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _oby_state(context)
    role = st.get("rel") or ""
    if not role:
        return await oby_work_done(update, context)
    val = (update.message.text or "").strip()
    if len(val) < 3:
        await update.message.reply_text("❗️ Ma'lumot qisqa. Qayta yozing.")
        return OBY_REL
    st["qarindosh"].append(role + ": " + val)
    st["rel"] = ""
    await update.message.reply_text(
        "✅ Qo'shildi. Yana qarindosh qo'shamizmi?",
        reply_markup=_oby_role_kb("✅ Yetarli — rasmga o'tish"),
    )
    return OBY_REL


async def oby_rel_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    await query.message.edit_text(
        "<b>Yakuniy qadam — 3x4 rasm</b>\n\n"
        "Rasmni yuboring (jpg / png). Rasm kerak bo'lmasa — pastdagi tugmani bosing, "
        "o'sha joyga bo'sh ramka qoladi.",
        reply_markup=_oby_done_kb("oby:nophoto", "⏭ Rasmsiz davom etish"),
        parse_mode=ParseMode.HTML,
    )
    return OBY_PHOTO


async def oby_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("oby"):
        await update.message.reply_text(
            "Avval 📋 Obyektivka tugmasini bosing."
        )
        return MENU
    try:
        _name, raw = await _download(update, context)
    except Exception:  # noqa: BLE001
        await update.message.reply_text(
            "Rasmni yuklab bo'lmadi. Qayta yuboring yoki «Rasmsiz davom etish»ni bosing."
        )
        return OBY_PHOTO
    return await _oby_build(update.message, context, raw)


async def oby_nophoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    return await _oby_build(query.message, context, None)


async def _oby_build(message, context, photo):
    """Word + PDF tayyorlab yuboradi."""
    st = context.user_data.pop("oby", None) or _oby_new()
    status = await message.reply_text("📋 Obyektivka tayyorlanmoqda...")
    text = "\n".join(
        list(st["lines"])
        + ["Mehnat: " + w.get("davr", "") + " | " + w.get("ish", "") for w in st["mehnat"]]
        + list(st["qarindosh"])
    )
    data = obyektivka.parse(text)
    try:
        docx_bytes, pdf_bytes = await asyncio.to_thread(
            obyektivka.build_all, data, photo
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Obyektivka xatosi: %s", exc)
        await status.edit_text(
            "❌ Fayl yasab bo'lmadi: " + str(exc)[:120] + "\n\n"
            "python-docx o'rnatilganini tekshiring (1_BOSHLASH.bat)."
        )
        return MENU

    safe = re.sub(r"[^A-Za-z0-9_'-]+", "_", data.get("fio") or "")[:40].strip("_")
    safe = safe or "obyektivka"
    try:
        await message.reply_document(
            document=io.BytesIO(docx_bytes),
            filename="Obyektivka_" + safe + ".docx",
            caption="📋 Obyektivka (Word — tahrirlash uchun)",
        )
        if pdf_bytes:
            await message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename="Obyektivka_" + safe + ".pdf",
                caption="📄 Obyektivka (PDF — chop etish uchun)",
            )
        else:
            await message.reply_text(
                "ℹ️ PDF qismi o'rnatilmagan. Bir marta <b>10_OBYEKTIVKA_ORNATISH.bat</b> "
                "faylini bosing, keyin PDF ham chiqadi. Hozir Word fayli yuborildi.",
                parse_mode=ParseMode.HTML,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Obyektivka yuborish xatosi: %s", exc)
        await status.edit_text("❌ Faylni yuborib bo'lmadi. /start bilan qayta urinib ko'ring.")
        return MENU

    await status.edit_text(
        "✅ Obyektivka tayyor!\n\n"
        "Word faylni ochib tahrirlashingiz, PDF ni esa shundayligicha chop etishingiz mumkin.\n"
        "Yana kerakmi? Pastdagi tugmalardan tanlang.",
        reply_markup=bottom_menu(),
    )
    return MENU


def _zip_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🗜 ZIP yaratish", callback_data="zip:go")]]
    )


def _book_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📚 Manba (kitob) yuboraman", callback_data="book:yes")],
            [InlineKeyboardButton("🤖 AI o'zi yozsin", callback_data="book:no")],
        ]
    )


async def _ask_fan(message):
    await message.reply_text(
        "<b>Fan nomini yozing.</b>\n"
        "Masalan: <i>Axborot texnologiyalari</i>\n\n"
        "Fan titul varaqda va ishlarning sarlavhasida ishlatiladi.\n"
        "Kerak bo'lmasa /skip yozing.",
        parse_mode=ParseMode.HTML,
    )


def _img_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1", callback_data="img:1"),
                InlineKeyboardButton("2", callback_data="img:2"),
                InlineKeyboardButton("3", callback_data="img:3"),
            ],
            [
                InlineKeyboardButton("4", callback_data="img:4"),
                InlineKeyboardButton("5", callback_data="img:5"),
                InlineKeyboardButton("6", callback_data="img:6"),
            ],
            [InlineKeyboardButton("⬜ Rasmsiz", callback_data="img:0")],
        ]
    )


def _make_plan_sync(topic, kind, size):
    if ai_available():
        try:
            return ai_plan(topic, kind, size), True
        except Exception as exc:  # noqa: BLE001
            log.warning("Reja AI orqali tuzilmadi: %s", exc)
    return _offline_plan(), False


async def _make_plan_step(message, context):
    """Hajm tanlangandan keyin reja tuzib, tasdiqlashga beradi."""
    kind = context.user_data.get("kind", "referat")
    topic = context.user_data.get("topic", "")
    size = int(context.user_data.get("size") or 10)

    status = await message.reply_text(
        "🧠 Reja tuzilmoqda, bir oz kuting...\n"
        "<i>AI javob bermasa, standart reja avtomatik qo'llanadi.</i>",
        parse_mode=ParseMode.HTML,
    )
    try:
        plan, used_ai = await asyncio.wait_for(
            asyncio.to_thread(_make_plan_sync, topic, kind, size),
            timeout=config.PLAN_TIMEOUT + 10,
        )
    except asyncio.TimeoutError:
        log.warning("Reja tuzish vaqti tugadi - standart reja ishlatiladi")
        plan, used_ai = _offline_plan(), False
    except Exception as exc:  # noqa: BLE001
        log.exception("Reja tuzishda xatolik: %s", exc)
        plan, used_ai = _offline_plan(), False

    if not plan:
        plan, used_ai = _offline_plan(), False
    context.user_data["plan"] = plan

    lines = "\n".join(str(i) + ". " + str(pp) for i, pp in enumerate(plan, start=1))
    mode = "🤖 AI tuzgan reja" if used_ai else "📋 Standart reja"
    unit = "slayddagi" if kind == "prezentatsiya" else "hujjatdagi"

    if kind == "prezentatsiya":
        await status.edit_text(
            "<b>" + mode + ":</b>\n" + lines + "\n\n"
            "Shu reja asosida slaydlar yoziladi.\n"
            "Har bir slaydga rasm avtomatik qo'shiladi.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("✅ Boshlash", callback_data="img:-1")]]
            ),
            parse_mode=ParseMode.HTML,
        )
    else:
        await status.edit_text(
            "<b>" + mode + ":</b>\n" + lines + "\n\n"
            "Shu reja asosida " + unit + " bo'limlar yoziladi.\n"
            "Rejani o'zgartirmoqchi bo'lsangiz — yangi rejani qatorma-qator yozib yuboring.\n\n"
            "<b>Nechta rasm qo'shamiz?</b> (1–6 yoki rasmsiz)",
            reply_markup=_img_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    return PLAN


# ---------------------------------------------------------------------------
# 5. Generatsiya
# ---------------------------------------------------------------------------
async def plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    log.info("plan_callback: data=%s state=%s", query.data, context.user_data.get("kind"))
    await _safe_answer(query)
    img_n = 0
    if query.data.startswith("img:"):
        try:
            val = int(query.data.split(":", 1)[1])
            img_n = -1 if val < 0 else max(0, min(val, 6))
        except ValueError:
            img_n = 0
    else:
        img_n = 4 if query.data.endswith("1") else 0
    use_images = img_n > 0
    plan = context.user_data.get("plan")
    if not plan:
        try:
            await query.message.reply_text(
                "Reja topilmadi. /start bilan qaytadan boshlang."
            )
        except Exception:  # noqa: BLE001
            pass
        return MENU
    if context.user_data.get("kind") == "prezentatsiya":
        plan = [p for p in plan]
    await _generate(
        update, context, plan, use_images,
        via_message=query.message, img_target=img_n,
    )
    return MENU


async def plan_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    plan = None
    if text.lower() not in ("/skip", "skip", "yo'q", "yoq", "-"):
        plan = [
            re.sub(r"^[\d\s.\-)]+", "", line).strip()
            for line in text.splitlines()
            if line.strip()
        ][:8]
        plan = [p for p in plan if len(p) > 2]
    if not plan:
        plan = context.user_data.get("plan")
    context.user_data["plan"] = plan
    await update.message.reply_text(
        "✅ Reja qabul qilindi.\n\n<b>Nechta rasm qo'shamiz?</b> (1–6 yoki rasmsiz)",
        reply_markup=_img_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return PLAN


def _save_file(data, kind):
    """Tayyor tuzilmadan .docx yoki .pptx yaratadi."""
    if kind == "prezentatsiya":
        return create_presentation(data, config.OUT_DIR, stamp=data.get("stamp", ""))
    return create_document(data, config.OUT_DIR)


def _count_words(data):
    """Hujjat/slayd hajmini so'z bilan hisoblaydi."""
    words = data.get("words")
    if words:
        return words
    total = 0
    for ch in data.get("chapters") or []:
        for sub in ch.get("subs") or []:
            for par in sub.get("paras") or []:
                total += len(str(par).split())
    for s in data.get("slides") or []:
        for bullet in s.get("bullets") or []:
            total += len(str(bullet).split())
    return total


async def _heartbeat(status, started, stop_evt):
    """Har 12 soniyada holat matnini yangilaydi - bot tirik ekanini ko'rsatadi."""
    while True:
        try:
            await asyncio.wait_for(stop_evt.wait(), timeout=12)
            return
        except asyncio.TimeoutError:
            pass
        except Exception:  # noqa: BLE001
            return

        snap = ai_engine.progress_snapshot()
        elapsed = int(time.time() - started)
        stage = snap.get("stage") or "ishlanmoqda"
        done = int(snap.get("done") or 0)
        total = int(snap.get("total") or 0)
        if total:
            stage = f"{stage} ({done}/{total})"
        text = (
            f"\u23f3 {elapsed} soniya...\n"
            f"{stage}\n\n"
            "Bot ishlayapti, iltimos kuting.\n"
            "Fayl tayyor bo'lishi bilan yuboriladi."
        )
        try:
            await status.edit_text(text)
        except Exception:  # noqa: BLE001
            pass


_BUSY = {}  # user_id -> boshlangan vaqt (bir foydalanuvchi bir vaqtda bitta ish)


async def _generate(update, context, plan, use_images, via_message=None, img_target=None, **kwargs):
    source_text = (context.user_data.get("source") or "")[:8000]
    user = update.effective_user
    kind = context.user_data.get("kind", "referat")
    topic = context.user_data.get("topic", "Mavzu")
    info = context.user_data.get("info", {})
    size = context.user_data.get("size", 10)

    used_today = storage.today_count(user.id)
    if used_today >= config.DAILY_LIMIT:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Bugungi bepul limit tugadi ({config.DAILY_LIMIT} ta).\nErtaga yana urinib ko'ring \U0001f64f",
            reply_markup=main_menu(),
        )
        return

    _t0 = _BUSY.get(user.id)
    if _t0 and time.time() - _t0 < 240:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\u23f3 Oldingi ishingiz hali tayyorlanmoqda. Tugashini kuting.",
        )
        return
    _BUSY[user.id] = time.time()

    status = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "\u23f3 Matn bo'lim-bo'lim yozilmoqda va rasmlar qidirilmoqda...\n"
            "1-3 daqiqa olishi mumkin. Kuting, iltimos."
        ),
    )

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_%d" % (user.id % 100000)
    lang = storage.get_lang(update.effective_user.id)
    path = None
    started = time.time()
    stop_evt = asyncio.Event()
    ai_engine.progress_new()  # shu so'rov uchun alohida jarayon/byudjet (vazifalardan oldin)
    hb = asyncio.create_task(_heartbeat(status, started, stop_evt))

    try:
        ai_engine.progress_reset("reja va bo'limlar tuzilmoqda")
        try:
            data, mode, note = await asyncio.wait_for(
                asyncio.to_thread(
                    workflow.build_work, kind, topic, info, size, plan, use_images, stamp, False, lang, img_target, source_text
                ),
                timeout=config.GENERATE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            ai_engine.cancel_current()  # orqa fondagi AI so'rovlari davom etmasin
            log.warning(
                "AI %s soniyada javob bermadi - oflayn rejimga o'tildi",
                config.GENERATE_TIMEOUT,
            )
            stop_evt.set()
            hb.cancel()
            ai_engine.progress_reset("tez rejimda tayyorlanmoqda")
            stop_evt = asyncio.Event()
            hb = asyncio.create_task(_heartbeat(status, started, stop_evt))
            try:
                await status.edit_text(
                    "\u26a0\ufe0f AI sekinlashdi. Endi tez rejimda tayyorlanadi - 20-40 soniya..."
                )
            except Exception:  # noqa: BLE001
                pass
            data, mode, note = await asyncio.to_thread(
                workflow.build_work, kind, topic, info, size, plan, use_images, stamp, True, lang, img_target, source_text
            )
            mode = "offline"
            note = (
                f"AI {config.GENERATE_TIMEOUT} soniyada javob bermadi "
                "(sekin internet yoki xizmat bloklangan)"
            )

        path = await asyncio.wait_for(
            asyncio.to_thread(_save_file, data, kind), timeout=90
        )

        img_count = sum(
            1 for ch in data.get("chapters", []) for s in ch.get("subs", []) if s.get("image")
        ) or sum(1 for s in data.get("slides", []) if s.get("image"))

        img_note = ""
        if img_count == 0 and data.get("images_planned"):
            img_note = (
                "\n\u26a0\ufe0f Rasmlar topilmadi (internet yoki Wikimedia ochilmadi).\n"
                "Rasmni o'zingiz qo'shishingiz mumkin, yoki 3_DIAGNOSTIKA.bat ni ishlatib "
                "tekshiring.\n"
            )

        img_line = (f"\U0001f5bc Rasmlar: {img_count} ta\n" if img_count else "")
        LANG_DEFAULT = "O'zbekcha"
        caption = (
            "\u2705 <b>Tayyor!</b>\n\n"
            f"\U0001f4cc Mavzu: {topic}\n"
            f"\U0001f4e6 Tur: {KIND_TITLES.get(kind, kind)}\n"
            f"\U0001f310 Til: {i18n.LANG_NAMES.get(data.get('lang', 'uz'), LANG_DEFAULT)}\n"
            f"{img_line}"
            f"{img_note}\n"
            "Faylni ochib, o'z ma'lumotlaringiz bilan to'ldirishingiz mumkin.\n"
            "\U0001f4a1 Word'da mundarija uchun F9 ni bosing.\n\n"
            f"Bugun yaratilgan ishlar: {used_today + 1}/{config.DAILY_LIMIT}"
        )

        with open(path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(f, filename=os.path.basename(path)),
                caption=caption,
                parse_mode=ParseMode.HTML,
            )

        storage.log_work(user.id, kind, topic, os.path.basename(path))
        await status.delete()

        if mode != "ai":
            warn = (
                "\u26a0\ufe0f <b>Diqqat:</b> AI ishlamadi, matn oflayn shablondan olindi.\n"
            )
            if note:
                warn += f"<i>Sabab: {note[:250]}</i>\n"
            warn += (
                "Kalitni tekshirish uchun /ai buyrug'ini yuboring.\n"
                "Google xizmati sizning hududingizda bloklangan bo'lsa, VPN yoqing "
                "yoki OpenRouter kalitidan foydalaning (README'da yozilgan).\n"
                "Oflayn matn umumiyroq bo'ladi - AI kaliti bilan ancha aniq chiqadi."
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=warn, parse_mode=ParseMode.HTML
            )

    except asyncio.TimeoutError:
        log.exception("Fayl saqlash vaqti tugadi")
        try:
            await status.edit_text(
                "Faylni saqlash cho'zilib ketdi \U0001f614\n"
                "Qaytadan urinib ko'ring yoki /cancel bilan boshidan boshlang."
            )
        except Exception:  # noqa: BLE001
            pass
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("Fayl yaratishda xatolik: %s", exc)
        try:
            await status.edit_text(
                "Xatolik yuz berdi \U0001f614\n"
                "Iltimos, qaytadan urinib ko'ring yoki /cancel bilan boshidan boshlang."
            )
        except Exception:  # noqa: BLE001
            pass
        return
    finally:
        _BUSY.pop(user.id, None)
        stop_evt.set()
        hb.cancel()
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        await asyncio.to_thread(workflow.cleanup_images, stamp)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Yana biror ish kerakmi? Pastdagi tugmalardan tanlang.",
        reply_markup=bottom_menu(),
    )
    context.user_data.clear()


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bekor qilindi. Pastdagi tugmalardan birini tanlang.",
        reply_markup=bottom_menu(),
    )
    return MENU


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = f"🤖 AI: {provider_name()}" if ai_available() else "📦 oflayn rejim (AI kaliti yo'q)"
    await update.message.reply_text(
        "<b>Buyruqlar</b>\n\n"
        "/start — asosiy menyu\n"
        "/cancel — jarayonni bekor qilish\n"
        "/stats — bot statistikasi (faqat admin)\n"
        "/myid — sizning Telegram ID\n"
        "/rasm_ochir — saqlangan 3x4 rasmni o'chirish\n\n"
        f"Holat: {mode}",
        parse_mode=ParseMode.HTML,
    )


async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI kaliti ishlayotganini batafsil tekshirish."""
    msg = await update.message.reply_text("🔌 AI ulanishi tekshirilmoqda... (5-20 soniya)")
    ok, text = await asyncio.to_thread(test_connection)
    info = status_info()
    icon = "✅" if ok else "❌"

    lines = [
        f"{icon} <b>AI holati:</b> {text}",
        "",
        f"🔑 Kalit: <code>{info['key']}</code>",
        f"🤖 Model: <code>{info['model']}</code>",
        f"📡 So'rovlar (shu ishga tushishda): {info['calls']}",
    ]
    if info["last_ok"]:
        lines.append(f"🕒 Oxirgi muvaffaqiyatli so'rov: {info['last_ok']}")

    if not ok:
        err = info["last_error"] or last_error()
        if err:
            lines.append(f"\n⚠️ <i>Sabab: {err[:200]}</i>")
        lines.append(
            "\n<b>Nima qilish kerak:</b>\n"
            "1) keys.txt faylida <code>GEMINI_API_KEY=AIza...</code> qatori borligini tekshiring\n"
            "2) aistudio.google.com/apikey dan yangi kalit oling (bepul)\n"
            "3) Kalitni qo'ygach botni qayta ishga tushiring"
        )
    else:
        lines.append("\nHammasi joyida — matn AI orqali aniq yoziladi.")

    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot statistikasi - faqat administratorga yuboriladi."""
    uid = update.effective_user.id
    aid = _admin_id()
    if not aid:
        await update.message.reply_text(
            "Administrator hali belgilanmagan. /start buyrug'ini yuboring."
        )
        return
    if uid != aid:
        await update.message.reply_text("Bu buyruq faqat administrator uchun.")
        return
    await update.message.reply_text(
        _stats_text(), parse_mode=ParseMode.HTML, reply_markup=main_menu(uid)
    )


async def versiya_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ishlab turgan kod versiyasini ko'rsatadi."""
    await update.message.reply_text(
        "Versiya: <b>" + VERSION + "</b>\n"
        "Rasm soni tanlash: " + ("BOR" if "img_target" in _generate.__code__.co_varnames else "YO'Q") + "\n"
        "Obyektivka (Word+PDF): " + ("BOR" if hasattr(obyektivka, "build_all") else "YO'Q") + "\n"
        "Ishga tushgan vaqt: " + __import__("time").strftime("%Y-%m-%d %H:%M"),
        parse_mode=ParseMode.HTML,
    )


async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi o'z Telegram ID sini ko'radi."""
    uid = update.effective_user.id
    aid = _admin_id()
    role = "administrator" if uid == aid else "foydalanuvchi"
    await update.message.reply_text(
        "Sizning Telegram ID: <code>" + str(uid) + "</code>\n"
        "Rol: " + role,
        parse_mode=ParseMode.HTML,
    )



# ---------------------------------------------------------------------------
# 6b. Yangi vositalar: manba (kitob), misol yechish, OCR, PDF, ZIP
# ---------------------------------------------------------------------------
SUBJECT_NAMES = {
    "math": "Matematika", "fizika": "Fizika", "kimyo": "Kimyo",
    "bio": "Biologiya", "geom": "Geometriya", "it": "Informatika",
    "econ": "Iqtisodiyot", "eng": "Ingliz tili",
}


async def _download(update, context):
    """Xabardagi rasm yoki faylni yuklab, (nom, baytlar) qaytaradi."""
    msg = update.message
    photos = getattr(msg, "photo", None) or []
    if photos:
        f = await context.bot.get_file(photos[-1].file_id)
        return "rasm.jpg", bytes(await f.download_as_bytearray())
    doc = getattr(msg, "document", None)
    if doc is not None:
        f = await context.bot.get_file(doc.file_id)
        return (doc.file_name or "fayl"), bytes(await f.download_as_bytearray())
    raise RuntimeError("fayl yoq")


async def book_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    if query.data == "book:yes":
        await query.message.edit_text(
            "📚 Manba matnini yuboring:\n\n"
            "• matnni shu chatga yozib yuboring, yoki\n"
            "• .docx / .txt fayl qilib yuboring.\n\n"
            "Kamida 200 belgi bo'lsin. Bekor qilish: /cancel",
            parse_mode=ParseMode.HTML,
        )
        return BOOK_TEXT
    context.user_data["source"] = ""
    await query.message.edit_text("Yaxshi — AI o'zi yozadi ✅")
    await _ask_fan(query.message)
    return FAN


async def book_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ""
    doc = getattr(update.message, "document", None)
    if doc is not None:
        name = (doc.file_name or "").lower()
        try:
            f = await context.bot.get_file(doc.file_id)
            raw = bytes(await f.download_as_bytearray())
        except Exception:  # noqa: BLE001
            await update.message.reply_text("Faylni yuklab bo'lmadi. Qayta yuboring.")
            return BOOK_TEXT
        if name.endswith(".txt"):
            text = raw.decode("utf-8", "ignore")
        elif name.endswith(".docx"):
            try:
                import docx
                d = docx.Document(io.BytesIO(raw))
                text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
            except Exception:  # noqa: BLE001
                await update.message.reply_text("Word faylini o'qib bo'lmadi. Matnni yozib yuboring.")
                return BOOK_TEXT
        else:
            await update.message.reply_text(
                "Faqat .docx yoki .txt qabul qilinadi. Matnni oddiy xabar qilib yuboring."
            )
            return BOOK_TEXT
    else:
        text = update.message.text or ""

    if len(text.strip()) < 200:
        await update.message.reply_text(
            "Matn juda qisqa (kamida 200 belgi kerak). To'liqroq matn yuboring."
        )
        return BOOK_TEXT

    context.user_data["source"] = text.strip()[:8000]
    await update.message.reply_text(
        "✅ Manba qabul qilindi (" + str(len(text)) + " belgi). Shu asosda yoziladi."
    )
    await _ask_fan(update.message)
    return FAN


async def solve_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    code = query.data.split(":", 1)[1]
    subject = SUBJECT_NAMES.get(code, "Matematika")
    context.user_data["solve_subject"] = subject
    await query.message.edit_text(
        "🧮 <b>" + subject + "</b>\n\n"
        "Misol yoki masalani yozib yuboring.\n\n"
        "Agar namuna kerak bo'lsa: avval namuna matnini, keyin <code>---</code>, "
        "keyin masalani yozing.\n\nBekor qilish: /cancel",
        parse_mode=ParseMode.HTML,
    )
    return SOLVE_TEXT


async def solve_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    subject = context.user_data.get("solve_subject", "Matematika")
    if len(text) < 5:
        await update.message.reply_text("Masala juda qisqa. To'liqroq yozing.")
        return SOLVE_TEXT

    sample = ""
    if "---" in text:
        sample, text = text.split("---", 1)
    if not ai_available():
        await update.message.reply_text(
            "Misol yechish uchun AI kaliti kerak. keys.txt dagi kalitni tekshiring."
        )
        return MENU

    status = await update.message.reply_text("🧮 Yechilmoqda, 10-30 soniya...")
    try:
        res = await asyncio.wait_for(
            asyncio.to_thread(
                ai_engine.ai_solve, subject,
                text.strip(), sample.strip(),
                storage.get_lang(update.effective_user.id),
            ),
            timeout=120,
        )
    except asyncio.TimeoutError:
        await status.edit_text("⏳ Vaqt tugadi. Qayta urinib ko'ring.")
        return MENU
    except Exception as exc:  # noqa: BLE001
        log.exception("Misol yechishda xato")
        await status.edit_text(
            "❌ Yechib bo'lmadi.\n<code>" + str(exc)[:150] + "</code>",
            parse_mode=ParseMode.HTML,
        )
        return MENU

    parts = ["🧮 <b>" + subject + "</b>\n"]
    if res.get("given"):
        parts.append("<b>Berilgan:</b> " + res["given"])
    if res.get("formula"):
        parts.append("<b>Formula:</b> " + res["formula"])
    if res.get("steps"):
        parts.append("\n<b>Yechish:</b>")
        for i, st in enumerate(res["steps"], start=1):
            parts.append(str(i) + ". " + st)
    if res.get("final"):
        parts.append("\n✅ <b>Javob:</b> " + res["final"])

    out = "\n".join(parts)
    for i in range(0, len(out), 3500):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=out[i:i + 3500],
            parse_mode=ParseMode.HTML,
        )
    context.user_data.pop("solve_subject", None)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Yana kerakmi? Pastdagi tugmalardan tanlang.",
        reply_markup=bottom_menu(),
    )
    return MENU


async def ocr_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tools.ocr_available():
        await update.message.reply_text(
            "Rasmdan matn olish moduli o'rnatilmagan.\n"
            "Bir marta 9_OCR_ORNATISH.bat ni bosing (2-3 daqiqa), keyin botni qayta yoqing."
        )
        return MENU
    try:
        _name, raw = await _download(update, context)
    except Exception:  # noqa: BLE001
        await update.message.reply_text("Rasmni yuklab bo'lmadi. Qayta yuboring.")
        return OCR_PHOTO

    status = await update.message.reply_text(
        "\U0001f50d Matn o'qilmoqda, Word fayl tayyorlanmoqda..."
    )
    docx_bytes = None
    text = ""
    try:
        docx_bytes, text = await asyncio.to_thread(tools.image_to_docx, raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("OCR -> docx xatosi: %s", exc)
        try:
            text = await asyncio.to_thread(tools.image_to_text, raw)
        except Exception as exc2:  # noqa: BLE001
            await status.edit_text("\u274c O'qib bo'lmadi: " + str(exc2)[:120])
            return MENU

    if not (text or "").strip():
        await status.edit_text("Rasmda matn topilmadi. Aniqroq, yorug'roq rasm yuboring.")
        return MENU

    await status.edit_text("\u2705 Tayyor (" + str(len(text)) + " belgi). Word fayl yuborilmoqda...")

    if docx_bytes:
        try:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(io.BytesIO(docx_bytes), filename="matn.docx"),
                caption=(
                    "\U0001f4c4 <b>Word (.docx)</b> — rasmning ko'rinishi saqlangan.\n"
                    "Satr joyi, tekislash, o'lcham va bo'sh masofalar asl rasmga moslandi.\n"
                    "Kichik xatolarni Word'da tuzatib olasiz."
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:  # noqa: BLE001
            log.exception("docx yuborilmadi")

    preview = text if len(text) <= 1200 else text[:1200] + "\u2026"
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Matn (tekshirish uchun):\n" + preview
        )
    except Exception:  # noqa: BLE001
        pass
    return MENU


async def pdf_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        _name, raw = await _download(update, context)
    except Exception:  # noqa: BLE001
        await update.message.reply_text("Rasmni yuklab bo'lmadi. Qayta yuboring.")
        return PDF_PHOTO
    imgs = context.user_data.setdefault("pdf_imgs", [])
    imgs.append(raw)
    await update.message.reply_text(
        "✅ " + str(len(imgs)) + " ta rasm qo'shildi. Yana yuboring yoki "
        "«📄 PDF yaratish» tugmasini bosing.",
        reply_markup=_pdf_keyboard(),
    )
    return PDF_PHOTO


async def pdf_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    imgs = context.user_data.get("pdf_imgs") or []
    if not imgs:
        await query.message.edit_text("Rasm topilmadi. Avval rasm yuboring.")
        return PDF_PHOTO
    await query.message.edit_text("📄 PDF yig'ilmoqda...")
    try:
        data = await asyncio.to_thread(tools.images_to_pdf, imgs)
    except Exception as exc:  # noqa: BLE001
        await query.message.edit_text("❌ PDF yaratilmadi: " + str(exc)[:120])
        return MENU
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=InputFile(io.BytesIO(data), filename="rasmlar.pdf"),
        caption="📄 " + str(len(imgs)) + " ta rasmdan tayyorlangan PDF.",
    )
    context.user_data["pdf_imgs"] = []
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Yana kerakmi? Pastdagi tugmalardan tanlang.",
        reply_markup=bottom_menu(),
    )
    return MENU


async def zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name, raw = await _download(update, context)
    except Exception:  # noqa: BLE001
        await update.message.reply_text("Faylni yuklab bo'lmadi. Qayta yuboring.")
        return ZIP_FILES

    if name.lower().endswith(".zip"):
        try:
            files = await asyncio.to_thread(tools.unzip_files, raw)
        except Exception as exc:  # noqa: BLE001
            await update.message.reply_text("❌ " + str(exc)[:150])
            return ZIP_FILES
        await update.message.reply_text("📦 Ichida " + str(len(files)) + " ta fayl bor. Yuborilmoqda...")
        for fn, data in files[:15]:
            try:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=InputFile(io.BytesIO(data), filename=fn),
                )
            except Exception:  # noqa: BLE001
                continue
        return ZIP_FILES

    files = context.user_data.setdefault("zip_files", [])
    files.append((name, raw))
    await update.message.reply_text(
        "✅ " + str(len(files)) + " ta fayl. Yana yuboring yoki «🗜 ZIP yaratish» tugmasini bosing.",
        reply_markup=_zip_keyboard(),
    )
    return ZIP_FILES


async def zip_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    files = context.user_data.get("zip_files") or []
    if not files:
        await query.message.edit_text("Fayl topilmadi. Avval fayl yuboring.")
        return ZIP_FILES
    try:
        data = await asyncio.to_thread(tools.make_zip, files)
    except Exception as exc:  # noqa: BLE001
        await query.message.edit_text("❌ ZIP yaratilmadi: " + str(exc)[:120])
        return MENU
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=InputFile(io.BytesIO(data), filename="arxiv.zip"),
        caption="🗜 " + str(len(files)) + " ta fayl bitta ZIP da.",
    )
    context.user_data["zip_files"] = []
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Yana kerakmi? Pastdagi tugmalardan tanlang.",
        reply_markup=bottom_menu(),
    )
    return MENU


async def on_error(update, context):
    err = context.error
    name = type(err).__name__
    msg = str(err or "")
    if name in ("TimedOut", "NetworkError") or "Query is too old" in msg or "query id is invalid" in msg:
        log.warning("Etiborsiz xato: %s", msg[:150])
        return
    log.exception("Kutilmagan xatolik", exc_info=err)
    try:
        if update and getattr(update, "effective_message", None):
            short = (name + ": " + msg)[:160].replace("&", "and").replace("<", "(").replace(">", ")")
            txt = "Kechirasiz, xatolik yuz berdi." + chr(10) + "<code>" + short + "</code>" + chr(10) + chr(10) + "/start bilan qaytadan urinib koring."
            await update.effective_message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 7. Ishga tushirish
# ---------------------------------------------------------------------------
def main():
    if "TOKEN" in config.BOT_TOKEN or len(config.BOT_TOKEN) < 20:
        print("=" * 62)
        print(" BOT_TOKEN topilmadi!")
        print(" 1) @BotFather dan token oling")
        print(" 2) token.txt fayliga yoki keys.txt ga BOT_TOKEN=... qilib yozing")
        print("=" * 62)
        return

    # Tarmoq javob bermasa cheksiz kutmaslik uchun umumiy chegara
    socket.setdefaulttimeout(45)

    os.makedirs(config.OUT_DIR, exist_ok=True)
    os.makedirs(config.IMG_DIR, exist_ok=True)
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # Konsol yopilganda ham xatolarni ko'rish uchun faylga yozamiz
    log_path = os.path.join(config.DATA_DIR, "bot.log")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(file_handler)

    # Ikki nusxa ishga tushib qolsa Telegram to'qnashuvini oldini olamiz
    global _LOCK_SOCKET
    _LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _LOCK_SOCKET.bind(("127.0.0.1", 47311))
        _LOCK_SOCKET.listen(1)
    except OSError:
        print("Bot allaqachon ishlayapti. Ikkinchi nusxani ishga tushirmang.")
        return

    print(f"Rejim: {'AI - ' + provider_name() if ai_available() else 'oflayn (AI kaliti yo`q)'}")
    print(f"Jurnal fayli: {log_path}")

    # concurrent_updates: bir foydalanuvchining uzoq ishi boshqalarni kutdirmasin
    app = ApplicationBuilder().token(config.BOT_TOKEN).concurrent_updates(16).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(menu_callback, pattern="^(help|my|feedback|stats|lang_menu)$"),
                CallbackQueryHandler(choose_kind, pattern="^kind:"),
            ],
            TOPIC: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, get_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_topic),
            ],
            FAN: [
                MessageHandler(_BTN_FILTER, menu_text),
                CommandHandler("skip", skip_fan),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_fan),
            ],
            SIZE: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, get_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_pages),
            ],
            TITUL: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, get_photo),
                CallbackQueryHandler(titul_callback, pattern="^titul:"),
            ],
            INFO: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, get_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_info),
            ],
            FEEDBACK: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_feedback),
            ],
            R_PHOTO: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, r_photo),
            ],
            R_BG: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(r_bg, pattern="^bg:"),
            ],
            R_DRESS: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(r_dress, pattern="^dress:"),
            ],
            R_REF: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(r_ref_choice, pattern="^ref:"),
                MessageHandler(_PHOTO_FILTER, r_ref_photo),
            ],
            BOOK_ASK: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(book_callback, pattern="^book:"),
            ],
            BOOK_TEXT: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(filters.Document.ALL, book_text),
                MessageHandler(filters.TEXT  &  ~filters.COMMAND, book_text),
            ],
            SOLVE_SUB: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(solve_sub, pattern="^subj:"),
            ],
            SOLVE_TEXT: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(filters.TEXT  &  ~filters.COMMAND, solve_text),
            ],
            OCR_PHOTO: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, ocr_photo),
            ],
            PDF_PHOTO: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, pdf_photo),
                CallbackQueryHandler(pdf_go, pattern="^pdf:go"),
            ],
            ZIP_FILES: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(filters.Document.ALL | filters.PHOTO, zip_file),
                CallbackQueryHandler(zip_go, pattern="^zip:go"),
            ],
            OBY_ASK: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, oby_photo),
                CommandHandler("skip", oby_skip_step),
                MessageHandler(_OBY_TEXT_FILTER, oby_answer),
            ],
            OBY_WORK: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(oby_work_done, pattern="^oby:workdone$"),
                CommandHandler("skip", oby_work_done),
                MessageHandler(_OBY_TEXT_FILTER, oby_work_answer),
            ],
            OBY_REL: [
                MessageHandler(_BTN_FILTER, menu_text),
                CallbackQueryHandler(oby_rel_role, pattern="^obyrole:"),
                CallbackQueryHandler(oby_rel_done, pattern="^oby:reldone$"),
                MessageHandler(_OBY_TEXT_FILTER, oby_rel_answer),
            ],
            OBY_PHOTO: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, oby_photo),
                CallbackQueryHandler(oby_nophoto, pattern="^oby:nophoto$"),
                MessageHandler(_OBY_TEXT_FILTER, oby_answer),
            ],
            PLAN: [
                MessageHandler(_BTN_FILTER, menu_text),
                MessageHandler(_PHOTO_FILTER, get_photo),
                CallbackQueryHandler(plan_callback, pattern="^(go|img):"),
                CommandHandler("skip", plan_text),
                MessageHandler(filters.TEXT & ~filters.COMMAND, plan_text),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang:"))
    # Zaxira: reja/rasm soni tugmalari suhbat holatidan qat'i nazar ishlaydi
    app.add_handler(
        CallbackQueryHandler(plan_callback, pattern="^(go|img):"), group=1
    )
    app.add_handler(__import__("telegram").ext.MessageHandler(__import__("telegram").ext.filters.TEXT & ~__import__("telegram").ext.filters.COMMAND, batch_fast.toplam_text), group=1)
    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ai", ai_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("myid", myid_cmd))
    app.add_handler(CommandHandler("versiya", versiya_cmd))
    app.add_handler(CommandHandler("sayt", site_cmd))
    app.add_handler(CommandHandler("elon", batch_fast.elon_cmd))
    app.add_handler(CommandHandler("elon_yuborish", batch_fast.elon_send_cmd))
    app.add_handler(CommandHandler("toplam", batch_fast.toplam_cmd))
    app.add_handler(CommandHandler("id", myid_cmd))
    app.add_error_handler(on_error)

    print("Versiya: " + VERSION)
    print("Bot ishga tushdi. To'xtatish uchun Ctrl+C")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
