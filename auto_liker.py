import time
import random
import vk_api
from config import *
from utils import *

def run_auto_liker():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    liked_posts = {}
    print("❤️ Автолайкер запущен")

    while True:
        try:
            if not is_liker_enabled():
                time.sleep(30)
                continue

            groups = get_liker_groups()
            stats = get_liker_stats()

            if stats["today"] >= 20:
                print("❤️ Лимит 20 лайков")
                time.sleep(300)
                continue

            for group_id in groups:
                try:
                    posts = vk.wall.get(owner_id=-group_id, count=5)
                    for post in posts.get("items", []):
                        pid = post["id"]

                        if liked_posts.get(group_id, 0) >= pid:
                            continue

                        vk.likes.add(type="post", owner_id=-group_id, item_id=pid)
                        liked_posts[group_id] = pid
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
