# -*- coding: utf-8 -*-
"""
Talaba yordamchisi — sayt (Flask).

Ishga tushirish:
    pip install -r requirements.txt
    python app.py
So'ng brauzerda: http://127.0.0.1:5000

Sayt bot bilan bir xil uslubda: sariq fon, oq kartochkalar, ko'k balans bloki.
Buyurtmalar SQLite bazasiga yoziladi (orders.db).
"""

import os
import sqlite3
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH") or os.path.join(BASE, "orders.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "talaba-sayt-maxfiy-kalit-almashtiring")

SERVICES = [
    {"slug": "hujjat", "icon": "🪪", "name": "Hujjat rasmi", "hint": "Talaba guvohnomasi uchun rasm"},
    {"slug": "obyektivka", "icon": "📋", "name": "Obyektivka", "hint": "O'qish joyidan ma'lumotnoma"},
    {"slug": "mustaqil", "icon": "📝", "name": "Mustaqil ish", "hint": "Titul varaq va reja bilan"},
    {"slug": "referat", "icon": "📄", "name": "Referat", "hint": "Kirish, bo'limlar, xulosa"},
    {"slug": "amaliyot", "icon": "📚", "name": "Amaliyot hisoboti", "hint": "Kundalik va xulosa bilan"},
    {"slug": "tezis", "icon": "📰", "name": "Tezis", "hint": "1-2 betlik ilmiy tezis"},
    {"slug": "maqola", "icon": "📄", "name": "Ilmiy maqola", "hint": "Annotatsiya va adabiyotlar"},
    {"slug": "kazus", "icon": "⚖️", "name": "Kazus yechish", "hint": "Huquqiy vaziyat tahlili"},
    {"slug": "tarjima", "icon": "🌐", "name": "Tarjima", "hint": "Matnni uz/ru/en ga o'girish"},
    {"slug": "ocr", "icon": "🔍", "name": "Rasmdan matn", "hint": "Skan va rasmdan matn olish"},
    {"slug": "prezentatsiya", "icon": "📊", "name": "Prezentatsiya", "hint": "Har slaydda rasm bilan"},
    {"slug": "skaner", "icon": "📷", "name": "Skaner", "hint": "Hujjatni tozalab skanerlash"},
    {"slug": "pdf", "icon": "📑", "name": "Rasmdan PDF", "hint": "Rasmlarni bitta PDF qilish"},
    {"slug": "arxiv", "icon": "🗜", "name": "Arxiv (ZIP)", "hint": "Fayllarni zip qilish"},
    {"slug": "gpa", "icon": "🎓", "name": "GPA hisoblash", "hint": "O'rtacha ballni hisoblash"},
]

SUBJECTS = ["Matematika", "Fizika", "Kimyo", "Biologiya", "Informatika",
            "Iqtisodiyot", "Tarix", "Filologiya", "Huquq", "Boshqa"]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   contact TEXT,
                   subject TEXT,
                   service TEXT NOT NULL,
                   topic TEXT NOT NULL,
                   size TEXT,
                   note TEXT,
                   created_at TEXT NOT NULL
               )"""
        )


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if name:
            session["name"] = name[:40]
        return redirect(url_for("index"))
    name = session.get("name", "")
    with db() as conn:
        rows = conn.execute(
            "SELECT service, topic, created_at FROM orders ORDER BY id DESC LIMIT 6"
        ).fetchall()
    return render_template("index.html", services=SERVICES, name=name, recent=rows)


@app.route("/xizmat/<slug>", methods=["GET", "POST"])
def service(slug):
    item = next((s for s in SERVICES if s["slug"] == slug), None)
    if item is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        name = (request.form.get("name") or session.get("name") or "").strip()
        topic = (request.form.get("topic") or "").strip()
        if not name or len(topic) < 5:
            return render_template(
                "service.html", item=item, subjects=SUBJECTS,
                error="Ism va mavzuni to'ldiring (mavzu kamida 5 belgi).",
                form=request.form, name=session.get("name", ""),
            )
        session["name"] = name[:40]
        with db() as conn:
            conn.execute(
                "INSERT INTO orders (name, contact, subject, service, topic, size, note, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    name[:60], (request.form.get("contact") or "")[:40],
                    (request.form.get("subject") or "")[:40],
                    item["name"], topic[:200],
                    (request.form.get("size") or "")[:20],
                    (request.form.get("note") or "")[:1000],
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )
        return render_template("done.html", item=item, topic=topic, name=name)

    return render_template(
        "service.html", item=item, subjects=SUBJECTS, error="",
        form={}, name=session.get("name", ""),
    )


@app.route("/buyurtmalarim")
def my_orders():
    name = session.get("name", "")
    rows = []
    if name:
        with db() as conn:
            rows = conn.execute(
                "SELECT service, topic, size, created_at FROM orders WHERE name = ?"
                " ORDER BY id DESC LIMIT 30", (name,)
            ).fetchall()
    return render_template("orders.html", rows=rows, name=name)


# Baza jadvalini har ishga tushishda tayyorlab qo'yamiz
# (serverda gunicorn/WSGI orqali ishga tushganda ham kerak)
init_db()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
