# suggestion_checker.py — Обработчик «Предложить пост» через стену группы.

import time
import logging
from datetime import datetime

import vk_api

from config import GROUP_TOKEN, GROUP_ID, ADMIN_ID, PUBLISH_INTERVAL, CHECK_INTERVAL
from utils import (
    contains_any_link,
    is_spam,
    contains_anonymous,
    get_user_name,
    get_next_schedule_time,
    add_scheduled_post,
    is_post_grabbed,
    add_grabbed_post,
    moderate_post,
)
from photo_utils import copy_attachments


def _schedule_suggestion(vk, post: dict):
    text = post.get("text", "")
    from_id = post.get("from_id") or post.get("signer_id") or 0
    attachments = post.get("attachments", [])

    new_attachments = copy_attachments(vk, attachments)

    if contains_anonymous(text):
        final_text = f"{text}\n\nАвтор: Аноним"
    elif from_id and from_id > 0:
        try:
            name = get_user_name(vk, from_id)
            final_text = f"{text}\n\nАвтор: [id{from_id}|{name[0]} {name[1]}]"
        except Exception:
            final_text = f"{text}\n\nАвтор: id{from_id}"
    else:
        final_text = text

    slot = get_next_schedule_time(PUBLISH_INTERVAL)

    kwargs = {
        "owner_id": -GROUP_ID,
        "message": final_text,
        "from_group": 1,
    }
    if new_attachments:
        kwargs["attachments"] = ",".join(new_attachments)

    for _ in range(96):
        try:
            kwargs["publish_date"] = slot
            vk.wall.post(**kwargs)
            add_scheduled_post(slot, final_text[:200], from_id)
            logging.info(
                f"✅ Предложка #{post['id']} → отложен на "
                f"{datetime.fromtimestamp(slot).strftime('%H:%M')} "
                f"({'с фото: ' + str(len(new_attachments)) if new_attachments else 'без фото'})"
            )
            return slot
        except vk_api.exceptions.ApiError as e:
            if e.code == 214 or "already scheduled" in str(e).lower():
                slot += PUBLISH_INTERVAL
                continue
            logging.error(f"❌ VK API ошибка при публикации предложки #{post['id']}: {e}")
            return None
        except Exception as e:
            logging.error(f"❌ Ошибка публикации предложки #{post['id']}: {e}")
            return None

    return None


def _notify_admin(vk, from_id: int, slot: int, text: str, photo_count: int):
    if not ADMIN_ID:
        return
    try:
        try:
            name = get_user_name(vk, from_id)
            author = f"{name[0]} {name[1]}"
        except Exception:
            author = f"id{from_id}"

        when = datetime.fromtimestamp(slot).strftime("%d.%m %H:%M")
        msg = f"📨 Новая предложка от {author}!\n📝 {text[:200]}"
        if photo_count:
            msg += f"\n📷 Фото: {photo_count} шт."
        msg += f"\n\n🕒 Отложен на {when}"

        vk.messages.send(user_id=ADMIN_ID, message=msg, random_id=0, group_id=GROUP_ID)
    except Exception as e:
        logging.warning(f"Не удалось уведомить админа: {e}")


def run_suggestion_checker():
    vk = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
    logging.info("📬 Обработчик предложок запущен")

    # Запоминаем существующие предложки при старте, чтобы не обработать повторно
    try:
        existing = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)
        for post in existing.get("items", []):
            if not is_post_grabbed(-GROUP_ID, post["id"]):
                add_grabbed_post(-GROUP_ID, post["id"])
        logging.info(f"📬 Запомнено {len(existing.get('items', []))} существующих предложок")
    except Exception as e:
        logging.warning(f"Не удалось загрузить существующие предложки: {e}")

    while True:
        try:
            suggestions = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)

            for post in suggestions.get("items", []):
                post_id = post["id"]
                text = post.get("text", "")
                from_id = post.get("from_id") or post.get("signer_id") or 0
                attachments = post.get("attachments", [])
                photo_count = sum(1 for a in attachments if a.get("type") == "photo")

                if is_post_grabbed(-GROUP_ID, post_id):
                    continue

                add_grabbed_post(-GROUP_ID, post_id)
                logging.info(f"📬 Новая предложка #{post_id} от id{from_id}: фото={photo_count}")

                if contains_any_link(text) or is_spam(text):
                    reason = "ссылки" if contains_any_link(text) else "спам-слова"
                    att_str = ",".join(
                        f"photo{a['photo']['owner_id']}_{a['photo']['id']}"
                        for a in attachments if a.get("type") == "photo"
                    )
                    moderate_post(vk, post_id, from_id, text, att_str,
                                  f"{reason} (предложка)", "suggestion")
                    logging.info(f"  ⚠️ Предложка #{post_id} → модерация ({reason})")
                    continue

                slot = _schedule_suggestion(vk, post)
                if slot:
                    _notify_admin(vk, from_id, slot, text, photo_count)
                else:
                    logging.error(f"❌ Не удалось запланировать предложку #{post_id}")

                time.sleep(1)

        except vk_api.exceptions.ApiError as e:
            if e.code == 15:
                logging.warning("⚠️ Нет доступа к предложкам (error 15). Включите «Предложить новость» в настройках группы.")
            else:
                logging.error(f"❌ VK API ошибка в suggestion_checker: {e}")
        except Exception as e:
            logging.error(f"❌ suggestion_checker: {e}")

        time.sleep(CHECK_INTERVAL)
