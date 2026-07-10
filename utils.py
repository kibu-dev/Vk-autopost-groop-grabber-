import re
import json
import vk_api
import time
import os
import threading
from datetime import datetime, timedelta

# ─── Файлы ───

GROUPS_FILE = "groups.json"
WORDS_FILE = "forbidden_words.json"
GRABBED_FILE = "grabbed_posts.json"
PUBLISHED_FILE = "published_posts.json"
SCHEDULED_FILE = "scheduled_posts.json"
PENDING_GRAB_FILE = "pending_grab.json"
LAST_PUB_FILE = "last_pub.json"
SKIPPED_FILE = "skipped_posts.json"
LIKER_GROUPS_FILE = "liker_groups.json"
LIKER_STATE_FILE = "liker_state.json"
LIKER_STATS_FILE = "liker_stats.json"
LIKED_FILE = "liked_posts.json"
ONLINE_STATE_FILE = "online_state.json"
FRIEND_STATE_FILE = "friend_state.json"
FRIEND_STATS_FILE = "friend_stats.json"
GROUP_ACCEPT_STATE_FILE = "group_accept_state.json"
GROUP_ACCEPT_STATS_FILE = "group_accept_stats.json"
MODERATION_FILE = "moderation.json"

_file_locks = {}

def _get_lock(filepath):
    if filepath not in _file_locks:
        _file_locks[filepath] = threading.Lock()
    return _file_locks[filepath]

def load_json(filepath, default=None):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(filepath, data):
    lock = _get_lock(filepath)
    with lock:
        try:
            tmp = filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, filepath)
        except Exception as e:
            print(f"Ошибка сохранения {filepath}: {e}")

# ─── Группы-доноры ───

def get_donor_groups():
    return load_json(GROUPS_FILE, {"groups": []}).get("groups", [])

def add_donor_group(group_id):
    data = load_json(GROUPS_FILE, {"groups": []})
    if group_id not in data["groups"]:
        data["groups"].append(group_id)
        save_json(GROUPS_FILE, data)

def remove_donor_group(group_id):
    data = load_json(GROUPS_FILE, {"groups": []})
    if group_id in data["groups"]:
        data["groups"].remove(group_id)
        save_json(GROUPS_FILE, data)

# ─── Запрещённые слова ───

def get_forbidden_words():
    return load_json(WORDS_FILE, {"words": []}).get("words", [])

def add_forbidden_word(word):
    data = load_json(WORDS_FILE, {"words": []})
    if word.lower() not in [w.lower() for w in data["words"]]:
        data["words"].append(word.lower())
        save_json(WORDS_FILE, data)

def remove_forbidden_word(word):
    data = load_json(WORDS_FILE, {"words": []})
    data["words"] = [w for w in data["words"] if w.lower() != word.lower()]
    save_json(WORDS_FILE, data)

# ─── Взятые посты ───

def is_post_grabbed(group_id, post_id):
    data = load_json(GRABBED_FILE, {"posts": []})
    return any(p["group_id"] == group_id and p["post_id"] == post_id for p in data["posts"])

def add_grabbed_post(group_id, post_id):
    data = load_json(GRABBED_FILE, {"posts": []})
    data["posts"].append({"group_id": group_id, "post_id": post_id, "date": datetime.now().strftime("%Y-%m-%d")})
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    data["posts"] = [p for p in data["posts"] if p["date"] >= cutoff]
    save_json(GRABBED_FILE, data)

def count_today_grabs(group_id):
    data = load_json(GRABBED_FILE, {"posts": []})
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for p in data["posts"] if p["group_id"] == group_id and p["date"] == today)

# ─── Отложенные посты ───

def get_next_free_hour():
    scheduled = load_json(SCHEDULED_FILE, {"posts": []})["posts"]
    now = datetime.now()
    hour = now.replace(minute=0, second=0, microsecond=0)
    if now.minute > 0:
        hour += timedelta(hours=1)
    while True:
        ts = int(hour.timestamp())
        if not any(p["time"] == ts for p in scheduled):
            return ts
        hour += timedelta(hours=1)

def get_next_schedule_time(interval):
    """Ближайший свободный слот для отложенной записи с шагом `interval` секунд.

    Первый пост уходит через `interval` от текущего момента, каждый следующий —
    на `interval` позже предыдущего запланированного, чтобы держать интервал 15 минут.
    """
    scheduled = load_json(SCHEDULED_FILE, {"posts": []})["posts"]
    now = int(time.time())
    ts = now + interval
    if scheduled:
        last = max(p["time"] for p in scheduled)
        if last + interval > ts:
            ts = last + interval
    taken = {p["time"] for p in scheduled}
    while ts in taken:
        ts += interval
    return ts

def add_scheduled_post(publish_date, text, from_group):
    data = load_json(SCHEDULED_FILE, {"posts": []})
    data["posts"].append({
        "time": publish_date,
        "text": text[:200],
        "from_group": from_group,
        "added_at": datetime.now().isoformat()
    })
    data["posts"].sort(key=lambda x: x["time"])
    save_json(SCHEDULED_FILE, data)

def get_scheduled_posts():
    data = load_json(SCHEDULED_FILE, {"posts": []})
    now = int(time.time())
    data["posts"] = [p for p in data["posts"] if p["time"] > now]
    save_json(SCHEDULED_FILE, data)
    return data["posts"]

def remove_scheduled_post(publish_time):
    data = load_json(SCHEDULED_FILE, {"posts": []})
    data["posts"] = [p for p in data["posts"] if p["time"] != publish_time]
    save_json(SCHEDULED_FILE, data)

# ─── Подозрительные граббера ───

def add_pending_grab(post, from_group, reason):
    data = load_json(PENDING_GRAB_FILE, {"posts": []})
    data["posts"].append({
        "post": {
            "id": post["id"],
            "text": post.get("text", ""),
            "attachments": build_attachments(post)
        },
        "from_group": from_group,
        "reason": reason,
        "added_at": datetime.now().isoformat()
    })
    save_json(PENDING_GRAB_FILE, data)

def get_pending_grabs():
    return load_json(PENDING_GRAB_FILE, {"posts": []})["posts"]

def remove_pending_grab(index):
    data = load_json(PENDING_GRAB_FILE, {"posts": []})
    if 0 <= index < len(data["posts"]):
        data["posts"].pop(index)
        save_json(PENDING_GRAB_FILE, data)
        return True
    return False

# ─── Пропущенные ───

def is_post_skipped(post_id):
    data = load_json(SKIPPED_FILE, {"posts": []})
    return post_id in data["posts"]

def add_skipped_post(post_id):
    data = load_json(SKIPPED_FILE, {"posts": []})
    if post_id not in data["posts"]:
        data["posts"].append(post_id)
        save_json(SKIPPED_FILE, data)

def remove_skipped_post(post_id):
    data = load_json(SKIPPED_FILE, {"posts": []})
    if post_id in data["posts"]:
        data["posts"].remove(post_id)
        save_json(SKIPPED_FILE, data)

def get_skipped_posts():
    return load_json(SKIPPED_FILE, {"posts": []})["posts"]

# ─── Опубликованные ───

def add_published_post(post_id, user_id, text):
    data = load_json(PUBLISHED_FILE, {"posts": []})
    data["posts"].append({"post_id": post_id, "user_id": user_id, "text": text[:200], "date": datetime.now().strftime("%Y-%m-%d")})
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    data["posts"] = [p for p in data["posts"] if p["date"] >= cutoff]
    save_json(PUBLISHED_FILE, data)

def get_user_posts(user_id):
    data = load_json(PUBLISHED_FILE, {"posts": []})
    return [p for p in data["posts"] if p["user_id"] == user_id]

def get_post_author(post_id):
    data = load_json(PUBLISHED_FILE, {"posts": []})
    for p in data["posts"]:
        if p["post_id"] == post_id:
            return p["user_id"]
    return None

def delete_user_post(user_id, post_id):
    data = load_json(PUBLISHED_FILE, {"posts": []})
    for p in data["posts"]:
        if p["post_id"] == post_id and p["user_id"] == user_id:
            data["posts"].remove(p)
            save_json(PUBLISHED_FILE, data)
            return True
    return False

# ─── Время публикации ───

def get_last_publish_time():
    return load_json(LAST_PUB_FILE, {"time": 0}).get("time", 0)

def save_last_publish_time(t):
    save_json(LAST_PUB_FILE, {"time": t})

# ─── Автолайкер ───

def get_liker_groups():
    return load_json(LIKER_GROUPS_FILE, {"groups": []}).get("groups", [])

def add_liker_group(group_id):
    data = load_json(LIKER_GROUPS_FILE, {"groups": []})
    if group_id not in data["groups"]:
        data["groups"].append(group_id)
        save_json(LIKER_GROUPS_FILE, data)

def remove_liker_group(group_id):
    data = load_json(LIKER_GROUPS_FILE, {"groups": []})
    if group_id in data["groups"]:
        data["groups"].remove(group_id)
        save_json(LIKER_GROUPS_FILE, data)

def is_liker_enabled():
    return load_json(LIKER_STATE_FILE, {"enabled": False}).get("enabled", False)

def set_liker_enabled(enabled):
    save_json(LIKER_STATE_FILE, {"enabled": enabled})

def get_liker_stats():
    return load_json(LIKER_STATS_FILE, {"today": 0, "total": 0, "date": ""})

def add_liker_stat():
    data = get_liker_stats()
    today = (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d")
    if data["date"] != today:
        data["today"] = 0
        data["date"] = today
    data["today"] += 1
    data["total"] += 1
    save_json(LIKER_STATS_FILE, data)

def get_liked_posts():
    return load_json(LIKED_FILE, {})

def save_liked_post(group_id, post_id):
    data = get_liked_posts()
    data[str(group_id)] = post_id
    save_json(LIKED_FILE, data)

# ─── Онлайн ───

def is_online_enabled():
    return load_json(ONLINE_STATE_FILE, {"enabled": False}).get("enabled", False)

def set_online_enabled(enabled):
    save_json(ONLINE_STATE_FILE, {"enabled": enabled})

# ─── Друзья ───

def is_friend_enabled():
    return load_json(FRIEND_STATE_FILE, {"enabled": False}).get("enabled", False)

def set_friend_enabled(enabled):
    save_json(FRIEND_STATE_FILE, {"enabled": enabled})

def get_friend_stats():
    return load_json(FRIEND_STATS_FILE, {"accepted": 0})

def add_friend_stat():
    data = get_friend_stats()
    data["accepted"] += 1
    save_json(FRIEND_STATS_FILE, data)

# ─── Приём в группу ───

def is_group_accept_enabled():
    return load_json(GROUP_ACCEPT_STATE_FILE, {"enabled": False}).get("enabled", False)

def set_group_accept_enabled(enabled):
    save_json(GROUP_ACCEPT_STATE_FILE, {"enabled": enabled})

def get_group_accept_stats():
    return load_json(GROUP_ACCEPT_STATS_FILE, {"accepted": 0})

def add_group_accept_stat():
    data = get_group_accept_stats()
    data["accepted"] += 1
    save_json(GROUP_ACCEPT_STATS_FILE, data)

# ─── Гороскоп ───

def get_horoscope_enabled():
    config = load_json("horoscope_config.json", {"enabled": False, "photo_id": "", "next_monday": ""})
    return config.get("enabled", False)

def set_horoscope_enabled(enabled):
    config = load_json("horoscope_config.json", {"enabled": False, "photo_id": "", "next_monday": ""})
    config["enabled"] = enabled
    save_json("horoscope_config.json", config)

def set_horoscope_photo(photo_id):
    config = load_json("horoscope_config.json", {"enabled": False, "photo_id": "", "next_monday": ""})
    config["photo_id"] = photo_id
    save_json("horoscope_config.json", config)

def get_horoscope_photo():
    config = load_json("horoscope_config.json", {"enabled": False, "photo_id": "", "next_monday": ""})
    return config.get("photo_id", "")

def get_horoscope_next_monday():
    config = load_json("horoscope_config.json", {"enabled": False, "photo_id": "", "next_monday": ""})
    return config.get("next_monday", "")

# ─── Проверки ───

def is_spam(text):
    if not text: return False
    words = get_forbidden_words()
    t = text.lower()
    return any(w in t for w in words)

def contains_any_link(text):
    if not text:
        return False
    patterns = [
        r'https?://[^\s]+',
        r'www\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}',
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False

def contains_anonymous(text):
    return any(kw in text.lower() for kw in ["анон", "анонимно", "аноним", "#анон", "#анонимно", "#аноним"])

def build_attachments(post):
    att = []
    for a in post.get("attachments", []):
        t = a["type"]; obj = a[t]
        oid = obj.get("owner_id"); iid = obj.get("id"); ak = obj.get("access_key", "")
        if oid and iid:
            s = f"{t}{oid}_{iid}"
            if ak: s += f"_{ak}"
            att.append(s)
    return ",".join(att) if att else None

def resolve_group_id(vk, identifier):
    identifier = identifier.strip().rstrip('/')
    if identifier.lstrip('-').isdigit(): return int(identifier)
    m = re.search(r'vk\.(?:com|ru)/(?:club|public|wall-)?([\w.]+)', identifier)
    if m: identifier = m.group(1)
    if identifier.lower().startswith('club'): identifier = identifier[4:]
    if identifier.isdigit(): return int(identifier)
    try: return vk.groups.getById(group_id=identifier)[0]["id"]
    except: return None

def get_user_name(vk, user_id):
    try:
        u = vk.users.get(user_ids=user_id, fields="first_name,last_name")[0]
        return u["first_name"], u["last_name"]
    except: return "Пользователь", ""

def get_group_name(vk, group_id):
    try: return vk.groups.getById(group_id=group_id)[0]["name"]
    except: return f"Группа {group_id}"

def send_message(vk, user_id, text, keyboard=None):
    try:
        vk.messages.send(user_id=user_id, message=text, random_id=0,
                         keyboard=keyboard.get_keyboard() if keyboard else None)
    except Exception as e: print(f"Ошибка отправки: {e}")

# ─── Модерация ───

def get_moderation_posts():
    return load_json(MODERATION_FILE, {"posts": []})["posts"]

def add_to_moderation(post_id, post_type, user_id, text, attachments_str, reason):
    data = load_json(MODERATION_FILE, {"posts": []})
    data["posts"] = [m for m in data["posts"] if m["post_id"] != post_id]
    data["posts"].append({
        "post_id": post_id,
        "post_type": post_type,
        "user_id": user_id,
        "text": text,
        "attachments": attachments_str or "",
        "reason": reason
    })
    save_json(MODERATION_FILE, data)

def remove_from_moderation(post_id):
    data = load_json(MODERATION_FILE, {"posts": []})
    data["posts"] = [m for m in data["posts"] if m["post_id"] != post_id]
    save_json(MODERATION_FILE, data)

def get_stats():
    return {
        "donor_count": len(get_donor_groups()),
        "pending_moderation": len(get_moderation_posts()) + len(get_pending_grabs()),
        "total_published": len(load_json(PUBLISHED_FILE, {"posts": []})["posts"]),
        "total_grabbed": len(load_json(GRABBED_FILE, {"posts": []})["posts"]),
        "scheduled_count": len(get_scheduled_posts()),
    }

def moderate_post(vk_user, post_id, uid, text, attachments_str, reason, post_type="suggestion"):
    from config import ADMIN_ID, GROUP_TOKEN, GROUP_ID
    add_to_moderation(post_id, post_type, uid, text, attachments_str or "", reason)
    if ADMIN_ID:
        try:
            vk_group = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
            from keyboards import get_moderation_keyboard
            kb = get_moderation_keyboard(post_id)
            try:
                u = vk_user.users.get(user_ids=uid, fields="first_name,last_name")[0]
                author = f"{u['first_name']} {u['last_name']}"
            except: author = f"id{uid}"
            msg = f"🚨 ПОДОЗРИТЕЛЬНЫЙ ПОСТ ({reason})\n\nАвтор: {author}\n\nТекст:\n{text[:500]}\n\nID: {post_id}"
            if attachments_str: msg += "\n📎 Есть вложения"
            vk_group.messages.send(user_id=ADMIN_ID, message=msg, random_id=0, keyboard=kb.get_keyboard(), group_id=GROUP_ID)
        except Exception as e: print(f"Ошибка уведомления: {e}")
