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


def vk_api(method, params):
    """Прямой вызов VK API."""
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


def upload_photo_to_wall(image_url):
    """Загружает одно фото на стену группы через messagesUploadServer (работает с групповым токеном)."""
    try:
        # 1. Получаем upload server для сообщений (доступен групповому токену)
        server = vk_api("photos.getMessagesUploadServer", {"group_id": GROUP_ID})
        if not server:
            return None

        # 2. Скачиваем фото
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.reddit.com/'
        }
        img = req.get(image_url, timeout=20, headers=headers)
        if img.status_code != 200 or len(img.content) < 1000:
            return None

        # 3. Загружаем
        up = req.post(server["upload_url"],
                      files={'photo': ('img.jpg', img.content, 'image/jpeg')}).json()
        if 'photo' not in up:
            return None

        # 4. Сохраняем как фото сообщения
        saved = vk_api("photos.saveMessagesPhoto", {
            "photo": up["photo"],
            "server": up["server"],
            "hash": up["hash"],
        })
        if not saved or not saved[0]:
            return None

        # 5. Фото сохранено в альбом сообщений, теперь его можно прикрепить к посту на стене
        owner_id = saved[0]["owner_id"]
        photo_id = saved[0]["id"]
        access_key = saved[0].get("access_key", "")

        attachment = f"photo{owner_id}_{photo_id}"
        if access_key:
            attachment += f"_{access_key}"

        return attachment

    except Exception as e:
        logging.error(f"Upload error: {e}")
        return None


def upload_photos_to_vk(image_urls):
    """Загружает фото через messagesUploadServer."""
    if not image_urls:
        return [], []

    attachments = []
    errors = []

    for url in image_urls[:10]:
        result = upload_photo_to_wall(url)
        if result:
            attachments.append(result)
            logging.info(f"📸 Фото загружено: {url[:60]}...")
        else:
            errors.append(f"Failed: {url[:60]}")

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

        msg = f"📱 Новый пост с Reddit!\n📌 {translated_title[:100]}\n🖼 Фото: {len(images)} шт.\n\nЗаходи в раздел «📱 Reddit» для обработки."

        vk_api("messages.send", {
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
