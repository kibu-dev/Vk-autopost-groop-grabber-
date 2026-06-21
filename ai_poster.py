import requests
import json
import re
import time
from datetime import datetime
from config import OPENROUTER_API_KEY, USER_TOKEN, GROUP_TOKEN, GROUP_ID

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
        ai_log("Нет API ключа")
        return None
    
    prompt = load_prompt().replace("{text}", text)
    ai_log(f"Запрос: {text[:100]}")
    
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
    """Генерирует картинку через Pollinations.ai, возвращает URL"""
    try:
        import urllib.parse
        encoded = urllib.parse.quote(prompt[:200])
        image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
        
        ai_log(f"Запрос картинки: {prompt[:100]}")
        
        for _ in range(3):
            response = requests.head(image_url, timeout=10)
            if response.status_code == 200:
                ai_log("Картинка сгенерирована")
                return image_url
            time.sleep(3)
        
        ai_log("Не удалось сгенерировать картинку")
        return None
    except Exception as e:
        ai_log(f"Ошибка генерации картинки: {e}")
        return None

def generate_image_prompt(text):
    """Создаёт короткий промт для картинки на основе текста поста"""
    if not OPENROUTER_API_KEY:
        return text[:100]
    
    prompt = f"Напиши короткое описание картинки (до 100 символов, на русском) для поста на тему: {text[:200]}"
    
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
                "max_tokens": 100
            },
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            ai_log(f"Промт картинки: {result}")
            return result
        return text[:100]
    except:
        return text[:100]

def upload_image_to_vk(image_url):
    """Скачивает картинку и загружает в ВК, возвращает строку для attachments"""
    try:
        ai_log(f"Скачиваю картинку: {image_url}")
        
        # Скачиваем картинку
        img_response = requests.get(image_url, timeout=30)
        if img_response.status_code != 200:
            ai_log(f"Ошибка скачивания: {img_response.status_code}")
            return None
        
        img_data = img_response.content
        ai_log(f"Скачано: {len(img_data)} байт")
        
        # Загружаем в ВК через messages.getUploadServer
        import vk_api
        vk = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
        
        # Получаем сервер для загрузки
        upload_server = vk.photos.getMessagesUploadServer(group_id=GROUP_ID)
        ai_log(f"Upload URL: {upload_server['upload_url'][:50]}...")
        
        # Загружаем фото
        files = {'photo': ('image.jpg', img_data, 'image/jpeg')}
        upload_response = requests.post(upload_server['upload_url'], files=files).json()
        ai_log(f"Upload response: {upload_response}")
        
        # Сохраняем фото
        save_result = vk.photos.saveMessagesPhoto(
            photo=upload_response['photo'],
            server=upload_response['server'],
            hash=upload_response['hash']
        )
        
        if save_result:
            photo = save_result[0]
            att_str = f"photo{photo['owner_id']}_{photo['id']}"
            ai_log(f"Фото загружено: {att_str}")
            return att_str
        else:
            ai_log("Не удалось сохранить фото")
            return None
            
    except Exception as e:
        ai_log(f"Ошибка загрузки фото в ВК: {e}")
        return None
