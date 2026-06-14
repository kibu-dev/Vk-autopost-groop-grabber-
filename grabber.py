import time
import traceback
import vk_api
from config import *
from utils import *

def run_grabber():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    
    print("🎣 Граббер запущен")
    
    while True:
        try:
            donors = get_donor_groups()
            if not donors:
                print("📭 Нет групп-доноров")
            else:
                print(f"\n🔍 Сканирую {len(donors)} групп...")
                
                for group_id in donors:
                    try:
                        if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                            continue
                        
                        posts = vk.wall.get(owner_id=-group_id, count=GRAB_POSTS_PER_GROUP, filter="owner")
                        
                        for post in posts.get("items", []):
                            post_id = post["id"]
                            text = post.get("text", "")
                            
                            if is_post_grabbed(group_id, post_id):
                                continue
                            
                            add_grabbed_post(group_id, post_id)
                            
                            if contains_any_link(text):
                                moderate_post(vk, post_id, -group_id, text, build_attachments(post), "ссылки (граббер)", "grab")
                                continue
                            
                            if is_spam(text):
                                moderate_post(vk, post_id, -group_id, text, build_attachments(post), "спам-слова (граббер)", "grab")
                                continue
                            
                            # Публикуем сразу
                            final_text = text
                            if GRABBER_POST_PREFIX:
                                final_text = GRABBER_POST_PREFIX + "\n" + final_text
                            if GRABBER_POST_SUFFIX:
                                final_text = final_text + "\n" + GRABBER_POST_SUFFIX
                            
                            attachments = build_attachments(post)
                            result = vk.wall.post(owner_id=-GROUP_ID, message=final_text, attachments=attachments, from_group=1)
                            add_published_post(result["post_id"], -group_id, text)
                            print(f"✅ Граббер: пост {post_id} из {group_id}")
                            time.sleep(15)
                            
                            if count_today_grabs(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                                break
                    
                    except Exception as e:
                        print(f"❌ Группа {group_id}: {e}")
            
            time.sleep(GRAB_INTERVAL)
        
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(60)
