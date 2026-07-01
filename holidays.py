import logging
import vk_api
from datetime import datetime, timedelta
from config import *
from utils import *
from ai_poster import generate_text

HOLIDAYS_CONFIG = "holidays_config.json"
HOLIDAY_PROMPT_FILE = "holiday_prompt.txt"
HOLIDAY_LIST_PROMPT_FILE = "holidays_list_prompt.txt"

def get_holidays_config():
    return load_json(HOLIDAYS_CONFIG, {
        "current_index": 0,
        "holidays_list": [],
        "month": "",
        "selected_name": "",
        "selected_date": "",
        "photo_id": "",
        "generated_text": ""
    })

def save_holidays_config(data):
    save_json(HOLIDAYS_CONFIG, data)

def load_holiday_prompt():
    try:
        with open(HOLIDAY_PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Напиши тёплое поздравление с праздником «{name}» для подписчиков группы."

def load_holiday_list_prompt():
    try:
        with open(HOLIDAY_LIST_PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Перечисли праздники России на {month} {year}."

def generate_holidays_list():
    """Запрашивает у ИИ список праздников на текущий месяц"""
    now = datetime.now() + timedelta(hours=3)
    months_ru = {
        "january": "январь", "february": "февраль", "march": "март", "april": "апрель",
        "may": "май", "june": "июнь", "july": "июль", "august": "август",
        "september": "сентябрь", "october": "октябрь", "november": "ноябрь", "december": "декабрь"
    }
    month_ru = months_ru.get(now.strftime("%B").lower(), now.strftime("%B"))
    
    prompt = load_holiday_list_prompt().replace("{month}", month_ru).replace("{year}", str(now.year))
    
    result = generate_text(prompt)
    if not result:
        return []
    
    holidays = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if "—" in line or "-" in line:
            parts = line.replace("—", "-").split("-", 1)
            if len(parts) == 2:
                date_str = parts[0].strip()
                name = parts[1].strip()
                if name and len(name) > 3:
                    holidays.append({"date": date_str, "name": name})
    
    return holidays

def get_holiday_publish_time(date_str):
    """Преобразует '8 июля' в timestamp 10:00 МСК (7:00 UTC). Если дата прошла — следующий год."""
    now = datetime.now() + timedelta(hours=3)
    months_ru = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
    }
    
    parts = date_str.strip().split()
    if len(parts) >= 2:
        day = int(parts[0])
        month_name = parts[1].lower()
        month = months_ru.get(month_name, now.month)
        year = now.year
        
        target = datetime(year, month, day, 10, 0, 0) - timedelta(hours=3)
        
        if target.timestamp() < datetime.now().timestamp():
            target = datetime(year + 1, month, day, 10, 0, 0) - timedelta(hours=3)
        
        return int(target.timestamp())
    return 0

def create_holiday_post(vk_user):
    """Создаёт отложенный пост для выбранного праздника"""
    config = get_holidays_config()
    
    date_str = config.get("selected_date", "")
    name = config.get("selected_name", "")
    photo_id = config.get("photo_id", "")
    text = config.get("generated_text", "")
    
    if not date_str or not text:
        logging.error(f"🎉 Нет даты или текста")
        return False
    
    pub_time = get_holiday_publish_time(date_str)
    logging.info(f"🎉 Праздник: {date_str} -> timestamp: {pub_time}, photo: {photo_id if photo_id else 'нет'}")
    
    if pub_time == 0:
        logging.error(f"🎉 Невалидная дата публикации")
        return False
    
    for attempt in range(24):
        try:
            result = vk_user.wall.post(
                owner_id=-GROUP_ID,
                message=text,
                attachments=photo_id if photo_id else None,
                from_group=1,
                publish_date=pub_time
            )
            pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
            logging.info(f"🎉 Поздравление запланировано на {pub_str}")
            add_scheduled_post(pub_time, text[:200], 0)
            return True
        except Exception as e:
            if "214" in str(e) or "already scheduled" in str(e):
                pub_time += 3600
                logging.info(f"🎉 Время занято, пробую {datetime.fromtimestamp(pub_time).strftime('%H:%M')}")
            else:
                logging.error(f"🎉 Ошибка публикации: {e}")
                return False
    
    logging.error(f"🎉 Не удалось найти свободное время")
    return False

def generate_holiday_text(name):
    """Генерирует текст поздравления через ИИ"""
    prompt = load_holiday_prompt().replace("{name}", name)
    return generate_text(prompt)
