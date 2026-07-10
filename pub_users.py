import time
import logging
import vk_api
from datetime import datetime
from config import *
from utils import *


def _get_api():
    # Для чтения предложки нужен токен с правами администратора сообщества.
    # Сначала пробуем USER_TOKEN (токен админа), иначе — токен группы.
    token = USER_TOKEN or GROUP_TOKEN
    return vk_api.VkApi(token=token, api_version="5.131").get_api()


def _can_read_suggests(vk):
    try:
        vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=1)
        return True
    except Exception as e:
        logging.warning(f"⚠️ Предложка недоступна для токена ({e}). "
                        f"Посты будут приниматься только через ЛС бота.")
        return False


def run_pub_users():
    if not (USER_TOKEN or GROUP_TOKEN):
        logging.warning("👤 Публикатор предложки: нет токена, пропуск.")
        return

    vk = _get_api()

    # Если у токена нет прав/методов на предложку — молча выходим,
    # тогда работает запасной вариант: пользователь пишет пост боту в ЛС.
    if not _can_read_suggests(vk):
        return

    logging.info("👤 Публикатор предложки запущен (в отложенные, интервал 15 мин)")

    while True:
        try:
            items = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)["items"]
            items.sort(key=lambda x: x.get("date", 0))

            for post in items:
                pid = post["id"]
                uid = post.get("from_id", 0)
                text = post.get("text", "")

                # Спам/ссылки — на модерацию администратору
                if is_spam(text) or contains_any_link(text):
                    reason = "спам-слова" if is_spam(text) else "ссылки"
                    if not any(m["post_id"] == pid for m in get_moderation_posts()):
                        if not is_post_skipped(pid):
                            moderate_post(vk, pid, uid, text, build_attachments(post), reason, "suggestion")
                    continue

                if contains_anonymous(text):
                    final = f"{text}\n\nАвтор: Аноним"
                else:
                    first, last = get_user_name(vk, uid)
                    final = f"{text}\n\nАвтор: [id{uid}|{first} {last}]"

                att = build_attachments(post)

                # Ставим пост в отложенные с шагом 15 минут
                slot = get_next_schedule_time(PUBLISH_INTERVAL)
                posted = False
                for _ in range(96):
                    try:
                        vk.wall.post(
                            owner_id=-GROUP_ID,
                            message=final,
                            attachments=att,
                            from_group=1,
                            publish_date=slot,
                        )
                        posted = True
                        break
                    except vk_api.exceptions.ApiError as e:
                        if e.code == 214 or "already scheduled" in str(e).lower():
                            slot += PUBLISH_INTERVAL
                        else:
                            raise

                if not posted:
                    logging.error(f"❌ Предложка: не удалось запланировать #{pid}")
                    continue

                # Убираем исходную запись из предложки
                try:
                    vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                except Exception as e:
                    logging.error(f"⚠️ Не удалось удалить предложку #{pid}: {e}")

                add_scheduled_post(slot, final[:200], uid)
                add_skipped_post(pid)
                when = datetime.fromtimestamp(slot).strftime("%H:%M")
                logging.info(f"✅ Предложка #{pid} → отложено на {when}")

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            logging.error(f"❌ Пуб предложки: {e}")
            time.sleep(60)
