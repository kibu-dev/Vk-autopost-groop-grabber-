import requests
from config import OPENROUTER_API_KEY

PROMPT_FILE = "prompt.txt"

def load_prompt():
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Улучши этот текст: {text}"

def generate_variants(text):
    if not OPENROUTER_API_KEY:
        print("❌ Нет API ключа")
        return None
    
    prompt = load_prompt().replace("{text}", text)
    
    try:
        print(f"📤 Отправляю запрос...")
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
        
        print(f"📥 Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            print(f"❌ OpenRouter ошибка: {response.status_code}")
            print(f"Ответ: {response.text[:500]}")
            return None
    except Exception as e:
        print(f"❌ OpenRouter ошибка: {e}")
        return None

def parse_variants(result):
    """Разбирает ответ ИИ на 3 варианта"""
    variants = []
    lines = result.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("1.") or line.startswith("2.") or line.startswith("3."):
            text = line[2:].strip()
            if text:
                variants.append(text)
    return variants[:3]
