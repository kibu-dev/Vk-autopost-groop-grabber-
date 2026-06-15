import time
import vk_api
from datetime import datetime, timedelta
from config import *
from utils import *

def run_grabber():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    print("🎣 Граббер запущен (ровно каждый час)")

    while True:
        try:
            now = datetime.now()
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            wait = (next_hour - datetime.now()).total_seconds()
            if wait > 0:
                print(f"⏰ Следующая проверка в {next_hour.strftime('%H:%M:%S')}")
                time.sleep(wait)

            donors = get_donor_groups()
            if not donors:
                print("📭 Нет групп-доноров")
                time.sleep(60)
                continue

            print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Сканирую {len(donors)} групп...")

            for group_id in donors:
                try:
                    if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                        print(f"  ⏭ Группа {group_id}: лимит")
                        continue

                    posts = vk.wall.get(owner_id=-group_id, count=GRAB_POSTS_PER_GROUP, filter="owner")
                    grabbed = 0

                    for post in posts.get("items", []):
                        pid = post["id"]
                        text = post.get("text", "")

                        if is_post_grabbed(group_id, pid):
                            continue

                        add_grabbed_post(group_id, pid)

                        # Проверки
                        if contains_any_link(text) or is_spam(text):
                            reason = "ссылки" if contains_any_link(text) else "спам-слова"
                            moderate_post(vk, pid, -group_id, text, build_attachments(post), f"{reason} (граббер)", "grab")
                            continue

                        # Чистый → в буфер
                        att = build_attachments(post)
                        buf_id = add_to_grab_buffer(text, att, group_id)
                        grabbed += 1
                        print(f"  📦 Пост {pid} → буфер (id={buf_id})")

                        time.sleep(2)

                        if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                            break

                    if grabbed == 0:
                        print(f"  📭 Группа {group_id}: нет новых")

                except Exception as e:
                    print(f"  ❌ Группа {group_id}: {e}")

            print(f"✅ Проверка завершена. В буфере: {buffer_count()}")

        except Exception as e:
            print(f"❌ Граббер: {e}")
            time.sleep(60)
