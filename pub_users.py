import time
import vk_api
from config import *
from utils import *

def run_pub_users():
    vk = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    last_pub = get_last_publish_time()
    print("👤 Публикатор пользователей запущен (каждые 15 мин)")

    while True:
        try:
            now = time.time()

            items = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)["items"]
            items.sort(key=lambda x: x.get("date", 0))

            for post in items:
                pid = post["id"]
                uid = post.get("from_id", 0)
                text = post.get("text", "")

                if is_spam(text) or contains_any_link(text):
                    reason = "спам-слова" if is_spam(text) else "ссылки"
                    if not any(m["post_id"] == pid for m in get_moderation_posts()):
                        if not is_post_skipped(pid):
                            moderate_post(vk, pid, uid, text, build_attachments(post), reason, "suggestion")
                    continue

                if now - last_pub < PUBLISH_INTERVAL:
                    continue

                if contains_anonymous(text):
                    final = f"{text}\n\nАвтор: Аноним"
                else:
                    first, last = get_user_name(vk, uid)
                    final = f"{text}\n\nАвтор: [id{uid}|{first} {last}]"

                att = build_attachments(post)
                result = vk.wall.post(owner_id=-GROUP_ID, message=final, attachments=att, from_group=1)
                vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                add_published_post(result["post_id"], uid, text)
                last_pub = time.time()
                save_last_publish_time(last_pub)
                print(f"✅ Пользователь: опубликован #{pid}")
                break

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"❌ Пуб пользователей: {e}")
            time.sleep(60)
