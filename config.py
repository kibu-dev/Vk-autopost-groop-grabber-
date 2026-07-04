import os
from dotenv import load_dotenv

load_dotenv()

USER_TOKEN = os.getenv("USER_TOKEN")
GROUP_TOKEN = os.getenv("GROUP_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "900"))
GRAB_INTERVAL = int(os.getenv("GRAB_INTERVAL", "900"))
GRAB_POSTS_PER_GROUP = int(os.getenv("GRAB_POSTS_PER_GROUP", "3"))
MAX_GRAB_PER_GROUP_DAY = int(os.getenv("MAX_GRAB_PER_GROUP_DAY", "3"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
