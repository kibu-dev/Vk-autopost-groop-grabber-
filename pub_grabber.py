import time
import vk_api
from datetime import datetime, timedelta
from config import *
from utils import *

def run_pub_grabber():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    last_pub = get_last_grab_publish_time()
    print("📦 Публикатор граббера запущен (раз в час)")

    while True:
        try:
            now = time.time()

            if now - last_pub < GRAB_PUB_INTERVAL:
                time.sleep(60)
                continue

            item = get_next_from_buffer()
            if item:
                text = item["text"]
                att = item["attachments"] if item["attachments"] else None

                result = vk.wall.post(owner_id=-GROUP_ID, message=text, attachments=att, from_group=1)
                add_published_post(result["post_id"], -item["from_group"], text)
                remove_from_buffer(item["id"])
                last_pub = time.time()
                save_last_grab_publish_time(last_pub)
                print(f"✅ Граббер: опубликован #{result['post_id']} (буфер id={item['id']})")
            else:
                print("📭 Буфер граббера пуст")

            time.sleep(60)

        except Exception as e:
            print(f"❌ Пуб граббера: {e}")
            time.sleep(60)
