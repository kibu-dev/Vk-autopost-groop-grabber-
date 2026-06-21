import requests
import json
import re
import time
from datetime import datetime
from config import OPENROUTER_API_KEY, POLLINATIONS_API_KEY, GROUP_TOKEN, GROUP_ID

PROMPT_FILE = "prompt.txt"
LOG_FILE = "ai_log.json"

def ai_log(message):
    try:
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = []
        
        logs.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": str(message)
        })
        
        logs = logs[-100:]
        
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except:
        pass

def load_prompt():
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Напиши пост на тему: {text}"

def generate_variants(text):
    if not OPENROUTER_API_KEY:
        ai_log("Нет API ключа OpenRouter")
        return None
    
    prompt = load_prompt().replace("{text}", text)
    ai_log(f"Запрос текста: {text[:100]}")
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash-lite",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000
            },
            timeout=60
        )
        
        ai_log(f"Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            ai_log(f"Ответ: {result[:200]}...")
            return result
        else:
            ai_log(f"Ошибка {response.status_code}: {response.text[:300]}")
            return None
    except Exception as e:
        ai_log(f"Исключение: {str(e)}")
        return None

def parse_variants(result):
    try:
        with open("last_ai_response.txt", "w", encoding="utf-8") as f:
            f.write(result)
    except:
        pass
    
    text = result.strip()
    if text:
        ai_log(f"Длина ответа: {len(text)} символов")
        return [text]
    return []

def generate_image(prompt):
    """Генерирует картинку через Pollinations.ai API, возвращает bytes"""
    if not POLLINATIONS_API_KEY:
        ai_log("Нет API ключа Pollinations")
        return None
    
    try:
        import urllib.parse
        encoded = urllib.parse.quote(prompt[:200])
        image_url = f"https://gen.pollinations.ai/image/{encoded}?model=flux&width=1024&height=1024&key={POLLINATIONS_API_KEY}"
        
        ai_log(f"Запрос картинки: {prompt[:100]}")
        
        for attempt in range(5):
            time.sleep(5)
            response = requests.get(image_url, timeout=30)
            if response.status_code == 200 and len(response.content) > 1000:
                ai_log(f"Картинка скачана: {len(response.content)} байт")
                return response.content
            ai_log(f"Попытка {attempt+1}: статус {response.status_code}, размер {len(response.content)}")
        
        ai_log("Не удалось скачать картинку")
        return None
    except Exception as e:
        ai_log(f"Ошибка генерации картинки: {e}")
        return None

def generate_image_prompt(text):
    """Создаёт короткий промт для картинки на английском"""
    if not OPENROUTER_API_KEY:
        return text[:100]
    
    prompt = f"""Напиши короткое описание картинки на английском языке (до 80 символов) для иллюстрации поста. 
Только описание, без эмодзи, без кавычек. 
Опиши что должно быть на картинке: объекты, цвета, стиль.

Пост: {text[:300]}"""
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash-lite",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 80
            },
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            result = result.strip('"\'')
            ai_log(f"Промт картинки: {result}")
            return result
        return "fitness motivation, healthy lifestyle"
    except:
        return "fitness motivation, healthy lifestyle"

def upload_image_to_vk(image_data):
    """Загружает картинку (bytes) в ВК, возвращает строку для attachments"""
    try:
        ai_log(f"Загружаю картинку в ВК: {len(image_data)} байт")
        
        import vk_api
        vk = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
        
        upload_server = vk.photos.getMessagesUploadServer(group_id=GROUP_ID)
        
        files = {'photo': ('image.jpg', image_data, 'image/jpeg')}
        upload_response = requests.post(upload_server['upload_url'], files=files).json()
        ai_log(f"Upload: фото загружено")
        
        save_result = vk.photos.saveMessagesPhoto(
            photo=upload_response['photo'],
            server=upload_response['server'],
            hash=upload_response['hash']
        )
        
        if save_result:
            photo = save_result[0]
            att_str = f"photo{photo['owner_id']}_{photo['id']}"
            ai_log(f"Фото сохранено: {att_str}")
            return att_str
        
        return None
    except Exception as e:
        ai_log(f"Ошибка загрузки фото: {e}")
        return None
