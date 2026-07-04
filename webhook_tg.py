import logging
import os
import json
import requests
import vk_api
from datetime import datetime, timedelta
from flask import Flask, request
from config import *

DRAFTS_FILE = "tg_drafts.json"
app = Flask(__name__)

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

@app.route("/test_tg", methods=["GET"])
def test_tg():
    try:
        r = requests.get("https://api.telegram.org", timeout=5)
        return f"OK: {r.status_code}"
    except Exception as e:
        return f"ERROR: {e}"

@app.route(f"/webhook/{TG_BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        
        if "message" not in data:
            return "ok"
        
        msg = data["message"]
        msg_id = msg.get("message_id")
        text = msg.get("text") or msg.get("caption", "")
        photos = msg.get("photo", [])
        
        logging.info(f"📡 TG: {text[:100]} | фото: {len(photos)}")
        
        drafts = load_drafts()
        drafts[str(msg_id)] = {"text": text, "photos": len(photos)}
        save_drafts(drafts)
        
        if photos:
            file_id = photos[-1]["file_id"]
            file_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getFile?file_id={file_id}"
            file_resp = requests.get(file_url).json()
            file_path = file_resp.get("result", {}).get("file_path")
            
            if file_path:
                download_url = f"https://api.telegram.org/file/bot{TG_BOT_TOKEN}/{file_path}"
                file_bytes = requests.get(download_url).content
                
                attachments = []
                att = vk_upload_photo(file_bytes)
                if att:
                    attachments.append(att)
                
                pub_time = next_hour_timestamp()
                if vk_post(text, attachments, pub_time):
                    pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
                    logging.info(f"📡 TG → VK: запланирован на {pub_str}")
        else:
            pub_time = next_hour_timestamp()
            if vk_post(text, [], pub_time):
                pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
                logging.info(f"📡 TG → VK (текст): запланирован на {pub_str}")
        
        return "ok"
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "error"

def run_webhook():
    if not TG_BOT_TOKEN:
        logging.warning("📡 ТГ-бот: не указан TG_BOT_TOKEN")
        return

    webhook_url = f"{DOMAIN}/webhook/{TG_BOT_TOKEN}"
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/setWebhook?url={webhook_url}")
        logging.info(f"📡 Webhook: {r.json()}")
    except Exception as e:
        logging.error(f"📡 Не удалось установить webhook: {e}")

    logging.info(f"📡 Flask запущен, порт 3000")
    app.run(host="0.0.0.0", port=3000)
