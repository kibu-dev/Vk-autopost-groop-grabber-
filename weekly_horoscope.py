import time
import logging
import vk_api
from datetime import datetime, timedelta
from config import *
from utils import *
from ai_poster import generate_variants

HOROSCOPE_CONFIG = "horoscope_config.json"
HOROSCOPE_PROMPT = "horoscope_prompt.txt"

def get_horoscope_config():
    return load_json(HOROSCOPE_CONFIG, {"enabled": False, "photo_id": "", "next_monday": ""})

def save_horoscope_config(data):
    save_json(HOROSCOPE_CONFIG, data)

def get_next_monday_9am():
    now = datetime.now() + timedelta(hours=3)
    days_until_monday = (7 - now.weekday()) % 7
    if days_until_monday == 0 and now.hour >= 9:
        days_until_monday = 7
    next_monday = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
    return int(next_monday.timestamp())

def load_horoscope_prompt():
    try:
        with open(HOROSCOPE_PROMPT, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Напиши гороскоп на неделю для всех знаков зодиака."

def run_weekly_horoscope():
    vk_user = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    vk_group = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
    
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
            
            now_ts = int((datetime.now() + timedelta(hours=3)).timestamp())
            next_monday_str = config.get("next_monday", "")
            
            need_new = False
            
            if not next_monday_str:
                need_new = True
            else:
                try:
                    next_monday_ts = int(datetime.fromisoformat(next_monday_str).timestamp())
                    if now_ts >= next_monday_ts:
                        need_new = True
                except:
                    need_new = True
            
            if need_new:
                logging.info("🔮 Создаю новый гороскоп...")
                
                prompt = load_horoscope_prompt()
                text = generate_variants(prompt)
                
                if not text:
                    logging.error("🔮 ИИ не сгенерировал гороскоп")
                    time.sleep(3600)
                    continue
                
                pub_time = get_next_monday_9am()
                photo_id = config.get("photo_id", "")
                logging.info(f"🔮 Фото для гороскопа: {photo_id if photo_id else 'не указано'}")
                
                result = vk_user.wall.post(
                    owner_id=-GROUP_ID,
                    message=text,
                    attachments=photo_id if photo_id else None,
                    from_group=1,
                    publish_date=pub_time
                )
                
                config["next_monday"] = datetime.fromtimestamp(pub_time).isoformat()
                save_horoscope_config(config)
                
                pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
                logging.info(f"🔮 Гороскоп запланирован на {pub_str}")
                
                if ADMIN_ID:
                    try:
                        vk_group.messages.send(
                            user_id=ADMIN_ID,
                            message=f"🔮 Гороскоп на неделю создан!\nЗапланирован на: {pub_str}" + (" 📎" if photo_id else ""),
                            random_id=0,
                            group_id=GROUP_ID
                        )
                    except Exception as e:
                        logging.error(f"Ошибка уведомления: {e}")
            
            time.sleep(3600)
            
        except Exception as e:
            logging.error(f"🔮 Ошибка: {e}")
            time.sleep(3600)
