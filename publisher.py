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
            
            for post in items:
                pid = post["id"]
                uid = post.get("from_id", 0)
                text = post.get("text", "")
                
                # Проверки
                if is_spam(text):
                    moderate_post(vk, pid, uid, text, build_attachments(post), "спам-слова", "suggestion")
                    continue
                if contains_any_link(text):
                    moderate_post(vk, pid, uid, text, build_attachments(post), "ссылки", "suggestion")
                    continue
                
                # Чистый пост → публикуем
                anon = contains_anonymous(text)
                if anon:
                    final = f"{text}\n\nАвтор: Аноним"
                else:
                    first, last = get_user_name(vk, uid)
                    final = f"{text}\n\nАвтор: [id{uid}|{first} {last}]"
                
                att = build_attachments(post)
                result = vk.wall.post(owner_id=-GROUP_ID, message=final, attachments=att, from_group=1)
                vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                add_published_post(result["post_id"], uid, text)
                last_pub = time.time()
                print(f"✅ Опубликован пост #{pid}")
                break
            
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"❌ Публикатор: {e}")
            time.sleep(60)
