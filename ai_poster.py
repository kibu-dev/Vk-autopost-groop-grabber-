import logging
from datetime import datetime
from groq import Groq
from config import GROQ_API_KEY

PROMPT_FILE = "prompt.txt"

def ai_log(message):
    """Заглушка для совместимости со старым кодом"""
    logging.info(f"AI: {message}")

def load_prompt():
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Напиши пост на тему: {text}"

def generate_text(prompt):
    if not GROQ_API_KEY:
        logging.error("Нет GROQ_API_KEY")
        return None
    
    logging.info(f"GROQ: {prompt[:100]}")
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="qwen/qwen-3-32b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7
        )
        result = response.choices[0].message.content
        logging.info(f"GROQ ответ: {result[:200]}...")
        return result
    except Exception as e:
        logging.error(f"GROQ ошибка: {e}")
        return None

def generate_variants(text):
    prompt = load_prompt().replace("{text}", text)
    return generate_text(prompt)

def parse_variants(result):
    if result and len(result.strip()) > 20:
        return [result.strip()]
    return []
