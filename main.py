import threading
from config import *
from grabber import run_grabber
from pub_grabber import run_pub_grabber
from pub_users import run_pub_users
from messenger import run_messenger

if __name__ == "__main__":
    if not USER_TOKEN or not GROUP_TOKEN or not GROUP_ID:
        print("❌ Проверьте .env"); exit(1)
    
    threading.Thread(target=run_grabber, daemon=True).start()
    threading.Thread(target=run_pub_grabber, daemon=True).start()
    threading.Thread(target=run_pub_users, daemon=True).start()
    
    print("🚀 Бот запущен!")
    run_messenger()
