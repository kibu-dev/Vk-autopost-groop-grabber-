import time
import random
import logging
import vk_api
from datetime import datetime, timedelta
from config import *
from utils import *

LIKED_FILE = "liked_posts.json"

def get_liked_posts():
    return load_json(LIKED_FILE, {})

def save_liked_post(group_id, post_id):
    data = get_liked_posts()
    data[str(group_id)] = post_id
    save_json(LIKED_FILE, data)

def run_auto_liker():
    vk = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    liked_posts = get_liked_posts()
    logging.info("❤️ Автолайкер запущен")

    while True:
        try:
            if not is_liker_enabled():
                time.sleep(30)
                continue

            now_msk = datetime.now() + timedelta(hours=3)
            today_str = now_msk.strftime("%Y-%m-%d")
            
            stats = get_liker_stats()
            if stats["date"] != today_str:
                stats["today"] = 0
                stats["date"] = today_str
                save_json(LIKER_STATS_FILE, stats)
                logging.info(f"❤️ Новый день! Сброс на {today_str}")

            if stats["today"] >= 20:
                time.sleep(300)
                continue

            groups = get_liker_groups()

            for group_id in groups:
                try:
                    posts = vk.wall.get(owner_id=-group_id, count=1)

                    for post in posts.get("items", []):
                        pid = post["id"]
                        last_liked = liked_posts.get(str(group_id), 0)

                        if pid <= last_liked:
                            continue

                        vk.likes.add(type="post", owner_id=-group_id, item_id=pid)
                        save_liked_post(group_id, pid)
                        liked_posts[str(group_id)] = pid
                        add_liker_stat()
                        logging.info(f"❤️ Лайк: {pid} в {group_id}")

                        delay = random.randint(120, 180)
                        time.sleep(delay)

                        if get_liker_stats()["today"] >= 20:
                            break

                except Exception as e:
                    logging.error(f"❤️ Ошибка в {group_id}: {e}")

            time.sleep(60)

        except Exception as e:
            logging.error(f"❤️ Ошибка: {e}")
            time.sleep(60)
