import re
import json
import vk_api
from datetime import datetime, timedelta

GROUPS_FILE = "groups.json"
WORDS_FILE = "forbidden_words.json"
GRABBED_FILE = "grabbed_posts.json"
PUBLISHED_FILE = "published_posts.json"

def load_json(filepath, default=None):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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

# ─── Опубликованные посты ───

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

# ─── Проверки ───

def is_spam(text):
    if not text: return False
    words = get_forbidden_words()
    t = text.lower()
    return any(w in t for w in words)

def contains_any_link(text):
    if not text: return False
    for p in [r'https?://[^\s]+', r'www\.[^\s]+', r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*']:
        if re.search(p, text, re.IGNORECASE): return True
    return False

def contains_anonymous(text):
    return any(kw in text.lower() for kw in ["анон", "анонимно", "аноним", "#анон", "#анонимно", "#аноним"])

# ─── Вложения ───

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

# ─── ID группы ───

def resolve_group_id(vk, identifier):
    identifier = identifier.strip().rstrip('/')
    if identifier.lstrip('-').isdigit(): return int(identifier)
    m = re.search(r'vk\.(?:com|ru)/(?:club|public|wall-)?([\w.]+)', identifier)
    if m: identifier = m.group(1)
    if identifier.lower().startswith('club'): identifier = identifier[4:]
    if identifier.isdigit(): return int(identifier)
    try: return vk.groups.getById(group_id=identifier)[0]["id"]
    except: return None

# ─── API ───

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

# ─── Модерация (в памяти) ───

moderation_queue = []

def add_to_moderation(post_id, post_type, user_id, text, attachments_str, reason):
    global moderation_queue
    moderation_queue = [m for m in moderation_queue if m["post_id"] != post_id]
    moderation_queue.append({"post_id": post_id, "post_type": post_type, "user_id": user_id,
                             "text": text, "attachments": attachments_str, "reason": reason})

def get_moderation_posts():
    return moderation_queue[-10:]

def remove_from_moderation(post_id):
    global moderation_queue
    moderation_queue = [m for m in moderation_queue if m["post_id"] != post_id]

def get_stats():
    return {
        "donor_count": len(get_donor_groups()),
        "pending_moderation": len(moderation_queue),
        "total_user_posts": len(load_json(PUBLISHED_FILE, {"posts": []})["posts"]),
        "total_grabbed": len(load_json(GRABBED_FILE, {"posts": []})["posts"])
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
