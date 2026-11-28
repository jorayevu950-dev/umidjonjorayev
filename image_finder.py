# -*- coding: utf-8 -*-
"""
Rasm qidiruvchi modul.

Rasmlar BEPUL va kalitsiz manbalardan olinadi:
  1) Wikimedia Commons (birinchi navbatda) - mavzuga eng mos rasmlar
  2) Openverse (zaxira) - CC litsenziyali rasmlar

Har bir rasm yuklab olinadi, o'lchami normallashtiriladi va
manba (litsenziya) ma'lumoti bilan qaytariladi.
"""

import io
import json
import os
import re
import urllib.parse
import urllib.request

from PIL import Image

UA = "TalabaYordamchisi/2.0 (talaba loyihasi; kontakt: student@example.com)"
TIMEOUT = 25
IMAGES_TOTAL_TIMEOUT = 40  # barcha rasmlar uchun umumiy chegara (soniya)

BAD_WORDS = (
    "logo", "icon", "coat of arms", "flag", "seal", "emblem",
    "signature", "portrait of", "poster", "cover",
)


# ---------------------------------------------------------------------------
# 1. Qidiruv
# ---------------------------------------------------------------------------
def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def _commons(query, limit):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": str(limit * 3),
        "gsrnamespace": "6",
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1400",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    pages = (data.get("query") or {}).get("pages") or {}
    items = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        info = (page.get("imageinfo") or [{}])[0]
        title = page.get("title", "").replace("File:", "")
        low = title.lower()
        if any(b in low for b in BAD_WORDS):
            continue
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        w, h = info.get("width") or 0, info.get("height") or 0
        if w < 640 or h < 400:
            continue
        ratio = w / h if h else 0
        if not (1.05 <= ratio <= 2.6):
            continue
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value") or "Wikimedia Commons"
        items.append({
            "url": info.get("thumburl") or info.get("url"),
            "title": title,
            "credit": f"Manba: Wikimedia Commons, {lic}",
            "page": info.get("descriptionurl") or "",
        })
        if len(items) >= limit:
            break
    return items


def _openverse(query, limit):
    params = {
        "q": query,
        "page_size": str(max(5, limit * 4)),
        "license": "cc0,pdm,by,by-sa",
        "mature": "false",
    }
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    items = []
    for r in data.get("results") or []:
        title = (r.get("title") or "").strip()
        if any(b in title.lower() for b in BAD_WORDS):
            continue
        w, h = r.get("width") or 0, r.get("height") or 0
        if w and h:
            ratio = w / h
            if w < 640 or not (1.05 <= ratio <= 2.6):
                continue
        lic = (r.get("license") or "CC").upper()
        items.append({
            "url": r.get("url"),
            "title": title or query,
            "credit": f"Manba: Openverse, {lic}",
            "page": r.get("foreign_landing_url") or "",
        })
        if len(items) >= limit:
            break
    return items


def search(query, limit=2):
    """Rasm havolalarini qaytaradi. Xato bo'lsa bo'sh ro'yxat."""
    query = re.sub(r"\s+", " ", query or "").strip()
    if not query:
        return []
    for func in (_commons, _openverse):
        try:
            found = func(query, limit)
            if found:
                return [f for f in found if f.get("url")]
        except Exception:  # noqa: BLE001
            continue
    return []


# ---------------------------------------------------------------------------
# 2. Yuklab olish va normallashtirish
# ---------------------------------------------------------------------------
def download(url, out_path, max_width=1400):
    """Rasmni yuklab, JPEG ko'rinishida saqlaydi. Muvaffaqiyatli bo'lsa path."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(9 * 1024 * 1024)
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        if img.width > max_width:
            height = int(img.height * max_width / img.width)
            img = img.resize((max_width, height), Image.LANCZOS)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path, "JPEG", quality=88, optimize=True)
        return out_path
    except Exception:  # noqa: BLE001
        return None


def _one_task(args):
    """Bitta so'rov: mos rasmni topib yuklaydi."""
    i, query, caption, out_dir, prefix, used = args
    query = re.sub(r"\s+", " ", query or "").strip()
    if not query:
        return None
    tries = [query]
    words = [w for w in re.split(r"[^A-Za-z0-9']+", query) if len(w) > 2]
    if len(words) > 2:
        tries.append(" ".join(words[:2]))
    qwords = set()
    for q in tries:
        qwords |= {w.lower() for w in re.split(r"[^A-Za-z0-9']+", q) if len(w) > 3}

    for q in tries:
        scored = []
        for item in search(q, limit=4):
            title = item.get("title") or ""
            key = (title or item["url"])[:80]
            if key in used:
                continue
            low = title.lower()
            scored.append((sum(1 for w in qwords if w in low), item, key))
        scored.sort(key=lambda x: -x[0])
        if not scored or scored[0][0] == 0:
            continue  # mavzuga mos rasm yo'q - xato rasm qo'ymaymiz
        for score, item, key in scored:
            if score <= 0:
                continue
            path = os.path.join(out_dir, "%s_%d.jpg" % (prefix, i))
            saved = download(item["url"], path)
            if not saved:
                continue
            used.add(key)
            return {
                "index": i,
                "path": saved,
                "caption": caption or item.get("title") or query,
                "credit": item.get("credit", ""),
            }
    return None


def fetch_for_queries(queries, out_dir, limit=None, prefix="img"):
    """Har bir so'rov uchun bitta rasm - PARALLEL yuklanadi."""
    from concurrent.futures import ThreadPoolExecutor

    used = set()
    tasks = []
    for i, (query, caption) in enumerate(queries):
        if limit and i >= limit:
            break
        tasks.append((i, query, caption, out_dir, prefix, used))
    if not tasks:
        return []
    # Rasmlar uchun umumiy vaqt chegarasi: sekin tarmoqda butun ishni kutdirmasin
    # (aks holda tayyor matn ham "vaqt tugadi" bilan yo'qoladi).
    from concurrent.futures import wait as _wait

    pool = ThreadPoolExecutor(max_workers=min(5, len(tasks)))
    futs = [pool.submit(_one_task, t) for t in tasks]
    done, _ = _wait(futs, timeout=IMAGES_TOTAL_TIMEOUT)
    got = []
    for f in done:
        try:
            r = f.result()
        except Exception:  # noqa: BLE001
            continue
        if r:
            got.append(r)
    pool.shutdown(wait=False, cancel_futures=True)
    return sorted(got, key=lambda r: r["index"])
