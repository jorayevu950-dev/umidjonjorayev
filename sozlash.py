# -*- coding: utf-8 -*-
"""Birinchi ishga tushirish yordamchisi.

Vazifasi: bot tokeni bor-yo'qligini tekshirish, kerak bo'lsa bir marta so'rash
va keys.txt ga yozib qo'yish. Keyin botni ishga tushirish.
"""

import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
KEYS_PATH = os.path.join(BASE, "keys.txt")
PLACEHOLDER = "BU_YERGA_TOKEN_QOYING"
TOKEN_RE = re.compile(r"^\d{5,12}:[A-Za-z0-9_\-]{25,}$")

OK = "[ OK ]"
WARN = "[ ?? ]"
NO = "[ XATO ]"


def _read_lines():
    if not os.path.exists(KEYS_PATH):
        return []
    with open(KEYS_PATH, encoding="utf-8-sig") as f:
        return f.read().splitlines()


def _write_lines(lines):
    with open(KEYS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def get_value(lines, name):
    name = name.upper()
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip().upper() == name:
            return v.strip().strip('"').strip("'")
    return ""


def set_value(lines, name, value):
    name_u = name.upper()
    out, done = [], False
    for line in lines:
        s = line.strip()
        if not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip().upper()
            if k == name_u:
                out.append("%s=%s" % (name_u, value))
                done = True
                continue
        out.append(line)
    if not done:
        out.append("%s=%s" % (name_u, value))
    return out


def ensure_token(ask=input, out=print):
    """Tokenni tekshiradi; kerak bo'lsa so'raydi va keys.txt ga yozadi."""
    lines = _read_lines()
    token = get_value(lines, "BOT_TOKEN")
    if TOKEN_RE.match(token or ""):
        out(OK + " Telegram tokeni saqlangan (…%s)" % token[-6:])
        return token

    out("")
    out("BOT TOKENI KERAK (faqat birinchi marta)")
    out("  1) Telegramda @BotFather ni oching")
    out("  2) /mybots - botingizni tanlang - API Token")
    out("  3) Chiqqan qatorni nusxalab, pastga qo'ying (Ctrl+V) va Enter bosing")
    out("")
    while True:
        try:
            raw = ask("Token: ")
        except (EOFError, KeyboardInterrupt):
            out("\nBekor qilindi. 1_BOSHLASH.bat ni qayta bosib, tokenni kiriting.")
            return None
        token = (raw or "").strip().strip('"').strip("'")
        token = token.replace(" ", "")
        if TOKEN_RE.match(token):
            break
        out(WARN + " Bu tokenga o'xshamadi. Namuna: 8123456789:AAH... (raqam, : belgisi, harflar)")

    lines = set_value(lines or [], "BOT_TOKEN", token)
    _write_lines(lines)
    out(OK + " Token saqlandi (…%s). Boshqa sozlash kerak emas." % token[-6:])
    return token


def main():
    out = print
    out("=" * 58)
    out("   TALABA YORDAMCHISI - BOT")
    out("=" * 58)

    lines = _read_lines()
    model = get_value(lines, "AI_MODEL") or "gpt-4o-mini"
    out(OK + " AI tayyor: “%s” (bepul)" % model)

    token = ensure_token()
    if not token:
        return 1

    out("")
    out("Bot ishga tushmoqda... (bu oynani yopmang)")
    out("To'xtatish: shu oynada Ctrl+C yoki 2_TOXTATISH.bat")
    out("-" * 58)
    code = subprocess.call([sys.executable, "bot.py"], cwd=BASE)
    out("-" * 58)
    out("Bot to'xtadi (kod: %s)" % code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
