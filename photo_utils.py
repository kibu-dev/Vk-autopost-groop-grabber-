# photo_utils.py — Надёжная загрузка фото в ВК через токен группы.

import logging
import requests
from config import GROUP_ID, GROUP_TOKEN


def _get_max_photo_url(photo_obj: dict):
    """Возвращает URL фото максимального размера."""
    sizes = photo_obj.get("sizes", [])
    if not sizes:
        return None
    best = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
    return best.get("url")


def upload_photo_to_group(vk, photo_obj: dict):
    """
    Скачивает фото по URL и загружает в группу.
    Возвращает строку вида 'photo-GROUP_ID_PHOTO_ID' или None при ошибке.
    """
    url = _get_max_photo_url(photo_obj)
    if not url:
        logging.warning("upload_photo_to_group: нет URL у фото")
        return None

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        photo_bytes = resp.content
        logging.info(f"📥 Скачано фото ({len(photo_bytes)} байт): {url[:80]}")
    except Exception as e:
        logging.error(f"Ошибка скачивания фото {url[:80]}: {e}")
        return None

    try:
        server = vk.photos.getWallUploadServer(group_id=GROUP_ID)
        upload_url = server["upload_url"]

        upload_resp = requests.post(
            upload_url,
            files={"photo": ("photo.jpg", photo_bytes, "image/jpeg")},
            timeout=60,
        ).json()

        if "photo" not in upload_resp or not upload_resp["photo"]:
            logging.error(f"VK upload server вернул ошибку: {upload_resp}")
            return None

        saved = vk.photos.saveWallPhoto(
            group_id=GROUP_ID,
            server=upload_resp["server"],
            photo=upload_resp["photo"],
            hash=upload_resp["hash"],
        )

        if saved:
            p = saved[0]
            att_str = f"photo{p['owner_id']}_{p['id']}"
            logging.info(f"✅ Фото загружено в группу: {att_str}")
            return att_str
        else:
            logging.error("photos.saveWallPhoto вернул пустой список")
            return None

    except Exception as e:
        logging.error(f"Ошибка загрузки фото в VK: {e}")
        return None


def copy_attachments(vk, attachments: list) -> list:
    """
    Принимает список вложений из VK API.
    Фото — скачивает и перезаливает. Остальное передаёт как есть.
    """
    result = []
    for att in attachments:
        att_type = att.get("type")
        obj = att.get(att_type, {})

        if att_type == "photo":
            new_att = upload_photo_to_group(vk, obj)
            if new_att:
                result.append(new_att)
            else:
                logging.warning("⚠️ Не удалось загрузить фото, пропускаем")

        elif att_type in ("video", "audio", "doc", "poll", "link"):
            owner_id = obj.get("owner_id")
            obj_id = obj.get("id")
            access_key = obj.get("access_key", "")
            if owner_id and obj_id:
                s = f"{att_type}{owner_id}_{obj_id}"
                if access_key:
                    s += f"_{access_key}"
                result.append(s)

    return result


def copy_photos_from_message(vk, message_id: int, group_id: int) -> list:
    """
    Получает вложения из сообщения по ID и загружает фото в группу.
    """
    try:
        msg_data = vk.messages.getById(message_ids=message_id, group_id=group_id)
        if not msg_data or not msg_data.get("items"):
            return []
        attachments = msg_data["items"][0].get("attachments", [])
        return copy_attachments(vk, attachments)
    except Exception as e:
        logging.error(f"copy_photos_from_message error: {e}")
        return []
