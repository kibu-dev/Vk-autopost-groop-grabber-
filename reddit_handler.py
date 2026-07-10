import logging
import json
import requests as req
from datetime import datetime
from flask import Flask, request
from config import *
from ai_poster import translate_text, is_russian

REDDIT_DRAFTS_FILE = "reddit_drafts.json"
app = Flask(__name__)

VK_API_URL = "https://api.vk.com/method"


def vk_api_call(method, params):
    """Прямой вызов VK API через HTTP (работает с групповым токеном)."""
    params["access_token"] = GROUP_TOKEN
    params["v"] = "5.131"
    try:
        resp = req.get(f"{VK_API_URL}/{method}", params=params, timeout=30).json()
        if "error" in resp:
            logging.error(f"VK API error [{method}]: {resp['error']}")
            return None
        return resp.get("response")
    except Exception as e:
        logging.error(f"VK API exception [{method}]: {e}")
        return None


def load_drafts():
    try:
        with open(REDDIT_DRAFTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_drafts(data):
    with open(REDDIT_DRAFTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def upload_photos_to_vk(image_urls):
    """Загружает фото в VK через прямые HTTP-запросы (работает с групповым токеном)."""
    if not image_urls:
        return [], []

    attachments = []
    errors = []

    for img_url in image_urls[:10]:
        try:
            # 1. Получаем upload server
            server_resp = vk_api_call("photos.getWallUploadServer", {"group_id": GROUP_ID})
            if not server_resp:
                errors.append(f"getWallUploadServer failed: {img_url[:60]}")
                continue
            upload_url = server_resp["upload_url"]

            # 2. Скачиваем фото
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.reddit.com/'
            }
            img_resp = req.get(img_url, timeout=20, headers=headers)
            if img_resp.status_code != 200 or len(img_resp.content) < 1000:
                errors.append(f"HTTP {img_resp.status_code}: {img_url[:60]}")
                continue

            # 3. Загружаем на сервер VK
            up_resp = req.post(upload_url, files={'photo': ('r.jpg', img_resp.content, 'image/jpeg')}).json()

            if 'photo' not in up_resp:
                errors.append(f"Upload failed: {img_url[:60]}")
                continue

            # 4. Сохраняем фото
            save_resp = vk_api_call("photos.saveWallPhoto", {
                "group_id": GROUP_ID,
                "photo": up_resp["photo"],
                "server": up_resp["server"],
                "hash": up_resp["hash"],
            })

            if save_resp and len(save_resp) > 0:
                attachments.append(f"photo{save_resp[0]['owner_id']}_{save_resp[0]['id']}")
                logging.info(f"📸 Фото загружено: {img_url[:60]}...")
            else:
                errors.append(f"saveWallPhoto failed: {img_url[:60]}")

        except Exception as e:
            errors.append(f"{str(e)[:80]}: {img_url[:60]}")

    return attachments, errors


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

        # Авто-перевод
        translated_title = title
        translated_text = text

        if title and not is_russian(title):
            try:
                tr = translate_text(title)
                if tr:
                    translated_title = tr
                    logging.info(f"📱 Заголовок переведён: {title[:50]} → {tr[:50]}")
            except Exception as e:
                logging.error(f"📱 Ошибка перевода заголовка: {e}")

        if text and not is_russian(text):
            try:
                tr = translate_text(text)
                if tr:
                    translated_text = tr
                    logging.info(f"📱 Текст переведён: {text[:50]} → {tr[:50]}")
            except Exception as e:
                logging.error(f"📱 Ошибка перевода текста: {e}")

        drafts = load_drafts()
        draft_id = str(int(datetime.now().timestamp()))
        drafts[draft_id] = {
            "title": translated_title,
            "text": translated_text,
            "original_text": text,
            "original_title": title,
            "images": images,
            "url": url,
            "author": author,
            "subreddit": subreddit,
            "source": "reddit",
            "status": "pending",
            "translated": True
        }
        save_drafts(drafts)

        # Уведомление админу
        msg = f"📱 Новый пост с Reddit!\n📌 {translated_title[:100]}\n🖼 Фото: {len(images)} шт.\n\nЗаходи в раздел «📱 Reddit» для обработки."

        vk_api_call("messages.send", {
            "user_id": ADMIN_ID,
            "message": msg,
            "random_id": 0,
            "group_id": GROUP_ID,
        })

        logging.info(f"📱 Reddit пост {draft_id} сохранён")
        return "ok"
    except Exception as e:
        logging.error(f"Reddit error: {e}")
        return "error", 500


def run_reddit_handler():
    logging.info("📱 Reddit handler запущен на порту 3000")
    app.run(host="0.0.0.0", port=3000)
