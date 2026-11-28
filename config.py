# -*- coding: utf-8 -*-
"""
Bot sozlamalari.

Token va AI kalitlarini 3 usulda berish mumkin:
  1) keys.txt fayli (eng oson) - ichiga qator-qator yozing:
         BOT_TOKEN=123456:AAH...
         GEMINI_API_KEY=AIza...
  2) config.py ichidagi pastdagi qatorlarga yozish
  3) muhit o'zgaruvchilari (set BOT_TOKEN=...)
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# keys.txt dan o'qish
# ---------------------------------------------------------------------------
def _read_keys():
    keys = {}
    path = os.path.join(BASE_DIR, "keys.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                keys[k.strip().upper()] = v.strip().strip('"').strip("'")
    return keys


_KEYS = _read_keys()


def _get(name, default=""):
    return (os.getenv(name) or _KEYS.get(name) or default).strip()


# ---------------------------------------------------------------------------
# Telegram token
# ---------------------------------------------------------------------------
def _read_token():
    token = _get("BOT_TOKEN")
    if token:
        return token
    path = os.path.join(BASE_DIR, "token.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return "BU_YERGA_TOKEN_QOYING"


BOT_TOKEN = _read_token()


# ---------------------------------------------------------------------------
# AI (aqlli rejim)
# ---------------------------------------------------------------------------
# Tavsiya: Google AI Studio dan BEPUL Gemini kaliti oling:
#   https://aistudio.google.com/apikey
# Asosiy model ishlamasa (model topilmadi / limit tugadi) navbat bilan sinaladi
GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MODEL_FALLBACKS = [
    m.strip()
    for m in _get(
        "GEMINI_MODEL_FALLBACKS",
        "gemini-2.5-flash-lite,gemini-2.0-flash,gemini-flash-latest",
    ).split(",")
    if m.strip()
]

# Muqobil: OpenAI yoki OpenAI-mos server (OpenRouter, Groq, DeepSeek va h.k.)
OPENAI_API_KEY = _get("OPENAI_API_KEY")
OPENAI_BASE_URL = _get("OPENAI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = _get("AI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY_BACKUP = _get("OPENAI_API_KEY_BACKUP")
OPENAI_BASE_URL_BACKUP = _get("OPENAI_BASE_URL_BACKUP", "https://openrouter.ai/api/v1")
AI_MODEL_BACKUP = _get("AI_MODEL_BACKUP", "nvidia/nemotron-3-ultra-550b-a55b:free")
AI_MODEL_BACKUP_FALLBACKS = [
    m.strip()
    for m in _get("AI_MODEL_BACKUP_FALLBACKS", "google/gemma-4-31b-it:free").split(",")
    if m.strip()
]

AI_MODEL_FALLBACKS = [
    m.strip()
    for m in _get(
        "AI_MODEL_FALLBACKS",
        "baidu/ernie-5.5-flash-preview:free,google/gemma-4-31b-it:free",
    ).split(",")
    if m.strip()
]

AI_TEMPERATURE = float(_get("AI_TEMPERATURE", "0.6"))

# Bitta so'rov uchun kutish vaqti (soniya)
AI_TIMEOUT = int(_get("AI_TIMEOUT", "50"))

# Har bir modelda necha marta urinish (kamaytirildi - bot osilib qolmasin)
AI_ATTEMPTS = int(_get("AI_ATTEMPTS", "1"))

# Matn yozish uchun umumiy vaqt byudjeti (soniya). Tugasa - oflayn rejim.
AI_BUDGET = int(_get("AI_BUDGET", "90"))

# Butun ish (matn + rasmlar + fayl) uchun maksimal vaqt (soniya)
GENERATE_TIMEOUT = int(_get("GENERATE_TIMEOUT", "180"))

# Reja tuzish uchun qisqa muddat: javob kelmasa - standart rejaga o'tadi
# (bot "Reja tuzilmoqda..." da qotib qolmasligi uchun)
PLAN_TIMEOUT = int(_get("PLAN_TIMEOUT", "35"))

# Kalit bo'lmasa: False -> oflayn shablon rejimida ishlaydi
AI_ENABLED = bool(GEMINI_API_KEY or OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Rasmlar
# ---------------------------------------------------------------------------
# Rasmlar Wikimedia Commons va Openverse (bepul, kalitsiz) dan olinadi
IMAGES_ENABLED = _get("IMAGES_ENABLED", "1") not in ("0", "false", "False")
MAX_IMAGES_DOC = int(_get("MAX_IMAGES_DOC", "2"))
MAX_IMAGES_SLIDES = int(_get("MAX_IMAGES_SLIDES", "5"))


# ---------------------------------------------------------------------------
# Fayllar va limitlar
# ---------------------------------------------------------------------------
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "bot.db")
OUT_DIR = os.path.join(DATA_DIR, "files")
IMG_DIR = os.path.join(DATA_DIR, "images")

DAILY_LIMIT = int(_get("DAILY_LIMIT", "5"))
ADMIN_ID = int(_get("ADMIN_ID", "0"))

# Sayt manzili (botdagi "Sayt" tugmasi shu manzilni ochadi).
# Sayt internetga chiqarilgach keys.txt ga SITE_URL=https://... qatorini qo'shing.
SITE_URL = _get("SITE_URL", "http://127.0.0.1:5000")

# 3x4 rasm uchun alohida kalit (ixtiyoriy). Bo'sh bo'lsa OPENAI_* ishlatiladi.
PHOTO_API_KEY = _get("PHOTO_API_KEY", "")
PHOTO_BASE_URL = _get("PHOTO_BASE_URL", "")
PHOTO_MODEL = _get("PHOTO_MODEL", "")

BOT_NAME = "Talaba Yordamchisi"
