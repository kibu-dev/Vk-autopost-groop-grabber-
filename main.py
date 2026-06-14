import os
import threading
from db import init_db, migrate_forbidden_words_from_json
from config import USER_TOKEN, GROUP_TOKEN, GROUP_ID
from grabber import run_grabber
from publisher import run_publisher
from messenger import run_messenger

if __name__ == "__main__":
    if not USER_TOKEN or not GROUP_TOKEN or not GROUP_ID:
        print("❌ Ошибка: проверьте USER_TOKEN, GROUP_TOKEN, GROUP_ID в .env")
        exit(1)
    
    init_db()
    print("✅ База данных готова")
    
    if os.path.exists("forbidden_words.json"):
        migrate_forbidden_words_from_json()
        os.rename("forbidden_words.json", "forbidden_words.json.bak")
        print("✅ JSON со словами перенесён в БД")
    
    threading.Thread(target=run_grabber, daemon=True).start()
    threading.Thread(target=run_publisher, daemon=True).start()
    
    print("🚀 Бот запущен!")
    run_messenger()
