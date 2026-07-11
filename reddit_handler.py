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


def _download_image(url, retries=3):
    """Скачивает картинку с несколькими попытками. Возвращает bytes или None."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://www.reddit.com/',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    }
    for attempt in range(retries):
        try:
            resp = req.get(url, timeout=25, headers=headers)
            if resp.status_code == 200 and len(resp.content) >= 1000:
                return resp.content
            logging.warning(f"📸 Попытка {attempt+1}: статус {resp.status_code}, "
                            f"размер {len(resp.content)} байт — {url[:70]}")
        except Exception as e:
            logging.warning(f"📸 Попытка {attempt+1} ошибка: {e} — {url[:70]}")
    return None


def upload_photos_to_vk(image_urls):
    """Загружает фото из Reddit через messagesUploadServer (работает с групповым токеном)."""
    attachments = []
    errors = []

    for idx, img_url in enumerate(image_urls[:10]):
        logging.info(f"📸 [{idx+1}/{len(image_urls[:10])}] Скачиваю: {img_url[:80]}")
        img_data = _download_image(img_url)

        if img_data is None:
            msg = f"Не удалось скачать фото #{idx+1}: {img_url[:70]}"
            errors.append(msg)
            logging.warning(f"📸 ⚠️ {msg}")
            continue

        logging.info(f"📸 Скачано {len(img_data)//1024} КБ, загружаю в VK...")

        try:
            # 1. getMessagesUploadServer (доступен групповому токену)
            server = vk_api("photos.getMessagesUploadServer", {"group_id": GROUP_ID})
            if not server:
                errors.append(f"getMessagesUploadServer failed: {img_url[:60]}")
                continue

            # 2. Загружаем на сервер VK
            up = req.post(server["upload_url"],
                          files={'photo': ('img.jpg', img_data, 'image/jpeg')},
                          timeout=30).json()
            if 'photo' not in up:
                errors.append(f"VK upload вернул неожиданный ответ для фото #{idx+1}")
                logging.warning(f"📸 Ответ сервера: {up}")
                continue

            # 3. saveMessagesPhoto
            saved = vk_api("photos.saveMessagesPhoto", {
                "photo": up["photo"],
                "server": up["server"],
                "hash": up["hash"],
            })

            if saved and len(saved) > 0:
                att = f"photo{saved[0]['owner_id']}_{saved[0]['id']}"
                if saved[0].get("access_key"):
                    att += f"_{saved[0]['access_key']}"
                attachments.append(att)
                logging.info(f"📸 ✅ Фото #{idx+1} сохранено: {att}")
            else:
                errors.append(f"saveMessagesPhoto вернул пустой ответ для фото #{idx+1}")

        except Exception as e:
            errors.append(f"Исключение при загрузке фото #{idx+1}: {str(e)[:80]}")
            logging.error(f"📸 Исключение: {e}")

    logging.info(f"📸 Итого: {len(attachments)} загружено, {len(errors)} ошибок")
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

        # Сразу заливаем фото в VK — Reddit URL-ы (особенно preview.redd.it) протухают
        vk_attachments = []
        upload_errors = []
        if images:
            logging.info(f"📱 Заливаю {len(images)} фото в VK сразу при получении поста...")
            vk_attachments, upload_errors = upload_photos_to_vk(images)
            if upload_errors:
                logging.warning(f"📱 Ошибки заливки: {upload_errors}")
            logging.info(f"📱 Залито {len(vk_attachments)}/{len(images)} фото")

        draft_id = str(int(datetime.now().timestamp()))
        drafts[draft_id] = {
            "title": translated_title,
            "text": translated_text,
            "original_text": text,
            "original_title": title,
            "images": images,                    # оригинальные URL на случай повторной попытки
            "vk_attachments": vk_attachments,   # готовые VK-строки (используются при публикации)
            "url": url,
            "author": author,
            "subreddit": subreddit,
            "source": "reddit",
            "status": "pending",
            "translated": True
        }
        save_drafts(drafts)

        photo_status = f"✅ {len(vk_attachments)}/{len(images)} фото" if images else "без фото"
        if upload_errors:
            photo_status += f" (⚠️ {len(upload_errors)} не загрузилось)"
        msg = (f"📱 Новый пост с Reddit!\n"
               f"📌 {translated_title[:100]}\n"
               f"🖼 Фото: {photo_status}\n\n"
               f"Заходи в раздел «📱 Reddit» для обработки.")

        vk_api("messages.send", {
            "user_id": ADMIN_ID,
            "message": msg,
            "random_id": 0,
            "group_id": GROUP_ID,
        })

        logging.info(f"📱 Reddit пост {draft_id} сохранён, вложений: {len(vk_attachments)}")
        return "ok"
    except Exception as e:
        logging.error(f"Reddit error: {e}")
        return "error", 500


def run_reddit_handler():
    logging.info("📱 Reddit handler запущен на порту 3000")
    app.run(host="0.0.0.0", port=3000)
