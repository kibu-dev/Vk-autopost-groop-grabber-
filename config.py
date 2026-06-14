import os
from dotenv import load_dotenv

load_dotenv()

# Основные токены
USER_TOKEN = os.getenv("USER_TOKEN")
GROUP_TOKEN = os.getenv("GROUP_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Интервалы (в секундах)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "900"))
GRAB_INTERVAL = int(os.getenv("GRAB_INTERVAL", "1800"))

# Граббер
GRAB_POSTS_PER_GROUP = int(os.getenv("GRAB_POSTS_PER_GROUP", "3"))
MAX_GRAB_PER_GROUP_DAY = int(os.getenv("MAX_GRAB_PER_GROUP_DAY", "2"))

# ID групп-доноров (по умолчанию пусто, админ добавит через бота)
DONOR_GROUPS_STR = os.getenv("DONOR_GROUPS", "")
DEFAULT_DONORS = [int(g.strip()) for g in DONOR_GROUPS_STR.split(",") if g.strip().isdigit()]

# Настройки поста от граббера
GRABBER_POST_PREFIX = os.getenv("GRABBER_POST_PREFIX", "")  # можно добавить хештег, например "#юмор"
GRABBER_POST_SUFFIX = os.getenv("GRABBER_POST_SUFFIX", "")  # подпись в конце, если нужна
