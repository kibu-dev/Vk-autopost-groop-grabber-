# config.py — полностью

import os
from dotenv import load_dotenv

load_dotenv()

GROUP_TOKEN = os.getenv("GROUP_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "900"))
GRAB_INTERVAL = int(os.getenv("GRAB_INTERVAL", "900"))
GRAB_POSTS_PER_GROUP = int(os.getenv("GRAB_POSTS_PER_GROUP", "3"))
MAX_GRAB_PER_GROUP_DAY = int(os.getenv("MAX_GRAB_PER_GROUP_DAY", "3"))

# Часовой пояс: Иркутск UTC+8 (сервер UTC+3, поправка +5)
TIMEZONE_OFFSET = int(os.getenv("TIMEZONE_OFFSET", "8"))
