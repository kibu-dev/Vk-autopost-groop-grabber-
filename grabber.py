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
                            
                            # Проверки
                            if contains_any_link(text):
                                moderate_post(vk, pid, -group_id, text, build_attachments(post), "ссылки (граббер)", "grab")
                                # Всё равно кидаем в предложку, админ решит
                                vk.wall.post(owner_id=-GROUP_ID, message=text, attachments=build_attachments(post), from_group=0)
                                continue
                            if is_spam(text):
                                moderate_post(vk, pid, -group_id, text, build_attachments(post), "спам-слова (граббер)", "grab")
                                vk.wall.post(owner_id=-GROUP_ID, message=text, attachments=build_attachments(post), from_group=0)
                                continue
                            
                            # Чистый пост → в предложку
                            vk.wall.post(owner_id=-GROUP_ID, message=text, attachments=build_attachments(post), from_group=0)
                            print(f"📨 Граббер: пост {pid} → предложка")
                            time.sleep(1)
                            
                            if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                                break
                    except Exception as e:
                        print(f"❌ Группа {group_id}: {e}")
            time.sleep(GRAB_INTERVAL)
        except Exception as e:
            print(f"❌ Граббер: {e}")
            time.sleep(60)
