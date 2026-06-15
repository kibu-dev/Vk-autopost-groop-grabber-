import time
import vk_api
from config import *
from utils import *

def run_publisher():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    last_pub = 0
    print("🚀 Публикатор запущен")

    while True:
        try:
            now = time.time()
            if now - last_pub < PUBLISH_INTERVAL:
                time.sleep(CHECK_INTERVAL)
                continue

            items = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)["items"]
            items.sort(key=lambda x: x.get("date", 0))

            for post in items:
                pid = post["id"]
                uid = post.get("from_id", 0)
                text = post.get("text", "")

                # Проверка на спам
                if is_spam(text):
                    if not any(m["post_id"] == pid for m in get_moderation_posts()):
                        moderate_post(vk, pid, uid, text, build_attachments(post), "спам-слова", "suggestion")
                    continue

                # Проверка на ссылки
                if contains_any_link(text):
                    if not any(m["post_id"] == pid for m in get_moderation_posts()):
                        moderate_post(vk, pid, uid, text, build_attachments(post), "ссылки", "suggestion")
                    continue

                # Публикация
                if uid < 0:
                    final = text  # от граббера — без подписи
                else:
                    if contains_anonymous(text):
                        final = f"{text}\n\nАвтор: Аноним"
                    else:
                        first, last = get_user_name(vk, uid)
                        final = f"{text}\n\nАвтор: [id{uid}|{first} {last}]"

                att = build_attachments(post)
                result = vk.wall.post(owner_id=-GROUP_ID, message=final, attachments=att, from_group=1)
                vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                add_published_post(result["post_id"], uid if uid > 0 else -uid, text)
                last_pub = time.time()
                print(f"✅ Опубликован #{pid}")
                break

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"❌ Публикатор: {e}")
            time.sleep(60)
