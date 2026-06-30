import requests
import json
from datetime import datetime
from config import OPENROUTER_API_KEY

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

def generate_text(prompt):
    """Отправляет прямой запрос к ИИ (без prompt.txt)"""
    if not OPENROUTER_API_KEY:
        ai_log("Нет API ключа")
        return None
    
    ai_log(f"Прямой запрос: {prompt[:100]}")
    
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
                "max_tokens": 1500
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

def generate_variants(text):
    """Генерирует текст через prompt.txt (для AI-постера, гороскопа)"""
    if not OPENROUTER_API_KEY:
        ai_log("Нет API ключа OpenRouter")
        return None
    
    prompt = load_prompt().replace("{text}", text)
    return generate_text(prompt)

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
