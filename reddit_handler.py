import logging
import json
from datetime import datetime
from flask import Flask, request
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from config import *

REDDIT_DRAFTS_FILE = "reddit_drafts.json"
app = Flask(__name__)

def load_drafts():
    try:
        with open(REDDIT_DRAFTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_drafts(data):
    with open(REDDIT_DRAFTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

@app.route("/reddit", methods=["POST"])
def reddit_post():
    try:
        data = request.get_json(force=True)
        title = data.get("title", "")
        text = data.get("text", "")
        images = data.get("images", [])
        url = data.get("url", "")
        author = data.get("author", "")
        subreddit = data.get("subreddit", "")

        drafts = load_drafts()
        draft_id = str(int(datetime.now().timestamp()))
        drafts[draft_id] = {
            "title": title,
            "text": text,
            "original_text": text,
            "images": images,
            "url": url,
            "author": author,
            "subreddit": subreddit,
            "source": "reddit",
            "status": "pending",
            "translated": False
        }
        save_drafts(drafts)

        # Уведомление админу — просто информируем
        msg = f"📱 Новый пост с Reddit!\n📌 {title[:100]}\n🖼 Фото: {len(images)} шт.\n\nЗаходи в раздел «📱 Reddit» для обработки."

        vk_group = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
        vk_group.messages.send(
            user_id=ADMIN_ID,
            message=msg,
            random_id=0,
            group_id=GROUP_ID
        )

        logging.info(f"📱 Reddit пост {draft_id} сохранён")
        return "ok"
    except Exception as e:
        logging.error(f"Reddit error: {e}")
        return "error", 500

def run_reddit_handler():
    logging.info("📱 Reddit handler запущен на порту 3000")
    app.run(host="0.0.0.0", port=3000)
