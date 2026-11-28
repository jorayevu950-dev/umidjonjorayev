# -*- coding: utf-8 -*-
"""
Bot nega qotib qolayotganini aniqlash uchun tekshiruv.

Ishga tushirish: Diagnostika.bat ni ikki marta bosing
(yoki: python diagnostika.py)

Natija ekranga chiqadi. Muammo bo'lsa - shu matnni nusxalab yuboring.
"""

import json
import os
import platform
import socket
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OK = "[ OK ]"
NO = "[ XATO ]"
WARN = "[ ?? ]"

problems = []


def line(title=""):
    if title:
        print("\n" + title)
    print("-" * 58)


def check_tcp(host, port=443, timeout=8):
    t = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, round((time.time() - t) * 1000)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:60]


def read_keys():
    keys = {}
    path = os.path.join(BASE, "keys.txt")
    if not os.path.exists(path):
        return keys, False
    with open(path, encoding="utf-8", errors="ignore") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            keys[k.strip().upper()] = v.strip().strip('"').strip("'")
    return keys, True


def gemini_ping(key):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=" + key
    )
    payload = {
        "contents": [{"parts": [{"text": "Salom, faqat OK deb javob ber."}]}],
        "generationConfig": {"maxOutputTokens": 30, "thinkingConfig": {"thinkingBudget": 0}},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            resp.read(200)
            return True, f"javob {round(time.time() - t, 1)} soniya"
    except urllib.error.HTTPError as exc:
        body = exc.read(400).decode("utf-8", "ignore")
        low = body.lower()
        if "api key not valid" in low or "api_key_invalid" in low or exc.code == 403:
            return False, "kalit qabul qilinmadi (HTTP %s)" % exc.code
        if exc.code == 429:
            return None, "bepul limit tugagan (429) - 1 daqiqadan keyin qayta urinib ko'ring"
        if exc.code in (400, 404):
            return None, "kalit ishlayapti (model javobi: HTTP %s)" % exc.code
        return False, f"HTTP {exc.code}: {body[:140]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:120]


def chat_ping(base, key, model, prompt, max_tokens, timeout=70):
    """OpenAI-mos serverga haqiqiy so'rov yuboradi va vaqtini o'lchaydi."""
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        secs = time.time() - t
        try:
            used = (json.loads(raw.decode("utf-8", "ignore")).get("usage") or {}).get("completion_tokens")
        except Exception:  # noqa: BLE001
            used = None
        extra = f", {used} token" if used else ""
        return True, f"javob {secs:.1f} soniya{extra}", secs
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode("utf-8", "ignore")
        if exc.code in (401, 403):
            return False, f"kalit qabul qilinmadi (HTTP {exc.code})", 0
        if exc.code == 402:
            return False, "balans tugagan (HTTP 402)", 0
        if exc.code == 404:
            return False, f"model topilmadi (HTTP 404): {model}", 0
        if exc.code == 429:
            return None, "limit tugagan (HTTP 429) - birozdan keyin urinib ko'ring", 0
        return False, f"HTTP {exc.code}: {body[:120]}", 0
    except Exception as exc:  # noqa: BLE001
        return False, f"{str(exc)[:90]} ({time.time() - t:.0f} soniya kutildi)", 0


def test_provider(title, base, key, model):
    """Bitta provayderni sinaydi: qisqa javob + uzunroq matn tezligi."""
    print(f"  [{title}] {base}  model: {model}")
    ok, msg, _ = chat_ping(base, key, model, "Faqat OK deb javob ber.", 16)
    if ok is True:
        print("   ", OK, "qisqa so'rov:", msg)
    elif ok is None:
        print("   ", WARN, "qisqa so'rov:", msg)
        return
    else:
        print("   ", NO, "qisqa so'rov:", msg)
        problems.append(f"{title} AI ({model}): {msg}")
        return
    ok, msg, secs = chat_ping(
        base, key, model,
        "O'zbek tilida sun'iy intellekt haqida 200 so'zdan iborat bitta paragraf yoz.", 500,
    )
    if ok is True:
        mark = OK if secs < 25 else WARN
        print("   ", mark, "uzun matn (taxminan 500 token):", msg)
        if secs >= 25:
            problems.append(
                f"{title} AI ({model}) JUDA SEKIN: oddiy bo'lim ham {secs:.0f} soniya oladi - "
                "boshqa (tezroq) model tanlang"
            )
    else:
        print("   ", WARN, "uzun matn:", msg)


def log_tail(n=25):
    path = os.path.join(BASE, "data", "bot.log")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="ignore") as f:
        rows = [r.rstrip("\n") for r in f]
    return rows[-n:]


def main():
    print("=" * 58)
    print("  TALABA YORDAMCHISI - DIAGNOSTIKA")
    print("=" * 58)

    # 1. Python
    line("1. Python")
    ver = sys.version.split()[0]
    if sys.version_info < (3, 9):
        print(NO, "Python", ver, "- juda eski (3.9+ kerak)")
        problems.append("Python 3.9 yoki yangirog'ini o'rnating")
    else:
        print(OK, "Python", ver, f"({platform.machine()}, {platform.system()})")

    for mod in ("telegram", "docx", "pptx", "requests"):
        try:
            __import__(mod)
            print(OK, "kutubxona:", mod)
        except Exception:  # noqa: BLE001
            print(NO, "kutubxona yo'q:", mod)
            problems.append(f"pip install -r requirements.txt  ({mod} yetishmayapti)")

    # 2. Kalitlar
    line("2. Kalitlar (keys.txt)")
    keys, has_file = read_keys()
    if not has_file:
        print(NO, "keys.txt fayli topilmadi")
        problems.append("keys.txt faylini yarating (Kalitlarni_sozlash.bat)")
    else:
        print(OK, "keys.txt topildi")

    token = keys.get("BOT_TOKEN", "")
    if not token:
        print(NO, "BOT_TOKEN yo'q")
        problems.append("BOT_TOKEN ni keys.txt ga yozing")
    elif ":" not in token or len(token) < 25:
        print(WARN, "BOT_TOKEN shakli g'alati:", token[:8] + "...")
    else:
        print(OK, "BOT_TOKEN bor:", token[:8] + "..." + token[-4:])

    gemini = keys.get("GEMINI_API_KEY", "")
    openai_key = keys.get("OPENAI_API_KEY", "")
    if gemini:
        print(OK, "GEMINI_API_KEY bor:", gemini[:6] + "..." + gemini[-4:])
    elif openai_key:
        print(OK, "OPENAI_API_KEY bor:", openai_key[:6] + "..." + openai_key[-4:])
        print("     manzil:", keys.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    else:
        print(WARN, "AI kaliti yo'q - bot faqat oflayn shablon bilan ishlaydi")

    # 3. Internet
    line("3. Internet (serverlarga ulanish)")
    checks = [
        ("api.telegram.org", "Telegram"),
        ("generativelanguage.googleapis.com", "Google AI"),
        ("openrouter.ai", "OpenRouter"),
        ("commons.wikimedia.org", "Wikimedia (rasmlar)"),
    ]
    from urllib.parse import urlparse

    for k in ("OPENAI_BASE_URL", "OPENAI_BASE_URL_BACKUP"):
        h = urlparse(keys.get(k, "")).hostname
        if h and all(h != c[0] for c in checks):
            checks.append((h, "AI server"))
    for host, title in checks:
        state, info = check_tcp(host)
        if state:
            print(OK, f"{title:26} {host} ({info} ms)")
        else:
            print(NO, f"{title:26} {host} - {info}")
            if "telegram" in host:
                problems.append("api.telegram.org ochilmayapti - internet/VPN ni tekshiring")
            else:
                problems.append(f"{host} ochilmayapti - VPN yoki OpenRouter variantini ishlatib ko'ring")

    # 4. AI kaliti amalda ishlayaptimi
    line("4. AI kaliti va tezligi sinovi (2 daqiqagacha kutish mumkin)")
    if gemini:
        ok, msg = gemini_ping(gemini)
        if ok is True:
            print(OK, "Gemini javob berdi -", msg)
        elif ok is None:
            print(WARN, "Gemini:", msg)
        else:
            print(NO, "Gemini javob bermadi -", msg)
            problems.append("Gemini kaliti ishlamayapti: yangi kalit oling yoki OpenRouter ishlatib ko'ring")
    elif openai_key:
        test_provider(
            "ASOSIY",
            keys.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_key,
            keys.get("AI_MODEL", "gpt-4o-mini"),
        )
        backup_key = keys.get("OPENAI_API_KEY_BACKUP", "")
        if backup_key:
            test_provider(
                "ZAXIRA",
                keys.get("OPENAI_BASE_URL_BACKUP", "https://openrouter.ai/api/v1"),
                backup_key,
                keys.get("AI_MODEL_BACKUP", "nvidia/nemotron-3-ultra-550b-a55b:free"),
            )
    else:
        print(WARN, "AI kaliti yo'q - sinov o'tkazilmadi")

    # 5. Bot ishlayaptimi
    line("5. Bot jarayoni")
    state, _ = check_tcp("127.0.0.1", 47311, timeout=2)
    if state:
        print(OK, "bot ishlab turibdi (port 47311 band)")
    else:
        print(WARN, "bot ishlab turgani aniqlanmadi (o'chirilgan bo'lishi mumkin)")

    # 6. Jurnal
    line("6. Jurnal (data/bot.log oxirgi qatorlari)")
    tail = log_tail()
    if tail is None:
        print(WARN, "data/bot.log hali yo'q - bot bir marta ishga tushmagan")
    else:
        for row in tail:
            print("   ", row[:110])

    # 7. Xulosa
    line("7. Xulosa")
    if not problems:
        print(OK, "Hammasi joyida ko'rinadi.")
        print("     Agar bot hali ham qotib qolsa: botni qayta ishga tushiring")
        print("     (Botni_toxtatish.bat, keyin start_hidden.vbs).")
    else:
        seen = []
        for p in problems:
            if p not in seen:
                seen.append(p)
        for i, p in enumerate(seen, 1):
            print(f"  {i}. {p}")
    print("\n" + "=" * 58)
    print("Shu matnni nusxalab yuborsangiz, sababini aniq aytaman.")
    print("=" * 58)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # noqa: BLE001
        print("Diagnostika xatosi:", exc)
    try:
        input("\nYopish uchun Enter bosing...")
    except Exception:  # noqa: BLE001
        pass
