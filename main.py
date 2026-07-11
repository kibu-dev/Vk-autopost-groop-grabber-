# main.py — полностью

import multiprocessing
import threading
import logging
import sys
from logging.handlers import RotatingFileHandler
from config import *
from grabber import run_grabber
from messenger import run_messenger
from group_acceptor import run_group_acceptor
from weekly_horoscope import run_weekly_horoscope
from suggestion_checker import run_suggestion_checker

def start_reddit():
    from reddit_handler import run_reddit_handler
    run_reddit_handler()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

console = logging.StreamHandler(sys.stdout)
console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
logger.addHandler(console)

file_handler = RotatingFileHandler('bot.log', maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(file_handler)

logging.info("🚀 Бот запускается...")

if __name__ == "__main__":
    if not GROUP_TOKEN or not GROUP_ID:
        logging.error("❌ Проверьте .env (GROUP_TOKEN, GROUP_ID)")
        exit(1)

    threading.Thread(target=run_grabber, daemon=True).start()
    threading.Thread(target=run_group_acceptor, daemon=True).start()
    threading.Thread(target=run_weekly_horoscope, daemon=True).start()

    # Обработчик «Предложить пост» — скачивает фото и ставит в отложенные
    threading.Thread(target=run_suggestion_checker, daemon=True).start()

    # Reddit handler в отдельном процессе
    multiprocessing.Process(target=start_reddit, daemon=True).start()

    run_messenger()
