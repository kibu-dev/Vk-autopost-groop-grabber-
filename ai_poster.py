# ai_poster.py — полностью (возвращаем g4f)

import time
import logging
from g4f.client import Client
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

def generate_text(prompt, max_tokens=1500):
    """Генерация текста через g4f"""
    try:
        ai_log(f"G4F запрос: {prompt[:100]}")
        time.sleep(2)
        client = Client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        result = response.choices[0].message.content
        ai_log(f"G4F ответ: {result[:200] if result else 'нет'}...")
        return result
    except Exception as e:
        ai_log(f"G4F ошибка: {e}")
        return None

def generate_variants(text):
    prompt = load_prompt().replace("{text}", text)
    return generate_text(prompt)

def parse_variants(result):
    if not result or len(result.strip()) <= 20:
        return []
    import re
    parts = re.split(r'(?:Вариант|Variant)\s*\d+[.:]\s*', result)
    parts = [p.strip() for p in parts if len(p.strip()) > 20]
    if len(parts) >= 2:
        return parts
    return [result.strip()]

def translate_text(text, target='ru'):
    try:
        if not text or len(text.strip()) < 5:
            return None
        translated = GoogleTranslator(source='auto', target=target).translate(text[:3000])
        return translated
    except Exception as e:
        ai_log(f"Перевод ошибка: {e}")
        return None

def is_russian(text):
    if not text or len(text.strip()) < 5:
        return True
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    cyrillic = sum(1 for c in letters if 'а' <= c.lower() <= 'я')
    return cyrillic / len(letters) >= 0.5

def rewrite_text(text):
    if not text or len(text.strip()) < 10:
        return None
    prompt = f"""Перефразируй этот текст своими словами, сохрани смысл и стиль.

Пиши живым, разговорным языком. Не используй Markdown. Сохрани все эмодзи, если они были. Объём примерно как оригинал.

{text[:2000]}"""
    return generate_text(prompt, max_tokens=2000)
