import re
import json
import vk_api
from db import get_forbidden_words, add_to_moderation

def load_json_file(filepath, default=None):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def save_json_file(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_spam(text):
    if not text:
        return False
    forbidden_words = get_forbidden_words()
    text_lower = text.lower()
    for word in forbidden_words:
        if word in text_lower:
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
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def contains_anonymous(text):
    keywords = ["анон", "анонимно", "аноним", "#анон", "#анонимно", "#аноним"]
    for kw in keywords:
        if kw in text.lower():
            return True
    return False

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

def parse_attachments_string(attachments_str):
    if not attachments_str:
        return None
    return attachments_str

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
            print(f"✅ Уведомление админу отправлено (пост {post_id}, {reason})")
        except Exception as e:
            print(f"Ошибка уведомления админа: {e}")
