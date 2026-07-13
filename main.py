# main.py — полностью (без граббера и акцептора)

import multiprocessing
import threading
import logging
import sys
from logging.handlers import RotatingFileHandler
from config import *
from messenger import run_messenger
from weekly_horoscope import run_weekly_horoscope

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

    threading.Thread(target=run_weekly_horoscope, daemon=True).start()
    multiprocessing.Process(target=start_reddit, daemon=True).start()
    run_messenger()
