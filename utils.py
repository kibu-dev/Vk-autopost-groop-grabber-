import re
import json
import vk_api
from datetime import datetime, timedelta

# ─── JSON файлы ───

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
    data = load_json(GROUPS_FILE, {"groups": []})
    return data.get("groups", [])

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
    data = load_json(WORDS_FILE, {"words": []})
    return data.get("words", [])

def add_forbidden_word(word):
    data = load_json(WORDS_FILE, {"words": []})
    if word.lower() not in [w.lower() for w in data["words"]]:
        data["words"].append(word.lower())
        save_json(WORDS_FILE, data)

def remove_forbidden_word(word):
    data = load_json(WORDS_FILE, {"words": []})
    data["words"] = [w for w in data["words"] if w.lower() != word.lower()]
    save_json(WORDS_FILE, data)

# ─── Взятые посты (граббер) ───

def is_post_grabbed(group_id, post_id):
    data = load_json(GRABBED_FILE, {"posts": []})
    for p in data["posts"]:
        if p["group_id"] == group_id and p["post_id"] == post_id:
            return True
    return False

def add_grabbed_post(group_id, post_id):
    data = load_json(GRABBED_FILE, {"posts": []})
    data["posts"].append({
        "group_id": group_id,
        "post_id": post_id,
        "date": datetime.now().strftime("%Y-%m-%d")
    })
    # Чистка старше 30 дней
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
    data["posts"].append({
        "post_id": post_id,
        "user_id": user_id,
        "text": text[:200],
        "date": datetime.now().strftime("%Y-%m-%d")
    })
    # Чистка старше 30 дней
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

# ─── Проверки текста ───

def is_spam(text):
    if not text:
        return False
    words = get_forbidden_words()
    text_lower = text.lower()
    for w in words:
        if w in text_lower:
            return True
    return False

def contains_any_link(text):
    if not text:
        return False
    patterns = [
        r'https?://[^\s]+',
        r'www\.[^\s]+',
        r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*'
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False

def contains_anonymous(text):
    keywords = ["анон", "анонимно", "аноним", "#анон", "#анонимно", "#аноним"]
    for kw in keywords:
        if kw in text.lower():
            return True
    return False

# ─── Вложения ───

def build_attachments(post):
    attachments = []
    for a in post.get("attachments", []):
        t = a["type"]
        obj = a[t]
        owner_id = obj.get("owner_id")
        item_id = obj.get("id")
        access_key = obj.get("access_key", "")
        if owner_id and item_id:
            attachment = f"{t}{owner_id}_{item_id}"
            if access_key:
                attachment += f"_{access_key}"
            attachments.append(attachment)
    return ",".join(attachments) if attachments else None

# ─── ID группы ───

def resolve_group_id(vk, identifier):
    identifier = identifier.strip().rstrip('/')
    if identifier.lstrip('-').isdigit():
        return int(identifier)
    match = re.search(r'vk\.(?:com|ru)/(?:club|public|wall-)?([\w.]+)', identifier)
    if match:
        identifier = match.group(1)
    if identifier.lower().startswith('club'):
        identifier = identifier[4:]
    if identifier.isdigit():
        return int(identifier)
    try:
        result = vk.groups.getById(group_id=identifier)
        return result[0]["id"]
    except:
        return None

# ─── API ───

def get_user_name(vk, user_id):
    try:
        user = vk.users.get(user_ids=user_id, fields="first_name,last_name")[0]
        return user["first_name"], user["last_name"]
    except:
        return "Пользователь", ""

def get_group_name(vk, group_id):
    try:
        group = vk.groups.getById(group_id=group_id)[0]
        return group["name"]
    except:
        return f"Группа {group_id}"

def send_message(vk, user_id, text, keyboard=None):
    try:
        vk.messages.send(
            user_id=user_id,
            message=text,
            random_id=0,
            keyboard=keyboard.get_keyboard() if keyboard else None,
        )
    except Exception as e:
        print(f"Ошибка отправки: {e}")

# ─── Модерация ───

# В памяти, при перезапуске сбрасывается — норм для модерации
moderation_queue = []

def add_to_moderation(post_id, post_type, user_id, text, attachments_str, reason):
    global moderation_queue
    # Удаляем старые записи этого поста
    moderation_queue = [m for m in moderation_queue if m["post_id"] != post_id]
    moderation_queue.append({
        "post_id": post_id,
        "post_type": post_type,
        "user_id": user_id,
        "text": text,
        "attachments": attachments_str,
        "reason": reason
    })

def get_moderation_posts():
    return moderation_queue[-10:]

def remove_from_moderation(post_id):
    global moderation_queue
    moderation_queue = [m for m in moderation_queue if m["post_id"] != post_id]

def get_stats():
    donor_count = len(get_donor_groups())
    mod_count = len(moderation_queue)
    user_posts = len(load_json(PUBLISHED_FILE, {"posts": []})["posts"])
    grabbed = len(load_json(GRABBED_FILE, {"posts": []})["posts"])
    return {
        "donor_count": donor_count,
        "pending_moderation": mod_count,
        "total_user_posts": user_posts,
        "total_grabbed": grabbed
    }

def moderate_post(vk_user, post_id, uid, text, attachments_str, reason, post_type="suggestion"):
    from config import ADMIN_ID, GROUP_TOKEN, GROUP_ID
    
    add_to_moderation(post_id, post_type, uid, text, attachments_str or "", reason)
    
    if ADMIN_ID:
        try:
            vk_group = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131").get_api()
            from keyboards import get_moderation_keyboard
            keyboard = get_moderation_keyboard(post_id)
            
            try:
                user = vk_user.users.get(user_ids=uid, fields="first_name,last_name")[0]
                author = f"{user['first_name']} {user['last_name']}"
            except:
                author = f"id{uid}"
            
            msg = f"🚨 ПОДОЗРИТЕЛЬНЫЙ ПОСТ ({reason})\n\nАвтор: {author}\n\nТекст:\n{text[:500]}\n\nID: {post_id}"
            if attachments_str:
                msg += "\n📎 Есть вложения"
            
            vk_group.messages.send(
                user_id=ADMIN_ID,
                message=msg,
                random_id=0,
                keyboard=keyboard.get_keyboard(),
                group_id=GROUP_ID
            )
            print(f"✅ Уведомление админу (пост {post_id})")
        except Exception as e:
            print(f"Ошибка уведомления: {e}")
