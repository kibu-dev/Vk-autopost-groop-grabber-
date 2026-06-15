import time
import vk_api
from config import *
from utils import *

def run_publisher():
    global last_publish_time
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    notified_posts = set()
    utils.last_publish_time = 0
    print("🚀 Публикатор запущен")

    while True:
        try:
            now = time.time()
            can_publish = (now - utils.last_publish_time >= PUBLISH_INTERVAL)

            items = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)["items"]
            items.sort(key=lambda x: x.get("date", 0))

            for post in items:
                pid = post["id"]
                uid = post.get("from_id", 0)
                text = post.get("text", "")

                if is_spam(text) or contains_any_link(text):
                    reason = "спам-слова" if is_spam(text) else "ссылки"
                    if pid not in notified_posts:
                        notified_posts.add(pid)
                        moderate_post(vk, pid, uid, text, build_attachments(post), reason, "suggestion")
                    continue

                if not can_publish:
                    continue

                if uid < 0:
                    final = text
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
                utils.last_publish_time = time.time()
                notified_posts.discard(pid)
                print(f"✅ Опубликован #{pid}")
                break

            existing_ids = {p["id"] for p in items}
            notified_posts = {p for p in notified_posts if p in existing_ids}

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"❌ Публикатор: {e}")
            time.sleep(60)
