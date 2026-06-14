import time
import traceback
import vk_api
from config import *
from utils import *

def run_publisher():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    last_publish_time = None

    print("🚀 Публикатор запущен")

    while True:
        try:
            if last_publish_time and (time.time() - last_publish_time) < PUBLISH_INTERVAL:
                remaining = int(PUBLISH_INTERVAL - (time.time() - last_publish_time))
                print(f"⏰ Жду интервал, {remaining // 60} мин.")
                time.sleep(CHECK_INTERVAL)
                continue
            
            items = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=10)["items"]
            
            for post in items:
                pid = post["id"]
                uid = post.get("from_id", 0)
                text = post.get("text", "")
                
                if is_spam(text):
                    moderate_post(vk, pid, uid, text, build_attachments(post), "спам-слова", "suggestion")
                    continue
                
                if contains_any_link(text):
                    moderate_post(vk, pid, uid, text, build_attachments(post), "ссылки", "suggestion")
                    continue
                
                anonymous = contains_anonymous(text)
                if anonymous:
                    final = f"{text}\n\nАвтор: Аноним"
                else:
                    first, last = get_user_name(vk, uid)
                    final = f"{text}\n\nАвтор: [id{uid}|{first} {last}]"
                
                attachments = build_attachments(post)
                result = vk.wall.post(owner_id=-GROUP_ID, message=final, attachments=attachments, from_group=1)
                vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                add_published_post(result["post_id"], uid, text)
                last_publish_time = time.time()
                print(f"✅ Опубликован пост #{pid}")
                break
            
            time.sleep(CHECK_INTERVAL)
        
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(60)
