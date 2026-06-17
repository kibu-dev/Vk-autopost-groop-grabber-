import time
import vk_api
from config import *
from utils import *

def run_online_keeper():
    vk = vk_api.VkApi(token=USER_TOKEN).get_api()
    print("🟢 Онлайн запущен")

    while True:
        try:
            if is_online_enabled():
                vk.account.setOnline()
                print("🟢 Онлайн")
                time.sleep(240)
            else:
                time.sleep(10)
        except Exception as e:
            print(f"🟢 Ошибка: {e}")
            time.sleep(60)
