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
    """Загружает фото через wall upload — как граббер."""
    try:
        # 1. Получаем сервер загрузки на стену
        server = req.get(
            "https://api.vk.com/method/photos.getWallUploadServer",
            params={
                "group_id": GROUP_ID,
                "access_token": GROUP_TOKEN,
                "v": "5.131"
            },
            timeout=30
        ).json()

        if "error" in server:
            logging.warning(f"📸 getWallUploadServer error #{idx_label}: {server['error']}")
            return None

        if "response" not in server:
            logging.error(f"📸 getWallUploadServer failed #{idx_label}")
            return None

        upload_url = server["response"]["upload_url"]

        # 2. Загружаем фото
        up = req.post(
            upload_url,
            files={"photo": ("photo.jpg", img_data, "image/jpeg")},
            timeout=60
        ).json()

        if not up.get("photo"):
            logging.warning(f"📸 VK не принял фото #{idx_label}: {up}")
            return None

        # 3. Сохраняем на стену
        saved = req.get(
            "https://api.vk.com/method/photos.saveWallPhoto",
            params={
                "group_id": GROUP_ID,
                "photo": up["photo"],
                "server": up["server"],
                "hash": up["hash"],
                "access_token": GROUP_TOKEN,
                "v": "5.131"
            },
            timeout=30
        ).json()

        if "response" in saved and saved["response"]:
            s = saved["response"][0]
            att = f"photo{s['owner_id']}_{s['id']}"
            if s.get("access_key"):
                att += f"_{s['access_key']}"
            logging.info(f"📸 ✅ Фото #{idx_label}: {att}")
            return att
        else:
            logging.error(f"📸 saveWallPhoto failed #{idx_label}: {saved}")
            return None

    except Exception as e:
        logging.error(f"📸 Ошибка загрузки #{idx_label}: {e}")
        return None


def upload_photos_to_vk(image_urls):
    """Загружает фото из Reddit на стену группы."""
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

            logging.info(f"📸 [{i}/{len(image_urls[:10])}] Скачиваю: {img_url[:60]}...")
            logging.info(f"📸 Скачано {len(img_resp.content)} байт, загружаю в VK...")

            result = _upload_single_photo(img_resp.content, f"{i}/{len(image_urls[:10])}")
            if result:
                attachments.append(result)
            else:
                errors.append(f"Не удалось сохранить фото #{i} в VK")

        except Exception as e:
            errors.append(f"{str(e)[:80]}: {img_url[:60]}")

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

        # Заранее загружаем фото при получении поста
        vk_attachments = []
        if images:
            logging.info(f"📸 Загружаю {len(images)} фото в VK сразу при получении поста...")
            vk_attachments, errors = upload_photos_to_vk(images)
            if errors:
                logging.warning(f"📱 Ошибки заливки: {errors}")
            logging.info(f"📱 Загружено {len(vk_attachments)}/{len(images)} фото")

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

        # Отправляем уведомление админу через прямой HTTP
        req.get(
            "https://api.vk.com/method/messages.send",
            params={
                "user_id": ADMIN_ID,
                "message": msg,
                "random_id": 0,
                "group_id": GROUP_ID,
                "access_token": GROUP_TOKEN,
                "v": "5.131"
            },
            timeout=30
        )

        logging.info(f"📱 Reddit пост {draft_id} сохранён, вложений: {len(vk_attachments)}")
        return "ok"
    except Exception as e:
        logging.error(f"Reddit error: {e}")
        return "error", 500


def run_reddit_handler():
    logging.info("📱 Reddit handler запущен на порту 3000")
    app.run(host="0.0.0.0", port=3000)
