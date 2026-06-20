import requests
import json
from datetime import datetime
from config import OPENROUTER_API_KEY

PROMPT_FILE = "prompt.txt"
LOG_FILE = "ai_log.json"

def ai_log(message):
    """Пишет лог в JSON файл"""
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
        
        # Оставляем последние 100 записей
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
        return "Улучши этот текст: {text}"

def generate_variants(text):
    if not OPENROUTER_API_KEY:
        ai_log("❌ Нет API ключа")
        return None
    
    prompt = load_prompt().replace("{text}", text)
    ai_log(f"📤 Запрос: {text[:100]}")
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash-lite",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        
        ai_log(f"📥 Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            ai_log(f"✅ Ответ получен: {result[:100]}")
            return result
        else:
            ai_log(f"❌ Ошибка {response.status_code}: {response.text[:300]}")
            return None
    except Exception as e:
        ai_log(f"❌ Исключение: {str(e)}")
        return None

def parse_variants(result):
    variants = []
    lines = result.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("1.") or line.startswith("2.") or line.startswith("3."):
            text = line[2:].strip()
            if text:
                variants.append(text)
    return variants[:3]
