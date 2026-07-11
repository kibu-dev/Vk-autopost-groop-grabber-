# reddit_handler.py — полностью

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


def _upload_single_photo(img_data, idx_label=""):
    """
    Загружает одно фото в VK.
    Сначала пробует getWallUploadServer (правильный альбом для постов).
    Если токен не имеет scope photos — fallback на getMessagesUploadServer.
    """
    # Попытка 1: wall upload (нужен scope photos в токене)
    server = vk_api("photos.getWallUploadServer", {"group_id": GROUP_ID})
    if server:
        try:
            up = req.post(server["upload_url"],
                          files={'photo': ('img.jpg', img_data, 'image/jpeg')},
                          timeout=30).json()
            if 'photo' in up:
                saved = vk_api("photos.saveWallPhoto", {
                    "group_id": GROUP_ID,
                    "photo": up["photo"],
                    "server": up["server"],
                    "hash": up["hash"],
                })
                if saved and len(saved) > 0:
                    att = f"photo{saved[0]['owner_id']}_{saved[0]['id']}"
                    if saved[0].get("access_key"):
                        att += f"_{saved[0]['access_key']}"
                    logging.info(f"📸 ✅ Фото {idx_label} → wall album: {att}")
                    return att
        except Exception as e:
            logging.warning(f"📸 saveWallPhoto исключение: {e}")
    else:
        logging.warning(
            "📸 getWallUploadServer недоступен (нет scope 'photos' в токене?). "
            "Fallback → messagesUploadServer."
        )

    # Fallback: messages upload
    server2 = vk_api("photos.getMessagesUploadServer", {"group_id": GROUP_ID})
    if not server2:
        logging.error(f"📸 Оба метода недоступны для фото {idx_label}")
        return None

    up2 = req.post(server2["upload_url"],
                   files={'photo': ('img.jpg', img_data, 'image/jpeg')},
                   timeout=30).json()
    if 'photo' not in up2:
        logging.warning(f"📸 messages upload вернул неожиданный ответ: {up2}")
        return None

    saved2 = vk_api("photos.saveMessagesPhoto", {
        "photo": up2["photo"],
        "server": up2["server"],
        "hash": up2["hash"],
    })
    if saved2 and len(saved2) > 0:
        att = f"photo{saved2[0]['owner_id']}_{saved2[0]['id']}"
        if saved2[0].get("access_key"):
            att += f"_{saved2[0]['access_key']}"
        logging.warning(f"📸 ⚠️ Фото {idx_label} сохранено в альбом сообщений (fallback): {att}")
        return att

    return None


def upload_photos_to_vk(image_urls):
    """Загружает фото из Reddit. Сначала wall-альбом, затем fallback на messages."""
    attachments = []
    errors = []

    for i, img_url in enumerate(image_urls[:10], 1):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.reddit.com/'
            }
            img_resp = req.get(img_url, timeout=20, headers=headers)
            if img_resp.status_code != 200 or len(img_resp.content) < 1000:
                errors.append(f"HTTP {img_resp.status_code}: {img_url[:60]}")
                continue

            result = _upload_single_photo(img_resp.content, f"{i}/{len(image_urls[:10])}")
            if result:
                attachments.append(result)
                logging.info(f"📸 Фото {i} загружено: {img_url[:60]}...")
            else:
                errors.append(f"Upload failed: {img_url[:60]}")

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

        # Заранее загружаем фото и сохраняем vk_attachments в черновик
        vk_attachments = []
        if images:
            logging.info(f"📸 Предзагрузка {len(images)} фото для нового Reddit поста...")
            vk_attachments, errors = upload_photos_to_vk(images)
            if errors:
                logging.warning(f"📸 Ошибки предзагрузки: {errors}")
            logging.info(f"📸 Предзагружено {len(vk_attachments)} фото")

        drafts = load_drafts()
        draft_id = str(int(datetime.now().timestamp()))
        drafts[draft_id] = {
            "title": translated_title,
            "text": translated_text,
            "original_text": text,
            "original_title": title,
            "images": images,
            "vk_attachments": vk_attachments,
            "url": url,
            "author": author,
            "subreddit": subreddit,
            "source": "reddit",
            "status": "pending",
            "translated": True
        }
        save_drafts(drafts)

        msg = f"📱 Новый пост с Reddit!\n📌 {translated_title[:100]}\n🖼 Фото: {len(images)} шт."
        if vk_attachments:
            msg += f" (загружено {len(vk_attachments)})"
        msg += "\n\nЗаходи в раздел «📱 Reddit» для обработки."

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
