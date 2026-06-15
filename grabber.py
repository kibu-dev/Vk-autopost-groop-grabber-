import time
import vk_api
from config import *
from utils import *

def run_grabber():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    print("🎣 Граббер запущен")

    while True:
        try:
            donors = get_donor_groups()
            if donors:
                for group_id in donors:
                    try:
                        if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                            continue

                        posts = vk.wall.get(owner_id=-group_id, count=GRAB_POSTS_PER_GROUP, filter="owner")

                        for post in posts.get("items", []):
                            pid = post["id"]
                            text = post.get("text", "")

                            if is_post_grabbed(group_id, pid):
                                continue

                            add_grabbed_post(group_id, pid)
                            att = build_attachments(post)

                            vk.wall.post(owner_id=-GROUP_ID, message=text, attachments=att, from_group=0)
                            print(f"📨 Пост {pid} из группы {group_id} → предложка")

                            time.sleep(2)

                            if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                                break

                    except Exception as e:
                        print(f"❌ Группа {group_id}: {e}")

            time.sleep(GRAB_INTERVAL)

        except Exception as e:
            print(f"❌ Граббер: {e}")
            time.sleep(60)
