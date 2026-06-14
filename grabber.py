import time
import traceback
import vk_api
from config import *
from db import *
from utils import *
from keyboards import get_moderation_keyboard

def run_grabber():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    
    print("🎣 Граббер запущен")
    print(f"⏱ Интервал сканирования: {GRAB_INTERVAL // 60} мин.")
    print(f"📊 Лимит с группы в сутки: {MAX_GRAB_PER_GROUP_DAY}")
    
    while True:
        try:
            donors = get_donor_groups()
            if not donors:
                print("📭 Нет групп-доноров. Добавьте через админку.")
            else:
                print(f"\n🔍 Сканирую {len(donors)} групп-доноров...")
                
                for group_id in donors:
                    try:
                        # Проверяем дневной лимит
                        today_count = count_today_grabs_from_group(group_id)
                        if today_count >= MAX_GRAB_PER_GROUP_DAY:
                            print(f"  ⏭ Группа {group_id}: лимит ({today_count}/{MAX_GRAB_PER_GROUP_DAY})")
                            continue
                        
                        # Забираем последние посты
                        posts = vk.wall.get(
                            owner_id=-group_id,
                            count=GRAB_POSTS_PER_GROUP,
                            filter="owner"  # только от имени группы
                        )
                        
                        grabbed = 0
                        for post in posts.get("items", []):
                            post_id = post["id"]
                            text = post.get("text", "")
                            
                            # Уже брали?
                            if is_post_grabbed(group_id, post_id):
                                continue
                            
                            # Отмечаем что видели
                            add_to_grab_history(group_id, post_id)
                            
                            # Проверка на ссылки
                            if contains_any_link(text):
                                attachments_str = build_attachments(post)
                                moderate_post(
                                    vk=vk,
                                    post_id=post_id,
                                    uid=-group_id,
                                    text=text,
                                    attachments_str=attachments_str,
                                    reason="ссылки (граббер)",
                                    post_type="grab"
                                )
                                continue
                            
                            # Проверка на спам-слова
                            if is_spam(text):
                                attachments_str = build_attachments(post)
                                moderate_post(
                                    vk=vk,
                                    post_id=post_id,
                                    uid=-group_id,
                                    text=text,
                                    attachments_str=attachments_str,
                                    reason="спам-слова (граббер)",
                                    post_type="grab"
                                )
                                continue
                            
                            # Добавляем в очередь
                            attachments_str = build_attachments(post)
                            add_to_grab_queue(group_id, post_id, text, attachments_str or "")
                            grabbed += 1
                            print(f"  ✅ Группа {group_id}: пост {post_id} → в очередь")
                            
                            # Проверяем лимит
                            if count_today_grabs_from_group(group_id) >= MAX_GRAB_PER_GROUP_DAY:
                                break
                        
                        if grabbed == 0:
                            print(f"  📭 Группа {group_id}: нет новых постов")
                    
                    except Exception as e:
                        print(f"  ❌ Ошибка в группе {group_id}: {e}")
                
                queue_count = get_grab_queue_count()
                print(f"📦 Постов в очереди граббера: {queue_count}")
            
            time.sleep(GRAB_INTERVAL)
        
        except Exception as e:
            print(f"❌ Ошибка граббера: {e}")
            traceback.print_exc()
            time.sleep(60)
