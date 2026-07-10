import time
import logging
import vk_api
from datetime import datetime, timedelta
from config import *
from utils import *

def run_grabber():
    vk = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
    logging.info("🎣 Граббер запущен")

    donors = get_donor_groups()
    if donors:
        logging.info("🔄 Первый запуск — запоминаю последние посты...")
        for group_id in donors:
            try:
                posts = vk.wall.get(owner_id=-group_id, count=1, filter="owner")
                if posts["items"]:
                    last_pid = posts["items"][0]["id"]
                    if not is_post_grabbed(group_id, last_pid):
                        add_grabbed_post(group_id, last_pid)
                        logging.info(f"  📌 Группа {group_id}: запомнен пост {last_pid}")
            except Exception as e:
                logging.error(f"  ❌ Группа {group_id}: {e}")

    while True:
        try:
            donors = get_donor_groups()
            if donors:
                logging.info(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Сканирую...")

                for group_id in donors:
                    try:
                        if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                            continue

                        posts = vk.wall.get(owner_id=-group_id, count=GRAB_POSTS_PER_GROUP, filter="owner")
                        posts["items"].sort(key=lambda x: x["id"])

                        for post in posts.get("items", []):
                            pid = post["id"]
                            text = post.get("text", "")

                            if is_post_grabbed(group_id, pid):
                                continue

                            add_grabbed_post(group_id, pid)

                            if contains_any_link(text) or is_spam(text):
                                reason = "ссылки" if contains_any_link(text) else "спам-слова"
                                add_pending_grab(post, group_id, reason)
                                moderate_post(vk, pid, -group_id, text, build_attachments(post), f"{reason} (граббер)", "grab")
                                logging.info(f"  ⚠️ Пост {pid} → модерация")
                                continue

                            att = build_attachments(post)
                            pub_time = get_next_free_hour()
                            vk.wall.post(
                                owner_id=-GROUP_ID,
                                message=text,
                                attachments=att,
                                from_group=1,
                                publish_date=pub_time
                            )
                            add_scheduled_post(pub_time, text[:200], group_id)
                            logging.info(f"  📮 Пост {pid} запланирован на {datetime.fromtimestamp(pub_time).strftime('%H:%M')}")

                            time.sleep(1)

                    except Exception as e:
                        logging.error(f"  ❌ Группа {group_id}: {e}")

            time.sleep(GRAB_INTERVAL)

        except Exception as e:
            logging.error(f"❌ Граббер: {e}")
            time.sleep(60)
