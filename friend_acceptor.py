import time
import vk_api
from config import *
from utils import *

def run_friend_acceptor():
    vk = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    print("🤝 Друзья запущены")

    while True:
        try:
            if is_friend_enabled():
                requests = vk.friends.getRequests(out=0, count=50)
                if requests["items"]:
                    for user_id in requests["items"]:
                        vk.friends.add(user_id=user_id)
                        add_friend_stat()
                        print(f"🤝 Принят: {user_id}")
                        time.sleep(1)
                time.sleep(900)
            else:
                time.sleep(10)
        except Exception as e:
            print(f"🤝 Ошибка: {e}")
            time.sleep(60)
