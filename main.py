import threading
import logging
import sys
from logging.handlers import RotatingFileHandler
from config import *
from grabber import run_grabber
from pub_users import run_pub_users
from messenger import run_messenger
from auto_liker import run_auto_liker
from online_keeper import run_online_keeper
from friend_acceptor import run_friend_acceptor
from group_acceptor import run_group_acceptor

# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Вывод в консоль (Bothost видит)
console = logging.StreamHandler(sys.stdout)
console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
logger.addHandler(console)

# Вывод в файл с ротацией
file_handler = RotatingFileHandler('bot.log', maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(file_handler)

logging.info("🚀 Бот запускается...")

if __name__ == "__main__":
    if not USER_TOKEN or not GROUP_TOKEN or not GROUP_ID:
        logging.error("❌ Проверьте .env")
        exit(1)

    threading.Thread(target=run_grabber, daemon=True).start()
    threading.Thread(target=run_pub_users, daemon=True).start()
    threading.Thread(target=run_auto_liker, daemon=True).start()
    threading.Thread(target=run_online_keeper, daemon=True).start()
    threading.Thread(target=run_friend_acceptor, daemon=True).start()
    threading.Thread(target=run_group_acceptor, daemon=True).start()

    run_messenger()
