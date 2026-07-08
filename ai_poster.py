import logging
from duckduckgo_search import DDGS
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
    """Генерация текста через DuckDuckGo AI Chat"""
    try:
        ai_log(f"DDG запрос: {prompt[:100]}")
        with DDGS() as ddgs:
            result = ddgs.chat(prompt, model='gpt-4o-mini')
            ai_log(f"DDG ответ: {result[:200] if result else 'нет'}...")
            return result
    except Exception as e:
        ai_log(f"DDG ошибка: {e}")
        return None

def generate_variants(text):
    """Генерация поста через prompt.txt"""
    prompt = load_prompt().replace("{text}", text)
    return generate_text(prompt)

def parse_variants(result):
    if result and len(result.strip()) > 20:
        return [result.strip()]
    return []

def translate_text(text, target='ru'):
    """Перевод текста через Google Translate"""
    try:
        if not text or len(text.strip()) < 5:
            return None
        translated = GoogleTranslator(source='auto', target=target).translate(text[:3000])
        return translated
    except Exception as e:
        ai_log(f"Перевод ошибка: {e}")
        return None
