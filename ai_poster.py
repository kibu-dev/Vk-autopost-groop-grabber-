import logging
import requests
from datetime import datetime
from config import YANDEX_API_KEY, YANDEX_FOLDER_ID

PROMPT_FILE = "prompt.txt"
IAM_TOKEN = None
IAM_TOKEN_EXPIRES = 0

def ai_log(message):
    logging.info(f"AI: {message}")

def load_prompt():
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Напиши пост на тему: {text}"

def get_iam_token():
    global IAM_TOKEN, IAM_TOKEN_EXPIRES
    now = int(datetime.now().timestamp())
    if IAM_TOKEN and now < IAM_TOKEN_EXPIRES:
        return IAM_TOKEN
    try:
        resp = requests.post("https://iam.api.cloud.yandex.net/iam/v1/tokens", json={"yandexPassportOauthToken": YANDEX_API_KEY})
        data = resp.json()
        IAM_TOKEN = data.get("iamToken")
        IAM_TOKEN_EXPIRES = now + 3600
        return IAM_TOKEN
    except Exception as e:
        logging.error(f"IAM ошибка: {e}")
        return None

def generate_text(prompt):
    if not YANDEX_API_KEY:
        logging.error("Нет YANDEX_API_KEY")
        return None
    
    iam = get_iam_token()
    if not iam:
        return None
    
    logging.info(f"YandexGPT: {prompt[:100]}")
    
    try:
        response = requests.post(
            f"https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers={"Authorization": f"Bearer {iam}", "Content-Type": "application/json"},
            json={
                "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
                "completionOptions": {"maxTokens": 1500, "temperature": 0.7},
                "messages": [{"role": "user", "text": prompt}]
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data["result"]["alternatives"][0]["message"]["text"]
            logging.info(f"YandexGPT ответ: {result[:200]}...")
            return result
        else:
            logging.error(f"YandexGPT ошибка {response.status_code}: {response.text[:300]}")
            return None
    except Exception as e:
        logging.error(f"YandexGPT ошибка: {e}")
        return None

def generate_variants(text):
    prompt = load_prompt().replace("{text}", text)
    return generate_text(prompt)

def parse_variants(result):
    if result and len(result.strip()) > 20:
        return [result.strip()]
    return []
