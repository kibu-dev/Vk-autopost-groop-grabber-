import logging
import os
import json
import asyncio
import requests
import vk_api
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from config import *

DRAFTS_FILE = "tg_drafts.json"
app = Flask(__name__)
tg_app = ApplicationBuilder().token(TG_BOT_TOKEN).build()
seen = set()

def load_drafts():
    try:
        with open(DRAFTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_drafts(data):
    with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def vk_upload_photo(file_bytes):
    vk = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    upload = vk.photos.getWallUploadServer(group_id=GROUP_ID)
    r = requests.post(upload["upload_url"], files={"photo": file_bytes}).json()
    if 'photo' in r and r['photo']:
        saved = vk.photos.saveWallPhoto(photo=r['photo'], server=r['server'], hash=r['hash'], group_id=GROUP_ID)
        if saved:
            p = saved[0]
            return f"photo{p['owner_id']}_{p['id']}"
    return None

def vk_post(text, attachments, publish_time=None):
    vk = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    try:
        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text or "",
            attachments=",".join(attachments) if attachments else None,
            from_group=1,
            publish_date=publish_time
        )
        return True
    except Exception as e:
        logging.error(f"VK post error: {e}")
        return False

def next_hour_timestamp():
    now = datetime.now()
    nxt = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return int(nxt.timestamp())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    if msg.message_id in seen:
        return
    seen.add(msg.message_id)

    text = msg.text or msg.caption or ""
    photos = []

    if msg.photo:
        file = await msg.photo[-1].get_file()
        file_bytes = await file.download_as_bytearray()
        photos.append(file_bytes.hex())

    drafts = load_drafts()
    drafts[str(msg.message_id)] = {"text": text, "photos": photos}
    save_drafts(drafts)

    attachments = []
    for ph_hex in photos:
        att = vk_upload_photo(bytes.fromhex(ph_hex))
        if att:
            attachments.append(att)

    pub_time = next_hour_timestamp()
    if vk_post(text, attachments, pub_time):
        pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
        logging.info(f"📡 TG → VK: запланирован на {pub_str}")
    else:
        logging.error("📡 Ошибка отправки в VK")

tg_app.add_handler(MessageHandler(filters.ALL, handle_message))

@app.route(f"/webhook/{TG_BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, tg_app.bot)
        tg_app.update_queue.put_nowait(update)
        return "ok"
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "error"

def run_webhook():
    if not TG_BOT_TOKEN:
        logging.warning("📡 ТГ-бот: не указан TG_BOT_TOKEN")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(tg_app.initialize())

    webhook_url = f"{DOMAIN}/webhook/{TG_BOT_TOKEN}"
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/setWebhook?url={webhook_url}")
        logging.info(f"📡 Webhook ответ: {r.json()}")
    except Exception as e:
        logging.error(f"📡 Не удалось установить webhook: {e}")

    logging.info(f"📡 Flask запущен, webhook: {webhook_url}")
    app.run(host="0.0.0.0", port=5000)
