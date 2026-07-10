import time
import vk_api
from config import *
from utils import *

def run_group_acceptor():
    vk = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
    print("👥 Приём в группу запущен")

    while True:
        try:
            if is_group_accept_enabled():
                requests = vk.groups.getRequests(group_id=GROUP_ID, count=100)
                if requests["items"]:
                    for user_id in requests["items"]:
                        vk.groups.approveRequest(group_id=GROUP_ID, user_id=user_id)
                        add_group_accept_stat()
                        print(f"👥 Принят в группу: {user_id}")
                        time.sleep(1)
                else:
                    print("👥 Нет заявок в группу")
                time.sleep(300)
            else:
                time.sleep(10)
        except Exception as e:
            print(f"👥 Ошибка: {e}")
            time.sleep(60)
