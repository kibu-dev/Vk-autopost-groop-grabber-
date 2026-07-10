import logging
import json
from datetime import datetime
from flask import Flask, request
import vk_api
import requests as req
from config import *
from ai_poster import translate_text, is_russian

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

def upload_photos_to_vk(image_urls):
    """Загружает фото в VK и возвращает список attachment-строк"""
    if not image_urls:
        return [], []
    
    attachments = []
    errors = []
    
    try:
        vk_group = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
    except Exception as e:
        return [], [f"VK auth error: {e}"]

    for img_url in image_urls[:10]:
        try:
            headers_list = [
                {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.reddit.com/'
                },
                {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36',
                    'Accept': 'image/*',
                    'Referer': 'https://www.reddit.com/'
                }
            ]
            resp = None
            for headers in headers_list:
                try:
                    resp = req.get(img_url, timeout=20, headers=headers)
                    if resp.status_code == 200 and len(resp.content) >= 1000:
                        break
                except:
                    continue
            
            if not resp or resp.status_code != 200 or len(resp.content) < 1000:
                errors.append(f"HTTP {resp.status_code if resp else 'timeout'}: {img_url[:60]}")
                continue
            
            up_server = vk_group.photos.getWallUploadServer(group_id=GROUP_ID)
            up = req.post(up_server['upload_url'], files={'photo': ('r.jpg', resp.content, 'image/jpeg')}).json()
            
            if 'photo' in up and up['photo']:
                saved = vk_group.photos.saveWallPhoto(photo=up['photo'], server=up['server'], hash=up['hash'], group_id=GROUP_ID)
                if saved:
                    attachments.append(f"photo{saved[0]['owner_id']}_{saved[0]['id']}")
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
