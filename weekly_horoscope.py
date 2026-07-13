# weekly_horoscope.py — полностью (один пост в понедельник, после выхода — следующий)

import time
import logging
import vk_api
from datetime import datetime, timedelta, timezone as tz
from config import *
from utils import *
from ai_poster import generate_variants

HOROSCOPE_CONFIG = "horoscope_config.json"
HOROSCOPE_PROMPT = "horoscope_prompt.txt"

def get_horoscope_config():
    return load_json(HOROSCOPE_CONFIG, {"enabled": False, "photo_id": "", "next_monday": "", "text": "", "post_id": 0})

def save_horoscope_config(data):
    save_json(HOROSCOPE_CONFIG, data)

def get_next_monday_9am():
    """Возвращает timestamp ближайшего понедельника 9:00 МСК (6:00 UTC)"""
    now_utc = datetime.now(tz.utc)
    now_msk = now_utc + timedelta(hours=3)
    
    days_until_monday = (7 - now_msk.weekday()) % 7
    if days_until_monday == 0 and now_msk.hour >= 9:
        days_until_monday = 7
    
    target_msk = (now_msk + timedelta(days=days_until_monday)).replace(hour=9, minute=0, second=0, microsecond=0)
    target_utc = target_msk - timedelta(hours=3)
    
    return int(target_utc.timestamp())

def load_horoscope_prompt():
    try:
        with open(HOROSCOPE_PROMPT, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Напиши гороскоп на неделю для всех знаков зодиака."

def create_horoscope(vk, vk_group):
    """Создаёт новый гороскоп на ближайший понедельник."""
    config = get_horoscope_config()
    next_monday = get_next_monday_9am()
    
    # Проверяем — может уже есть гороскоп на этот понедельник
    if config.get("next_monday"):
        try:
            existing_ts = int(datetime.fromisoformat(config["next_monday"]).timestamp())
            if existing_ts == next_monday:
                logging.info(f"🔮 Гороскоп на {datetime.fromtimestamp(next_monday).strftime('%d.%m %H:%M')} уже создан")
                return True
        except:
            pass
    
    # Удаляем старый пост если есть
    old_post_id = config.get("post_id")
    if old_post_id:
        try:
            vk.wall.delete(owner_id=-GROUP_ID, post_id=old_post_id)
            logging.info(f"🔮 Удалён старый гороскоп #{old_post_id}")
        except:
            pass
    
    logging.info("🔮 Создаю новый гороскоп...")
    
    prompt = load_horoscope_prompt()
    text = generate_variants(prompt)
    
    if not text:
        logging.error("🔮 ИИ не сгенерировал гороскоп")
        return False
    
    pub_time = next_monday  # начинаем с 9:00 МСК понедельника
    photo_id = config.get("photo_id", "")
    logging.info(f"🔮 Фото: {'есть' if photo_id else 'нет'}")
    
    for attempt in range(24):
        try:
            result = vk.wall.post(
                owner_id=-GROUP_ID,
                message=text,
                attachments=photo_id if photo_id else None,
                from_group=1,
                publish_date=pub_time
            )
            config["post_id"] = result["post_id"]
            break
        except Exception as e:
            if "214" in str(e) or "already scheduled" in str(e):
                pub_time += 3600
                logging.info(f"🔮 Время занято, пробую {datetime.fromtimestamp(pub_time).strftime('%H:%M')}")
            else:
                logging.error(f"🔮 Ошибка публикации: {e}")
                return False
    
    # Сохраняем ИСХОДНЫЙ понедельник (не сдвинутый), чтобы проверка работала
    config["next_monday"] = datetime.fromtimestamp(next_monday).isoformat()
    config["text"] = text[:2500]
    save_horoscope_config(config)
    
    pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
    logging.info(f"🔮 Запланирован на {pub_str}")
    
    if ADMIN_ID:
        try:
            vk_group.messages.send(
                user_id=ADMIN_ID,
                message=f"🔮 Гороскоп создан!\nЗапланирован на: {pub_str}" + (" 📎" if photo_id else ""),
                random_id=0,
                group_id=GROUP_ID
            )
        except Exception as e:
            logging.error(f"Ошибка уведомления: {e}")
    
    return True


def run_weekly_horoscope():
    vk = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.199").get_api()
    vk_group = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.199").get_api()
    
    logging.info("🔮 Гороскоп запущен")
    
    config = get_horoscope_config()
    if not config.get("next_monday"):
        config["next_monday"] = ""
        save_horoscope_config(config)
    
    while True:
        try:
            config = get_horoscope_config()
            
            if not config.get("enabled", False):
                time.sleep(300)
                continue
            
            now_ts = int(time.time())
            next_monday_str = config.get("next_monday", "")
            
            need_new = False
            
            if not next_monday_str:
                need_new = True
            else:
                try:
                    existing_ts = int(datetime.fromisoformat(next_monday_str).timestamp())
                    # Гороскоп вышел (время публикации прошло) — пора создавать новый
                    if existing_ts <= now_ts:
                        need_new = True
                except:
                    need_new = True
            
            if need_new:
                create_horoscope(vk, vk_group)
            
            time.sleep(3600)
            
        except Exception as e:
            logging.error(f"🔮 Ошибка: {e}")
            time.sleep(3600)
