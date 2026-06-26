import time
import random
import vk_api
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
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    liked_posts = get_liked_posts()
    print("❤️ Автолайкер запущен")

    while True:
        try:
            if not is_liker_enabled():
                time.sleep(30)
                continue

            groups = get_liker_groups()
            stats = get_liker_stats()

            if stats["today"] >= 20:
                time.sleep(300)
                continue

            for group_id in groups:
                try:
                    # Берём только 1 последний пост
                    posts = vk.wall.get(owner_id=-group_id, count=1)
                    
                    for post in posts.get("items", []):
                        pid = post["id"]
                        last_liked = liked_posts.get(str(group_id), 0)

                        # Лайкаем только если это новый пост (ID больше последнего лайкнутого)
                        if pid <= last_liked:
                            continue

                        vk.likes.add(type="post", owner_id=-group_id, item_id=pid)
                        save_liked_post(group_id, pid)
                        liked_posts[str(group_id)] = pid
                        add_liker_stat()
                        print(f"❤️ Лайк: {pid} в {group_id}")

                        delay = random.randint(120, 180)
                        time.sleep(delay)

                        if get_liker_stats()["today"] >= 20:
                            break

                except Exception as e:
                    print(f"❤️ Ошибка в {group_id}: {e}")

            time.sleep(60)

        except Exception as e:
            print(f"❤️ Ошибка: {e}")
            time.sleep(60)
