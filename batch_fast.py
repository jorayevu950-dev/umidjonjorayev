# -*- coding: utf-8 -*-
"""Toplu ishlar + admin eloni."""
import asyncio, time, os
import config, workflow
from make_docx import create_document
from make_pptx import create_presentation
_QUEUE = asyncio.Queue()
_WORKER_STARTED = False
_BATCH = {}
async def _worker(app):
    while True:
        job = await _QUEUE.get()
        try: await _do_one(app, job)
        except Exception as e:
            try: await app.bot.send_message(job["chat_id"], "Xato: " + str(e)[:200])
            except Exception: pass
        _QUEUE.task_done()
async def _do_one(app, job):
    data, mode, note = await asyncio.to_thread(workflow.build_work, job["kind"], job["topic"], {}, 10, None, False, job["stamp"], False, "uz", 0, "")
    path = await asyncio.to_thread(_save, data, job["kind"])
    with open(path, "rb") as f: await app.bot.send_document(chat_id=job["chat_id"], document=f, caption="Tayyor: " + job["topic"])
    try: os.remove(path)
    except OSError: pass
    st = _BATCH.get(job["user_id"])
    if st:
        st["done"] += 1
        if st["done"] >= st["total"]:
            await app.bot.send_message(job["chat_id"], "Hammasi tayyor: " + str(st["done"]) + "/" + str(st["total"]) + " ta ish.")
            _BATCH.pop(job["user_id"], None)
def _save(data, kind):
    if kind == "prezentatsiya": return create_presentation(data, config.OUT_DIR, stamp=data.get("stamp",""))
    return create_document(data, config.OUT_DIR)
async def _ensure_worker(app):
    global _WORKER_STARTED
    if not _WORKER_STARTED:
        _WORKER_STARTED = True
        asyncio.create_task(_worker(app))
async def toplam_cmd(update, context):
    await _ensure_worker(context.application)
    context.user_data["await_toplam"] = True
    context.user_data["toplam_kind"] = "mustaqil"
    await update.message.reply_text("TOPLU REJIM: 10 tagacha mavzuni har birini alohida qatorda yozib yuboring. Keyin bot fonda tayyorlab yuboradi.")
async def elon_cmd(update, context):
    from bot import storage as _storage, _admin_id
    if update.effective_user.id != _admin_id(): await update.message.reply_text("Faqat admin uchun."); return
    text = update.message.text.partition(" ")[2].strip()
    if not text: await update.message.reply_text("Foydalanish: /elon Matn"); return
    _storage.set_meta("elon", text)
    await update.message.reply_text("Elon saqlandi. Yuborish: /elon_yuborish")
async def elon_send_cmd(update, context):
    from bot import storage as _storage, _admin_id
    if update.effective_user.id != _admin_id(): await update.message.reply_text("Faqat admin uchun."); return
    text = _storage.get_meta("elon", "")
    if not text: await update.message.reply_text("Avval /elon bilan matn yozing."); return
    ids = _storage.all_user_ids()
    ok = 0
    for uid in ids:
        try: await context.bot.send_message(uid, "ELON:" + chr(10) + chr(10) + text); ok += 1; await asyncio.sleep(0.05)
        except Exception: pass
    await update.message.reply_text("Elon " + str(ok) + " kishiga yuborildi.")
async def enqueue_batch(app, user_id, chat_id, kind, topics):
    await _ensure_worker(app)
    base = str(int(time.time()))
    _BATCH[user_id] = {"total": len(topics), "done": 0}
    for i, t in enumerate(topics): await _QUEUE.put({"user_id": user_id, "chat_id": chat_id, "kind": kind, "topic": t, "stamp": base + "_" + str(user_id) + "_" + str(i)})
    return len(topics)
async def toplam_text(update, context):
    if not context.user_data.get("await_toplam"): return None
    topics = [l.strip() for l in (update.message.text or "").splitlines() if l.strip()][:10]
    if len(topics) < 1: return None
    context.user_data["await_toplam"] = False
    kind = context.user_data.get("toplam_kind", "mustaqil")
    await enqueue_batch(context.application, update.effective_user.id, update.effective_chat.id, kind, topics)
    await update.message.reply_text("Qabul qilindi: " + str(len(topics)) + " ta mavzu. Fonda tayyorlanmoqda, har biri alohida keladi.")
    return None
