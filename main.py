import os
import threading
from db import init_db, migrate_forbidden_words_from_json
from config import DEFAULT_DONORS, USER_TOKEN, GROUP_TOKEN, GROUP_ID
from grabber import run_grabber
from publisher import run_publisher
from messenger import run_messenger
from db import add_donor_group, get_donor_groups

if __name__ == "__main__":
    # Проверка конфига
    if not USER_TOKEN or not GROUP_TOKEN or not GROUP_ID:
        print("❌ Ошибка: проверьте USER_TOKEN, GROUP_TOKEN, GROUP_ID в .env")
        exit(1)
    
    # Инициализация БД
    init_db()
    print("✅ База данных готова")
    
    # Переносим слова из JSON в БД (однократно)
    if os.path.exists("forbidden_words.json"):
        migrate_forbidden_words_from_json()
        os.rename("forbidden_words.json", "forbidden_words.json.bak")
        print("✅ JSON со словами перенесён в БД, файл переименован в .bak")
    
    # Добавляем группы-доноры из .env если есть
    existing_donors = get_donor_groups()
    for g in DEFAULT_DONORS:
        if g not in existing_donors:
            add_donor_group(g)
            print(f"➕ Добавлена группа-донор из .env: {g}")
    
    # Запускаем потоки
    threading.Thread(target=run_grabber, daemon=True).start()
    threading.Thread(target=run_publisher, daemon=True).start()
    
    print("🚀 Бот запущен!")
    
    # Основной процесс
    run_messenger()
