import time
import traceback
import vk_api
from config import *
from db import *
from utils import *

def run_publisher():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    last_publish_time = None

    print("🚀 Публикатор запущен")
    print(f"⏱ Интервал: {PUBLISH_INTERVAL // 60} мин.")

    while True:
        try:
            published = False
            
            # 1. Сначала проверяем очередь граббера
            grab_post = get_next_grab_post()
            
            if grab_post:
                # Проверяем интервал
                if last_publish_time is None or (time.time() - last_publish_time) >= PUBLISH_INTERVAL:
                    text = grab_post["text"]
                    
                    # Добавляем префикс/суффикс если заданы
                    final_text = text
                    if GRABBER_POST_PREFIX:
                        final_text = GRABBER_POST_PREFIX + "\n" + final_text
                    if GRABBER_POST_SUFFIX:
                        final_text = final_text + "\n" + GRABBER_POST_SUFFIX
                    
                    attachments = parse_attachments_string(grab_post["attachments"])
                    
                    try:
                        result = vk.wall.post(
                            owner_id=-GROUP_ID,
                            message=final_text,
                            attachments=attachments,
                            from_group=1
                        )
                        mark_grab_published(grab_post["id"])
                        last_publish_time = time.time()
                        print(f"✅ Опубликован пост граббера (из группы {grab_post['donor_group_id']})")
                        published = True
                    except Exception as e:
                        print(f"❌ Ошибка публикации граббера: {e}")
                        mark_grab_published(grab_post["id"])  # всё равно помечаем чтобы не циклиться
                else:
                    remaining = int(PUBLISH_INTERVAL - (time.time() - last_publish_time))
                    print(f"⏰ Жду интервал, осталось {remaining // 60} мин.")
            
            # 2. Если не опубликовали — проверяем предложку
            if not published:
                if last_publish_time is None or (time.time() - last_publish_time) >= PUBLISH_INTERVAL:
                    items = vk.wall.get(owner_id=-GROUP_ID, filter="suggests", count=10)["items"]
                    
                    for post in items:
                        pid = post["id"]
                        uid = post.get("from_id", 0)
                        text = post.get("text", "")
                        
                        # Проверка на спам
                        if is_spam(text):
                            moderate_post(
                                vk=vk, post_id=pid, uid=uid, text=text,
                                attachments_str=build_attachments(post),
                                reason="спам-слова", post_type="suggestion"
                            )
                            continue
                        
                        # Проверка на ссылки
                        if contains_any_link(text):
                            moderate_post(
                                vk=vk, post_id=pid, uid=uid, text=text,
                                attachments_str=build_attachments(post),
                                reason="ссылки", post_type="suggestion"
                            )
                            continue
                        
                        # Публикуем
                        anonymous = contains_anonymous(text)
                        if anonymous:
                            final = f"{text}\n\nАвтор: Аноним"
                        else:
                            first, last = get_user_name(vk, uid)
                            final = f"{text}\n\nАвтор: [id{uid}|{first} {last}]"
                        
                        attachments = build_attachments(post)
                        result = vk.wall.post(
                            owner_id=-GROUP_ID,
                            message=final,
                            attachments=attachments,
                            from_group=1
                        )
                        vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                        add_user_post(uid, result["post_id"], text)
                        last_publish_time = time.time()
                        print(f"✅ Опубликован пост #{pid} от пользователя")
                        break  # один пост за раз
            
            time.sleep(CHECK_INTERVAL)
        
        except Exception as e:
            print(f"❌ Ошибка публикатора: {e}")
            traceback.print_exc()
            time.sleep(60)
