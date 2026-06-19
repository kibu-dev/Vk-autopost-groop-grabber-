import threading
from config import *
from grabber import run_grabber
from pub_users import run_pub_users
from messenger import run_messenger
from auto_liker import run_auto_liker
from online_keeper import run_online_keeper
from friend_acceptor import run_friend_acceptor
from group_acceptor import run_group_acceptor

if __name__ == "__main__":
    if not USER_TOKEN or not GROUP_TOKEN or not GROUP_ID:
        print("❌ Проверьте .env"); exit(1)

    threading.Thread(target=run_grabber, daemon=True).start()
    threading.Thread(target=run_pub_users, daemon=True).start()
    threading.Thread(target=run_auto_liker, daemon=True).start()
    threading.Thread(target=run_online_keeper, daemon=True).start()
    threading.Thread(target=run_friend_acceptor, daemon=True).start()
    threading.Thread(target=run_group_acceptor, daemon=True).start()

    print("🚀 Бот запущен!")
    run_messenger()
