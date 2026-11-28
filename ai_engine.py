# -*- coding: utf-8 -*-
"""
AI mazmun generatori (aqlli rejim) - 3-versiya.

Muhim yaxshilanishlar:
  * Matn BO'LIM-BO'LIM yoziladi (bitta katta javob emas) - shu sababli
    matn to'liq, chuqur va mavzuga xos chiqadi, kesilib qolmaydi.
  * Har bir bo'lim sifat tekshiruvidan o'tadi: mavzu atamalari bormi,
    hajm yetarlimi. Yetishmasa - avtomatik qayta yoziladi.
  * Gemini 2.5 da "o'ylash" (thinking) tokenlari o'chiriladi - javob
    to'liq sig'adi (avval shu sababli javob kesilib, oflayn shablonga
    tushib qolardi).
  * 429/503 xatolarida kutib qayta urinish, model topilmasa - zaxira model.

Kalit bo'lmasa yoki internet ishlamasa - content_engine (oflayn) ishlatiladi.
"""

import contextvars
import json
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import config
import i18n


class AIError(Exception):
    """AI bilan aloqadagi xatolik. status - HTTP kodi (bo'lsa)."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


# Oxirgi xatolik va statistika ( /ai buyrug'i uchun )
_STATE = {"error": "", "model": "", "calls": 0, "last_ok": ""}
_LOCK = threading.Lock()

# "Avtomatik o'chirgich": ketma-ket uzilishlarda AI ni bir muddat chetlab o'tamiz
_BREAKER = {"fails": 0, "until": 0.0}


def _breaker_open():
    return time.time() < _BREAKER["until"]


def _breaker_fail():
    with _LOCK:
        _BREAKER["fails"] += 1
        if _BREAKER["fails"] >= 3:
            _BREAKER["until"] = time.time() + 45
            _BREAKER["fails"] = 0


def _breaker_success():
    with _LOCK:
        _BREAKER["fails"] = 0
        _BREAKER["until"] = 0.0


# Jarayon ko'rsatkichi: bot "qotib qolmagan"ini foydalanuvchiga ko'rsatish uchun
# ---------------------------------------------------------------------------
# Har bir generatsiya (foydalanuvchi so'rovi) uchun ALOHIDA holat:
# jarayon ko'rsatkichi, vaqt byudjeti va bekor qilish belgisi.
# contextvars orqali oqimlarga (thread) uzatiladi - shuning uchun bir nechta
# foydalanuvchi bir vaqtda ishlaganda bir-biriga xalaqit bermaydi.
# ---------------------------------------------------------------------------
_CTX = contextvars.ContextVar("ai_ctx", default=None)


def _new_ctx():
    return {
        "progress": {"stage": "", "done": 0, "total": 0, "started": 0.0, "note": ""},
        "deadline": 0.0,
        "cancel": threading.Event(),
    }


def progress_new():
    """Yangi generatsiya boshida (bot handlerida, vazifalar yaratilishidan OLDIN) chaqiriladi."""
    ctx = _new_ctx()
    _CTX.set(ctx)
    return ctx


def _ctx():
    ctx = _CTX.get()
    if ctx is None:
        ctx = _new_ctx()
        _CTX.set(ctx)
    return ctx


def cancel_current():
    """Joriy generatsiyani bekor qiladi (yangi AI so'rovlari yuborilmaydi)."""
    ctx = _CTX.get()
    if ctx is not None:
        ctx["cancel"].set()


def _cancelled():
    ctx = _CTX.get()
    return bool(ctx is not None and ctx["cancel"].is_set())


def _pmap(func, items, workers):
    """ThreadPoolExecutor.map, lekin joriy kontekstni (byudjet, jarayon) oqimlarga uzatadi."""
    ctx = contextvars.copy_context()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(lambda item: ctx.copy().run(func, item), items))


def progress_reset(stage="", total=0):
    p = _ctx()["progress"]
    with _LOCK:
        p.update(stage=stage, done=0, total=total, started=time.time(), note="")


def progress_step(plus=1, stage=None, total=None):
    p = _ctx()["progress"]
    with _LOCK:
        if stage is not None:
            p["stage"] = stage
        if total is not None:
            p["total"] = total
        p["done"] += plus


def progress_snapshot():
    ctx = _CTX.get()
    with _LOCK:
        if ctx is not None:
            snap = dict(ctx["progress"])
        else:
            snap = {"stage": "", "done": 0, "total": 0, "started": 0.0, "note": ""}
    if snap.get("started"):
        snap["elapsed"] = time.time() - snap["started"]
    else:
        snap["elapsed"] = 0
    return snap


# Umumiy vaqt byudjeti (ai_document / ai_presentation ichida tekshiriladi)
def _start_budget(seconds=None):
    _ctx()["deadline"] = time.time() + max(30, int(seconds or config.AI_BUDGET))


def _stop_budget():
    _ctx()["deadline"] = 0.0


def _remaining():
    ctx = _CTX.get()
    if ctx is None or not ctx["deadline"]:
        return None
    return ctx["deadline"] - time.time()


def _budget_over():
    rem = _remaining()
    return rem is not None and rem <= 0


def _guard():
    """Bekor qilingan yoki vaqt tugagan bo'lsa - yangi so'rov yubormaymiz."""
    if _cancelled():
        raise AIError("Bekor qilindi")
    if _budget_over():
        raise AIError("AI vaqti tugadi")


def _can_retry():
    """Ixtiyoriy qayta yozish uchun vaqt yetarlimi (yana bitta to'liq so'rov sig'sa)."""
    rem = _remaining()
    return rem is None or rem > 35


def _req_timeout(t):
    """Bitta so'rovning kutish vaqti qolgan byudjetdan oshib ketmasin."""
    rem = _remaining()
    if rem is None:
        return t
    return max(10, min(t, int(rem) + 3))


def last_error():
    return _STATE["error"]


def _remember(**kwargs):
    with _LOCK:
        _STATE.update(kwargs)


def _bump_calls():
    with _LOCK:
        _STATE["calls"] += 1


SYSTEM = (
    "Sen O'zbekiston oliy o'quv yurtlari uchun akademik ishlar (referat, "
    "mustaqil ish, prezentatsiya) yozadigan mutaxassissan. "
    "Har bir gap mavzuga oid bo'lishi shart: aniq atama, texnologiya nomi, "
    "jarayon yoki amaliy misol keltiriladi. "
    "Umumiy, bo'sh gaplar (\"katta ahamiyatga ega\", \"dolzarb hisoblanadi\") "
    "yozilmaydi. "
    "MA'LUMOT ANIQLIGI QOIDALARI (eng muhim): "
    "1) Faqat keng ma'lum, ishonchli faktlarni yoz. "
    "2) Uydirma statistika, foiz, o'lchov, sana, reyting va raqam YOZMA. "
    "3) Uydirma tadqiqot, universitet, muassasa yoki olim nomini YOZMA; "
    "faqat dunyoga mashhur, aniq mavjud nomlarni ishlat. "
    "4) Aniq raqam o'rniga sifat ifodasini ishlat: \"sezilarli darajada\", "
    "\"ko'plab tadbirlar\", \"amaliyotda keng qo'llanadi\". "
    "5) Ishonching komil bo'lmasa - mavzuning umumiy, tekshirilgan "
    "tomonlarini yoz, to'qima. "
    "Faqat so'ralgan JSON ni qaytarasan, hech qanday izoh qo'shmaysan."
)

# O'zbekcha mavzudan mazmunli so'zlarni ajratish uchun to'xtatuvchi so'zlar
_STOP = set(
    "va bilan uchun ham bu shu shunday ammo lekin yoki yana har bir kabi "
    "bo'yicha orqali emas eng juda ko'p o'z uning ular biz siz men deb esa "
    "chunki agar keyin oldin hozir yil yillarda asosiy masala muammo "
    "nima qanday qaysi necha sifat natija jarayon tizim soha rivoj "
    "shuningdek jami yana zarur kerak lozim".split()
)


# ---------------------------------------------------------------------------
# 1. Holat
# ---------------------------------------------------------------------------
def ai_available():
    return bool(config.AI_ENABLED)


def provider_name():
    if config.GEMINI_API_KEY:
        return f"Gemini ({config.GEMINI_MODEL})"
    if config.OPENAI_API_KEY:
        return f"OpenAI-mos ({config.AI_MODEL})"
    return "Oflayn"


def mask_key(key):
    if not key:
        return "—"
    return key[:6] + "…" + key[-4:] if len(key) > 12 else "…"


def status_info():
    """ /ai buyrug'i uchun batafsil holat. """
    return {
        "enabled": ai_available(),
        "provider": provider_name(),
        "key": mask_key(config.GEMINI_API_KEY or config.OPENAI_API_KEY),
        "model": _STATE["model"] or config.GEMINI_MODEL,
        "calls": _STATE["calls"],
        "last_error": _STATE["error"],
        "last_ok": _STATE["last_ok"],
    }


# ---------------------------------------------------------------------------
# 2. HTTP
# ---------------------------------------------------------------------------
def _http_json(url, payload, headers, timeout=None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout or config.AI_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:500]
        if exc.code in (401, 403) and (
            "ACCESS_TOKEN_TYPE_UNSUPPORTED" in detail or "API_KEY_INVALID" in detail
        ):
            raise AIError(
                "AI kaliti qabul qilinmadi. Yangi \"AQ.\" turidagi kalit hozircha "
                "Gemini API'da ishlamayapti - keys.txt ichida OpenRouter "
                "(OPENAI_API_KEY + OPENAI_BASE_URL) dan foydalanib ko'ring.",
                status=exc.code,
            ) from exc
        raise AIError(f"API xatosi {exc.code}: {detail}", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise AIError(f"Internetga ulanmadi: {exc.reason}") from exc
    except Exception as exc:  # noqa: BLE001
        raise AIError(f"Ulanish xatosi: {exc}") from exc


def _gemini_models():
    models = [config.GEMINI_MODEL] + list(config.GEMINI_MODEL_FALLBACKS)
    out = []
    for m in models:
        m = (m or "").strip()
        if m and m not in out:
            out.append(m)
    return out


def _gemini_once(model, prompt, max_tokens, json_mode, system, temperature, timeout=None):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={config.GEMINI_API_KEY}"
    )
    gen = {
        "temperature": temperature,
        "maxOutputTokens": int(max_tokens),
        "topP": 0.95,
    }
    if json_mode:
        gen["responseMimeType"] = "application/json"
    # 2.5 flash uchun "o'ylash"ni o'chiramiz - aks holda javob kesiladi
    if "2.5" in model and "pro" not in model.lower():
        gen["thinkingConfig"] = {"thinkingBudget": 0}

    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
               "generationConfig": gen}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    try:
        data = _http_json(url, payload, {"Content-Type": "application/json"}, timeout=timeout)
    except AIError as exc:
        # Ba'zi modellar thinkingConfig yoki json rejimini qabul qilmaydi
        if exc.status == 400 and "thinkingConfig" in gen:
            gen.pop("thinkingConfig", None)
            payload["generationConfig"] = gen
            data = _http_json(url, payload, {"Content-Type": "application/json"}, timeout=timeout)
        else:
            raise

    cand = (data.get("candidates") or [{}])[0]
    finish = cand.get("finishReason")
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))

    if not text.strip():
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise AIError(f"AI so'rovni rad etdi ({block})", status=400)
        raise AIError("AI bo'sh javob qaytardi", status=503)
    if finish == "MAX_TOKENS":
        raise AIError("Javob to'liq sig'madi (MAX_TOKENS)", status=-1)
    if finish == "SAFETY":
        raise AIError("AI xavfsizlik filtri ishga tushdi", status=400)
    return text


def _openai_once(model, prompt, max_tokens, json_mode, system, temperature, timeout=None,
                base_url=None, api_key=None):
    base = (base_url or config.OPENAI_BASE_URL).rstrip("/")
    url = base + "/chat/completions"
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": int(max_tokens),
        "messages": [
            {"role": "system", "content": system or SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key or config.OPENAI_API_KEY}",
    }
    try:
        data = _http_json(url, payload, headers, timeout=timeout)
    except AIError as exc:
        if exc.status == 400 and "response_format" in payload:
            payload.pop("response_format", None)
            data = _http_json(url, payload, headers, timeout=timeout)
        else:
            raise
    try:
        choice = data["choices"][0]
        text = choice["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIError("AI bo'sh javob qaytardi")
    if choice.get("finish_reason") == "length":
        raise AIError("Javob to'liq sig'madi (length)", status=-1)
    return text


# Balans/kalit xatosi bergan provayderlar (sessiyada qayta sinalmaydi)
_DEAD = {}
_DEAD_LOCK = threading.Lock()


def _is_dead(name):
    with _DEAD_LOCK:
        return bool(_DEAD.get(name))


def _mark_dead(name, reason=""):
    with _DEAD_LOCK:
        _DEAD[name] = reason or "xato"


def _call(prompt, max_tokens=8000, json_mode=True, system=None, temperature=None,
          timeout=None, models=None, attempts=None):
    """Bitta AI so'rovi.

    timeout   - bitta so'rov uchun kutish vaqti (soniya)
    models    - sinaladigan modellar ro'yxati (berilmasa - standart zaxiralar)
    attempts  - har bir model uchun urinishlar soni

    Ketma-ket 2 marta internet uzilsa - 90 soniya davomida tez qaytaradi
    (bot osilib qolmasligi uchun "avtomatik o'chirgich").
    """
    temperature = config.AI_TEMPERATURE if temperature is None else temperature
    if attempts is None:
        attempts = max(1, config.AI_ATTEMPTS)
    timeout = timeout or config.AI_TIMEOUT

    _guard()
    if _breaker_open():
        raise AIError("AI vaqtincha ishlamaydi (internet yoki limit) - oflayn rejim")

    _bump_calls()

    last_status = None
    if config.GEMINI_API_KEY:
        errors = []
        tokens = max_tokens
        model_list = [m for m in (models or _gemini_models()[:2]) if m]
        for model in model_list:
            for attempt in range(max(1, attempts)):
                _guard()
                try:
                    text = _gemini_once(
                        model, prompt, tokens, json_mode, system, temperature, _req_timeout(timeout)
                    )
                    _remember(model=model)
                    _breaker_success()
                    return text
                except AIError as exc:
                    errors.append(f"{model}: {exc}")
                    last_status = exc.status
                    if exc.status == -1 and attempt < attempts - 1:
                        tokens = int(tokens * 1.6)
                        continue
                    if exc.status in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                        time.sleep(3 * (attempt + 1))
                        continue
                    if exc.status is None and not _budget_over():
                        _breaker_fail()
                    break
        msg = errors[-1] if errors else "AI javob bermadi"
        _remember(error=msg[:400])
        if not (config.OPENAI_API_KEY and last_status in (401, 403)):
            raise AIError(msg)
        # Gemini kaliti rad etildi (masalan, yangi "AQ." turi) - muqobil provayderga o'tamiz
        _remember(error="Gemini kaliti qabul qilinmadi - zaxira provayder ishlatilmoqda")

    if config.OPENAI_API_KEY:
        models = []
        for m in [config.AI_MODEL] + list(getattr(config, "AI_MODEL_FALLBACKS", []) or []):
            m = (m or "").strip()
            if m and m not in models:
                models.append(m)
        provs = [("", config.OPENAI_BASE_URL, config.OPENAI_API_KEY, models)]
        bk_key = getattr(config, "OPENAI_API_KEY_BACKUP", "")
        if bk_key and bk_key != config.OPENAI_API_KEY:
            bk_models = []
            for m in [config.AI_MODEL_BACKUP] + list(getattr(config, "AI_MODEL_BACKUP_FALLBACKS", []) or []):
                m = (m or "").strip()
                if m and m not in bk_models:
                    bk_models.append(m)
            provs.append(("zaxira: ", config.OPENAI_BASE_URL_BACKUP, bk_key, bk_models))

        errors = []
        for pname, base_url, api_key, prov_models in provs:
            if not prov_models:
                continue
            if _is_dead(pname or "asosiy"):
                continue
            for model in prov_models:
                tokens = max_tokens
                for attempt in range(max(1, attempts)):
                    _guard()
                    try:
                        text = _openai_once(
                            model, prompt, tokens, json_mode, system, temperature, _req_timeout(timeout),
                            base_url=base_url, api_key=api_key,
                        )
                        _remember(model=pname + model)
                        _breaker_success()
                        return text
                    except AIError as exc:
                        errors.append(f"{pname}{model}: {exc}")
                        if exc.status == -1 and attempt < attempts - 1:
                            tokens = int(tokens * 1.6)
                            continue
                        if exc.status in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                            time.sleep(3 * (attempt + 1))
                            continue
                        if exc.status is None and not _budget_over():
                            _breaker_fail()
                        if exc.status in (401, 402, 403):
                            _mark_dead(pname or "asosiy", str(exc)[:120])
                        break
        msg = errors[-1] if errors else "AI javob bermadi"
        _remember(error=msg[:400])
        raise AIError(msg)

    raise AIError("AI kaliti sozlanmagan")


# ---------------------------------------------------------------------------
# 3. JSON yordamchilari
# ---------------------------------------------------------------------------
def _parse_json(text):
    if not text:
        raise AIError("Bo'sh javob")
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise AIError("AI javobi JSON formatida emas")


def _json_call(prompt, max_tokens=6000, system=SYSTEM, temperature=None, **kwargs):
    """JSON so'raydi; buzuq chiqsa bir marta qayta so'raydi."""
    text = _call(prompt, max_tokens, True, system, temperature, **kwargs)
    try:
        return _parse_json(text)
    except AIError:
        retry = (
            prompt
            + "\n\nMUHIM: javobni faqat yaroqli, to'liq JSON ko'rinishida qaytar. "
              "Matnni qisqartir, lekin JSON ni buzma."
        )
        return _parse_json(_call(retry, max_tokens, True, system, temperature, **kwargs))


def _s(value, limit=None):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if limit and len(text) > limit:
        cut = text[:limit]
        dot = cut.rfind(". ")
        text = cut[:dot + 1] if dot > limit * 0.6 else cut.rstrip() + "…"
    return text


def _list(value, max_items=None):
    if isinstance(value, str):
        value = [value]
    out = [_s(v) for v in (value or []) if _s(v)]
    return out[:max_items] if max_items else out


def _clean_topic(topic):
    return re.sub(r"\s+", " ", (topic or "").strip()).strip("«»\"' ")


def _wc(text):
    return len(re.findall(r"[\w'’-]+", text or ""))


def _keywords(topic, limit=6):
    words = re.findall(r"[A-Za-zÀ-ÿА-яЎўҚқҒғҲҳ'’-]+", (topic or "").lower())
    good = []
    for w in words:
        w = w.strip("-'’")
        if len(w) >= 4 and w not in _STOP and w not in good:
            good.append(w)
    return good[:limit]


def _has_keyword(text, keywords):
    low = (text or "").lower()
    return any(k in low for k in keywords)


def _chapter_count(size):
    size = int(size)
    if size <= 8:
        return 3
    if size <= 12:
        return 4
    if size <= 20:
        return 5
    if size <= 25:
        return 6
    return 7


# ---------------------------------------------------------------------------
# 4. Reja
# ---------------------------------------------------------------------------
def _src(info, limit=3500):
    """Manba (kitob/maqola) matni bo'lsa, promptga qo'shiladigan blok."""
    text = str((info or {}).get("manba") or "").strip()
    if len(text) < 120:
        return ""
    return ("\nMANBA MATN (mazmun asosan shundan olinsin, so'zma-so'z ko'chirilmasin):\n"
            + text[:limit] + "\n")


def ai_plan(topic, kind="referat", size=10, lang="uz"):
    """Mavzu bo'yicha bo'limlar rejasini tuzadi (foydalanuvchi tasdiqlaydi)."""
    topic = _clean_topic(topic)
    n = _chapter_count(int(size))
    WHAT = {
        "prezentatsiya": "prezentatsiya slaydlari",
        "referat": "referat",
        "mustaqil": "mustaqil ish",
        "amaliy": "amaliy hisobot",
        "tezis": "ilmiy tezis",
        "maqola": "ilmiy maqola",
    }
    what = WHAT.get(kind, "referat")
    prompt = f"""Mavzu: «{topic}»
Vazifa: shu mavzuda {size} {('slayd' if kind == 'prezentatsiya' else 'bet')} hajmli {what} uchun mantiqiy reja tuz.

Talablar:
- Aynan {n} ta bo'lim, har biri 3-7 so'z, o'zbek tilida, mavzuga xos.
- 1-bo'lim nazariy asos, o'rtadagilar tahlil va amaliyot, oxirgisi aniq va amaliy xulosa bo'lsin.
- Bo'limlar bir-birini takrorlamasin va «Kirish», «Xulosa» deb nomlanmasin.
- Umumiy bo'limlar («Tarixi», «Tushunchasi») o'rniga mavzuning aniq jihatlarini yoz.

{i18n.ai_directive(lang)}

Faqat shu JSON: {{"plan": ["bo'lim nomi", "..."]}}"""
    # Reja uchun qisqa muddat: javob kelmasa bot osilib qolmasin
    data = _json_call(
        prompt,
        max_tokens=1200,
        temperature=0.5,
        timeout=config.PLAN_TIMEOUT,
        models=[config.GEMINI_MODEL] if config.GEMINI_API_KEY else None,
        attempts=1,
    )
    plan = _list((data or {}).get("plan"), 8)
    plan = [re.sub(r"^[\d\s.\-)]+", "", p).strip() for p in plan if len(p) > 3]
    if len(plan) < 3:
        raise AIError("Reja juda qisqa chiqdi")
    return plan[:n]


def _fix_titles(chapters):
    """Rejada «taklif» bobini odatiy akademik nomga almashtiradi."""
    for ch in chapters:
        low = str(ch.get("title") or "").lower()
        if "taklif" in low or "tavsiya" in low:
            ch["title"] = "Amaliy xulosa va natijalar"
    return chapters


def _outline(topic, info, plan, kind, size, lang="uz"):
    """Bo'limlar va kichik bo'limlar nomlari."""
    n_ch = _chapter_count(int(size))

    if plan:
        chapters = [{"title": _s(re.sub(r"^[\d\s.\-)]+", "", p), 90)} for p in plan[:7]]
        chapters = _fix_titles(chapters)
        chapters = [c for c in chapters if len(c["title"]) > 3]
    else:
        prompt = f"""MAVZU: «{topic}»
FAN: {info.get('fan') or '—'}
{_src(info, 1500)}

Aynan {n_ch} ta bob va har biriga 2-3 ta kichik bo'lim nomini tuz.
Har nom 3-7 so'z, o'zbek tilida, mavzuga xos, takrorlanmasin.

{i18n.ai_directive(lang)}

JSON: {{"chapters": [{{"title": "bob nomi", "subs": ["kichik bo'lim", "..."]}}]}}"""
        data = _json_call(prompt, max_tokens=1200, temperature=0.5)
        chapters = []
        for ch in (data or {}).get("chapters") or []:
            if not isinstance(ch, dict):
                continue
            title = _s(ch.get("title"), 90)
            subs = [_s(s, 90) for s in _list(ch.get("subs"), 3) if len(_s(s)) > 3]
            if title and len(subs) >= 2:
                chapters.append({"title": title, "subs": subs})

    if len(chapters) < 2:
        raise AIError("AI reja tuzilmasini bermadi")

    # Har bobda kamida 2 kichik bo'lim bo'lsin
    for ch in chapters:
        subs = ch.get("subs") or []
        while len(subs) < 2:
            base = ch["title"]
            subs.append(f"{base} bo'yicha tahlil" if not subs else f"{base}: amaliy jihatlar")
        ch["subs"] = subs[:3]
    return chapters[:7]


# ---------------------------------------------------------------------------
# 5. Bobni yozish
# ---------------------------------------------------------------------------
def _write_chapter(topic, info, ch_title, sub_titles, words_per_sub, keywords, _depth=0, kind="referat", lang="uz"):
    subs_txt = "\n".join(f"{i+1}. {t}" for i, t in enumerate(sub_titles))
    must = ", ".join(f"«{k}»" for k in keywords) if keywords else "mavzu atamalari"

    WORK = {
        "referat": "REFERAT",
        "mustaqil": "MUSTAQIL ISH",
        "amaliy": "AMALIY HISOBOT",
        "tezis": "TEZIS",
        "maqola": "ILMIY MAQOLA",
    }
    prompt = f"""Sen talaba uchun {WORK.get(kind, "REFERAT")} yozasan.

MAVZU: «{topic}»
FAN: {info.get('fan') or '—'}
{_src(info)}
BOB: «{ch_title}»
KICHIK BO'LIMLAR:
{subs_txt}

TALABLAR:
1. Har bir kichik bo'lim uchun 2-3 ta paragraf yoz. Har paragraf 60-85 so'z (3-5 gap).
2. Har bir paragrafda mavzuga oid aniq atama, texnologiya yoki usul nomi, imkon bo'lsa davlat/muassasa misoli bo'lsin.
3. Quyidagi atamalardan albatta foydalan: {must}.
4. TAQIQLANADI: umumiy bo'sh gaplar («katta ahamiyatga ega», «dolzarb hisoblanadi», «kundan-kunga ortib bormoqda»), bir xil boshlanadigan gaplar, takrorlar.
5. Ishonching komil bo'lmagan raqam yoki sanani yozma — o'rniga sifat bahosi ishlat.
6. Har bir kichik bo'lim uchun ingliz tilida rasm qidiruv so'zi (image_query, 2-5 so'z, aynan shu bo'lim mazmunini tasvirlaydigan aniq obyekt) va o'zbekcha qisqa izoh (image_caption) yoz.

JSON:
{{"subs": [{{"title": "...", "paras": ["...", "..."], "image_query": "...", "image_caption": "..."}}]}}

{i18n.ai_directive(lang)}

Faqat JSON qaytar. Kichik bo'limlar soni aynan {len(sub_titles)} ta bo'lsin."""

    data = _json_call(prompt, max_tokens=5200, temperature=0.65)
    raw_subs = (data or {}).get("subs") or []

    subs = []
    for i, sub in enumerate(raw_subs):
        if not isinstance(sub, dict):
            continue
        title = sub_titles[i] if i < len(sub_titles) else _s(sub.get("title"), 90)
        paras = [p for p in _list(sub.get("paras")) if _wc(p) >= 25]
        if not paras:
            continue
        subs.append({
            "title": title,
            "paras": paras[:4],
            "image_query": _s(sub.get("image_query"), 80),
            "image_caption": _s(sub.get("image_caption"), 120),
        })

    # Yetishmagan kichik bo'limlarni to'ldirishga urinamiz
    if len(subs) < len(sub_titles):
        have = {s["title"] for s in subs}
        missing = [t for t in sub_titles if t not in have]
        if missing and _can_retry():
            subs.extend(_retry_missing(topic, info, ch_title, missing, words_per_sub, keywords, lang))

    if not subs:
        raise AIError("Bob matni yozilmadi")

    total = sum(_wc(p) for s in subs for p in s["paras"])
    text_all = " ".join(p for s in subs for p in s["paras"])

    # Sifat: hajm yoki mavzu atamalari yetishmasa - qayta yozamiz
    need_words = int(words_per_sub * len(sub_titles) * 0.45)
    need_retry = total < need_words or (keywords and not _has_keyword(text_all, keywords))
    if need_retry and _depth == 0 and _can_retry():
        try:
            again = _write_chapter(
                topic, info, ch_title, sub_titles, int(words_per_sub * 1.15), keywords, _depth=1, lang=lang
            )
            again_total = sum(_wc(p) for s in again for p in s["paras"])
            if again_total > total or not _has_keyword(text_all, keywords):
                subs = again
        except AIError:
            pass

    return subs


def _retry_missing(topic, info, ch_title, missing, words_per_sub, keywords, lang="uz"):
    """Yetishmayotgan kichik bo'limlarni alohida so'rov bilan yozadi."""
    subs_txt = "\n".join(f"{i+1}. {t}" for i, t in enumerate(missing))
    must = ", ".join(f"«{k}»" for k in keywords) if keywords else "mavzu atamalari"
    prompt = f"""MAVZU: «{topic}»  |  BOB: «{ch_title}»
Quyidagi kichik bo'limlar uchun matn yoz:
{subs_txt}

Har biriga 2-3 paragraf, har paragraf {int(words_per_sub*0.4)}-{int(words_per_sub*0.6)} so'z.
Mavzuga oid aniq atama va misollar bo'lsin: {must}.
Har biriga inglizcha image_query va o'zbekcha image_caption yoz.

{i18n.ai_directive(lang)}

JSON: {{"subs": [{{"title": "...", "paras": ["..."], "image_query": "...", "image_caption": "..."}}]}}"""
    try:
        data = _json_call(prompt, max_tokens=4000, temperature=0.65)
    except AIError:
        return []
    out = []
    for i, sub in enumerate((data or {}).get("subs") or []):
        if not isinstance(sub, dict):
            continue
        paras = [p for p in _list(sub.get("paras")) if _wc(p) >= 25]
        if not paras:
            continue
        out.append({
            "title": missing[i] if i < len(missing) else _s(sub.get("title"), 90),
            "paras": paras[:4],
            "image_query": _s(sub.get("image_query"), 80),
            "image_caption": _s(sub.get("image_caption"), 120),
        })
    return out


# ---------------------------------------------------------------------------
# 6. Hujjat (referat / mustaqil ish)
# ---------------------------------------------------------------------------
def ai_document(topic, info, size=10, plan=None, kind="referat", lang="uz"):
    """Kirish + boblar (bo'lim-bo'lim) + xulosa + adabiyotlar."""
    topic = _clean_topic(topic)
    info = info or {}
    size = max(6, min(30, int(size)))
    keywords = _keywords(topic)

    progress_reset("reja va bo'limlar tuzilmoqda")
    _start_budget()
    chapters = _outline(topic, info, plan, kind, size, lang)
    progress_reset(f"matn yozilmoqda: {len(chapters)} bob", total=len(chapters))
    n_subs = sum(len(c["subs"]) for c in chapters)
    total_words = int(max(1200, (size - 3) * 300))
    words_per_sub = max(150, int(total_words / max(1, n_subs)))

    # Boblarni parallel yozamiz (3 tadan - bepul limitga mos)
    def work(ch):
        try:
            if _budget_over():
                return []
            return _write_chapter(
                topic, info, ch["title"], ch["subs"], words_per_sub, keywords, kind=kind, lang=lang
            )
        except AIError:
            return []
        finally:
            progress_step(plus=1)

    written = _pmap(work, chapters, min(6, len(chapters) + 2))

    norm_chapters = []
    for ch, subs in zip(chapters, written):
        if subs:
            norm_chapters.append({"title": ch["title"], "subs": subs})

    if not norm_chapters:
        raise AIError("Boblar matni yozilmadi")
    # Boblarning kamida yarmi yozilmagan bo'lsa - hujjat juda kichik chiqadi
    if len(norm_chapters) < max(1, (len(chapters) + 1) // 2):
        raise AIError("AI sekinlashdi - boblarning yarmidan ko'pi yozilmadi")

    # Boblar tayyor: vaqt byudjeti tugagan bo'lsa ham ularni TASHLAB YUBORMAYMIZ,
    # kirish va xulosa uchun alohida qisqa vaqt ajratamiz.
    progress_reset("kirish va xulosa yozilmoqda")
    _breaker_success()  # bu so'rov majburiy: avvalgi uzilishlar uni to'smasin
    _start_budget(40)
    intro, conclusion, refs = _intro_outro(topic, info, [c["title"] for c in norm_chapters], keywords)

    # Nomlarni akademik ko'rinishga keltiramiz
    romans = ["I", "II", "III", "IV", "V", "VI"]
    final = []
    for ci, ch in enumerate(norm_chapters[:6]):
        title = ch["title"].upper()
        title = re.sub(r"^(I{1,3}|IV|V|VI)[\.\s]+BOB[\.\s]*", "", title).strip()
        subs = []
        for si, sub in enumerate(ch["subs"][:4]):
            st = re.sub(r"^\d+(\.\d+)*[\.\s]*", "", sub["title"]).strip()
            st = st[:1].upper() + st[1:]
            subs.append({
                "title": f"{ci + 1}.{si + 1}. {st}",
                "paras": sub["paras"],
                "image_query": sub["image_query"],
                "image_caption": sub["image_caption"],
            })
        final.append({"title": f"{romans[ci]} BOB. {title}", "subs": subs})

    data = {
        "kind": "referat",
        "topic": topic,
        "info": info,
        "lang": lang,
        "source": "ai",
        "keywords": keywords,
        "intro": intro,
        "chapters": final,
        "conclusion": conclusion,
        "references": refs,
        "words": sum(_wc(p) for ch in final for s in ch["subs"] for p in s["paras"]),
    }
    _stop_budget()
    return data


def _intro_outro(topic, info, chapter_titles, keywords):
    """Kirish, xulosa va adabiyotlar ro'yxati (bitta so'rov)."""
    chs = "\n".join(f"{i+1}. {t}" for i, t in enumerate(chapter_titles))
    must = ", ".join(f"«{k}»" for k in keywords) if keywords else "mavzu atamalari"
    prompt = f"""MAVZU: «{topic}»
FAN: {info.get('fan') or '—'}
BOBILAR:
{chs}

Yoz:
1) intro — 3 paragraf: (a) mavzuning dolzarbligi va 2-3 aniq muammo, (b) maqsad va vazifalar, (c) tadqiqot usullari. Har paragraf 80-120 so'z.
2) conclusion — 3 paragraf: aniq natijalar, amaliy tavsiyalar, istiqbol. Har paragraf 80-110 so'z.
3) references — 7-8 ta REAL mavjud manba (darslik, monografiya, ilmiy maqola, rasmiy sayt). Muallif, nom, shahar, nashriyot, yil. Uydirma manba yozma.

Matnda {must} atamalaridan foydalan, umumiy bo'sh gaplardan qoch.

JSON: {{"intro": ["..."], "conclusion": ["..."], "references": ["..."]}}"""
    data = _json_call(prompt, max_tokens=4000, temperature=0.6)
    intro = _list((data or {}).get("intro"))[:4]
    conclusion = _list((data or {}).get("conclusion"))[:4]
    refs = _list((data or {}).get("references"), 10)

    if len(intro) < 2:
        raise AIError("Kirish qismi yozilmadi")
    if not conclusion:
        conclusion = [
            "O'rganilgan materiallar asosida mavzu bo'yicha asosiy xulosalar shakllantirildi."
        ]
    if not refs:
        refs = ["Mavzu bo'yicha ma'ruza matnlari."]
    return intro, conclusion, refs


# ---------------------------------------------------------------------------
# 7. Prezentatsiya
# ---------------------------------------------------------------------------
def ai_presentation(topic, info, size=10, plan=None, lang="uz"):
    topic = _clean_topic(topic)
    info = info or {}
    size = max(7, min(30, int(size)))
    body = max(4, size - 4)
    keywords = _keywords(topic)

    progress_reset("slayd sarlavhalari tuzilmoqda")
    _start_budget()
    titles = _slide_titles(topic, info, plan, body, lang)
    progress_reset(f"slayd matni yozilmoqda: {len(titles)} ta", total=len(titles))
    slides = _slide_batches(topic, info, titles, keywords, lang)
    if len(slides) < 3:
        raise AIError("Slaydlar yozilmadi")

    progress_reset("xulosa va adabiyotlar")
    conclusion, refs = _slide_conclusion(topic, info, [s["title"] for s in slides], keywords, lang)

    plan_slide = {
        "title": "Reja",
        "bullets": (_list(plan, 7) if plan else [s["title"] for s in slides[:6]]),
    }

    data = {
        "kind": "prezentatsiya",
        "topic": topic,
        "info": info,
        "lang": lang,
        "source": "ai",
        "keywords": keywords,
        "plan": plan_slide["bullets"],
        "plan_slide": plan_slide,
        "slides": slides[:body],
        "conclusion": conclusion,
        "references": refs,
    }
    _stop_budget()
    return data


def _slide_titles(topic, info, plan, body, lang="uz"):
    plan_txt = ""
    if plan:
        plan_txt = "\nTASDIQLANGAN REJA (albatta qamrab olinsin):\n" + "\n".join(
            f"{i+1}. {p}" for i, p in enumerate(_list(plan, 7))
        )

    prompt = f"""MAVZU: «{topic}»
FAN: {info.get('fan') or '—'}{plan_txt}

Aynan {body} ta slayd sarlavhasini tuz (2-6 so'z, o'zbek tilida, takrorlanmasin).
Slaydlar mantiqiy ketma-ketlikda bo'lsin: muammo -> tahlil -> yechim -> amaliyot.
Reja berilgan bo'lsa, uning har bir punkti alohida slayd bo'lsin, qolganlari bilan to'ldir.

{i18n.ai_directive(lang)}

JSON: {{"titles": ["...", "..."]}}"""
    data = _json_call(prompt, max_tokens=900, temperature=0.5)
    titles = [_s(t, 70) for t in _list((data or {}).get("titles"), body) if len(_s(t)) > 3]

    # Reja berilgan bo'lsa, uning punktlari albatta qatnashsin
    if plan:
        for p in _list(plan, 7):
            p = re.sub(r"^[\d\s.\-)]+", "", p).strip()
            if p and len(p) > 3 and not any(p.lower()[:12] in t.lower() for t in titles):
                titles.insert(0, p)

    if len(titles) < 3:
        raise AIError("Slayd sarlavhalari tuzilmadi")
    return titles[:body]


def _slide_batches(topic, info, titles, keywords, lang="uz"):
    """Slaydlarni 4 tadan guruhlab yozadi (sifat uchun)."""
    must = ", ".join(f"«{k}»" for k in keywords) if keywords else "mavzu atamalari"
    chunks = [titles[i:i + 4] for i in range(0, len(titles), 4)]

    def work(chunk):
        lst = "\n".join(f"{i+1}. {t}" for i, t in enumerate(chunk))
        prompt = f"""MAVZU: «{topic}»
{_src(info, 2500)}
SLAYDLAR:
{lst}

Har bir slayd uchun 4-5 punkt yoz (har punkt 6-12 so'z). Punktlar ANIQ bo'lsin: atama, texnologiya nomi, raqam yoki xulosa.
TAQIQLANADI: «katta ahamiyatga ega», «dolzarb hisoblanadi» kabi bo'sh gaplar.
{must} atamalaridan foydalan.
Har slaydga inglizcha image_query (2-5 so'z) va o'zbekcha image_caption yoz.

{i18n.ai_directive(lang)}

JSON: {{"slides": [{{"title": "...", "bullets": ["..."], "image_query": "...", "image_caption": "..."}}]}}"""
        try:
            data = _json_call(prompt, max_tokens=2600, temperature=0.6)
        except AIError:
            return []
        out = []
        for i, s in enumerate((data or {}).get("slides") or []):
            if not isinstance(s, dict):
                continue
            bullets = _list(s.get("bullets"), 5)
            title = _s(s.get("title"), 70) or (chunk[i] if i < len(chunk) else "")
            if title and len(bullets) >= 2:
                out.append({
                    "title": title,
                    "bullets": bullets,
                    "image_query": _s(s.get("image_query"), 80),
                    "image_caption": _s(s.get("image_caption"), 120),
                })
        return out

    parts = _pmap(work, chunks, 2)

    slides = []
    for part in parts:
        slides.extend(part)

    # Yetishmagan slaydlarni yakka tartibda to'ldirishga urinamiz
    if len(slides) < len(titles):
        have = {s["title"].strip().lower() for s in slides}
        missing = [t for t in titles if t.strip().lower() not in have]
        for t in missing[:3]:
            one = _slide_one(topic, t, must)
            if one:
                slides.append(one)
    return slides


def _slide_one(topic, title, must):
    """Bitta slaydni alohida yozadi (zaxira yo'l)."""
    prompt = f"""MAVZU: «{topic}»
SLAYD: «{title}»

Shu slayd uchun 4-5 punkt yoz (har punkt 6-12 so'z), aniq atama va xulosa bilan.
{must} atamalaridan foydalan.
Inglizcha image_query (2-5 so'z) va o'zbekcha image_caption yoz.

JSON: {{"slides": [{{"title": "{title}", "bullets": ["..."], "image_query": "...", "image_caption": "..."}}]}}"""
    try:
        data = _json_call(prompt, max_tokens=1000, temperature=0.6)
    except AIError:
        return None
    for s in (data or {}).get("slides") or []:
        if not isinstance(s, dict):
            continue
        bullets = _list(s.get("bullets"), 5)
        if len(bullets) >= 2:
            return {
                "title": _s(s.get("title"), 70) or title,
                "bullets": bullets,
                "image_query": _s(s.get("image_query"), 80),
                "image_caption": _s(s.get("image_caption"), 120),
            }
    return None


def _slide_conclusion(topic, info, slide_titles, keywords, lang="uz"):
    must = ", ".join(f"«{k}»" for k in keywords) if keywords else "mavzu atamalari"
    lst = "\n".join(f"- {t}" for t in slide_titles[:8])
    prompt = f"""MAVZU: «{topic}»
SLAYLAR:
{lst}

1) conclusion — 4-5 punkt: aniq natija va amaliy tavsiyalar (6-14 so'z).
2) references — 5-6 ta REAL manba (muallif, nom, shahar, nashriyot, yil).
{must} atamalaridan foydalan.

{i18n.ai_directive(lang)}

JSON: {{"conclusion": ["..."], "references": ["..."]}}"""
    data = _json_call(prompt, max_tokens=1600, temperature=0.6)
    conclusion = _list((data or {}).get("conclusion"), 6)
    refs = _list((data or {}).get("references"), 8)
    return conclusion or [("Mavzu bo'yicha xulosalar shakllantirildi." if lang == "uz" else ("Выводы по теме сформулированы." if lang == "ru" else "Conclusions on the topic have been drawn."))], refs


# ---------------------------------------------------------------------------
# 8. Ulanishni tekshirish
# ---------------------------------------------------------------------------
def test_connection():
    """AI kaliti ishlayotganini tekshiradi. (ok, xabar) qaytaradi."""
    if not ai_available():
        return False, "AI kaliti topilmadi (keys.txt faylida GEMINI_API_KEY yo'q)"
    try:
        data = _json_call(
            'Faqat shu JSON ni qaytar: {"ok": true, "echo": "salom"}',
            max_tokens=200,
            temperature=0.1,
        )
        if isinstance(data, dict):
            _remember(last_ok=time.strftime("%Y-%m-%d %H:%M:%S"), error="")
            return True, f"Ulanish muvaffaqiyatli ({provider_name()})"
        return True, f"Ulanish muvaffaqiyatli ({provider_name()})"
    except AIError as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"Kutilmagan xato: {exc}"


def ai_solve(subject, problem, sample="", lang="uz"):
    """
    Misol/masalani qadam-baqadam yechadi.
    Qaytaradi: dict {"answer", "steps": [...], "final"}
    """
    subject = _s(subject, 60) or "Matematika"
    problem = str(problem or "").strip()
    if len(problem) < 3:
        raise AIError("Masala matni juda qisqa")

    sample_block = ""
    if sample and len(str(sample).strip()) > 20:
        sample_block = (
            "\nNAMUNA (shu uslubda, shu tartibda yech):\n" + str(sample)[:2500] + "\n"
        )

    prompt = f"""Sen {subject} fanidan tajribali o'qituvchisan. Talaba yuborgan misol/masalani yechib ber.

FAN: {subject}
MASALA:
{problem[:2500]}
{sample_block}
TALABLAR:
1. Yechimni qadam-baqadam yoz: har qadamda nima qilinayotgani va formula.
2. Formulalarni oddiy matnda yoz (masalan: S = v * t, x = (-b ± sqrt(b^2-4ac)) / 2a).
3. Har qadam qisqa bo'lsin (1-3 gap yoki formula).
4. Oxirida aniq javob: "Javob: ..." (o'lchov birligi bilan).
5. Agar masala shartida ma'lumot yetishmasa - shuni ayt va taxmin qilib yechma.
6. Matn {i18n.ai_directive(lang)} bo'lsin.

JSON: {{"given": "...", "formula": "...", "steps": ["...", "..."], "final": "..."}}"""

    data = _json_call(prompt, max_tokens=1800, temperature=0.3)
    if not isinstance(data, dict):
        raise AIError("AI yechim qaytarmadi")
    steps = [_s(x, 400) for x in _list(data.get("steps"), 12) if _s(x)]
    final = _s(data.get("final"), 400)
    if not steps and not final:
        raise AIError("Yechim bo'sh chiqdi")
    return {
        "given": _s(data.get("given"), 400),
        "formula": _s(data.get("formula"), 400),
        "steps": steps,
        "final": final,
    }
