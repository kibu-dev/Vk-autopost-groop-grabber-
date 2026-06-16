import time
import vk_api
from datetime import datetime, timedelta
from config import *
from utils import *

def run_grabber():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    print("🎣 Граббер запущен (каждые 15 мин, без лимитов)")

    while True:
        try:
            donors = get_donor_groups()
            if donors:
                print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Сканирую {len(donors)} групп...")

                for group_id in donors:
                    try:
                        posts = vk.wall.get(owner_id=-group_id, count=10, filter="owner")

                        for post in posts.get("items", []):
                            pid = post["id"]
                            text = post.get("text", "")

                            if is_post_grabbed(group_id, pid):
                                continue

                            add_grabbed_post(group_id, pid)

                            # Подозрительный → на модерацию
                            if contains_any_link(text) or is_spam(text):
                                reason = "ссылки" if contains_any_link(text) else "спам-слова"
                                add_pending_grab(post, group_id, reason)
                                moderate_post(vk, pid, -group_id, text, build_attachments(post), f"{reason} (граббер)", "grab")
                                print(f"  ⚠️ Пост {pid} → модерация ({reason})")
                                continue

                            # Чистый → планируем
                            att = build_attachments(post)
                            pub_time = get_next_free_hour()
                            vk.wall.post(
                                owner_id=-GROUP_ID,
                                message=text,
                                attachments=att,
                                from_group=1,
                                publish_date=pub_time
                            )
                            add_scheduled_post(pub_time, text[:200], group_id)
                            print(f"  📅 Пост {pid} запланирован на {datetime.fromtimestamp(pub_time).strftime('%H:%M')}")

                            time.sleep(2)

                    except Exception as e:
                        print(f"  ❌ Группа {group_id}: {e}")

            else:
                print("📭 Нет групп-доноров")

            time.sleep(900)

        except Exception as e:
            print(f"❌ Граббер: {e}")
            time.sleep(60)
