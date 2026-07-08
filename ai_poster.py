# ai_poster.py
import time
import logging
from deep_translator import GoogleTranslator

PROMPT_FILE = "prompt.txt"

def ai_log(message):
    logging.info(f"AI: {message}")

def load_prompt():
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Напиши пост на тему: {text}"

def generate_text(prompt):
    """Генерация текста через g4f"""
    try:
        ai_log(f"G4F запрос: {prompt[:100]}")
        time.sleep(2)
        from g4f.client import Client
        client = Client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        result = response.choices[0].message.content
        ai_log(f"G4F ответ: {result[:200]}...")
        return result
    except Exception as e:
        ai_log(f"G4F ошибка: {e}")
        return None

def generate_variants(text):
    prompt = load_prompt().replace("{text}", text)
    return generate_text(prompt)

def parse_variants(result):
    if result and len(result.strip()) > 20:
        return [result.strip()]
    return []

def translate_text(text, target='ru'):
    try:
        if not text or len(text.strip()) < 5:
            return None
        translated = GoogleTranslator(source='auto', target=target).translate(text[:3000])
        return translated
    except Exception as e:
        ai_log(f"Перевод ошибка: {e}")
        return None
