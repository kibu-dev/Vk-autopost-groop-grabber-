import re
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from config import *
from utils import *
from keyboards import *

waiting_support = set()
selected_post = {}
admin_state = {}

def run_messenger():
    vk_session = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131")
    vk = vk_session.get_api()
    vk_user_session = vk_api.VkApi(token=USER_TOKEN, api_version="5.131")
    vk_user = vk_user_session.get_api()
    longpoll = VkLongPoll(vk_session, group_id=GROUP_ID, mode=2, preload_messages=True)

    print("🤖 ЛС бот запущен")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text.strip() if event.text else ""
            is_admin = (user_id == ADMIN_ID)
            
            # ─── СОСТОЯНИЯ ───
            if is_admin and user_id in admin_state:
                state = admin_state[user_id]
                mode = state.get("mode")
                
                if mode in ["add_donor", "del_donor", "add_word", "del_word"]:
                    if text.lower() in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                        continue
                    
                    if mode == "add_donor":
                        gid = resolve_group_id(vk_user, text.strip())
                        if gid:
                            add_donor_group(gid)
                            name = get_group_name(vk_user, gid)
                            send_message(vk, user_id, f"✅ Группа [{name}] добавлена!", get_donor_groups_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не удалось найти группу.", get_back_admin_keyboard())
                    
                    elif mode == "del_donor":
                        gid = resolve_group_id(vk_user, text.strip())
                        if gid and gid in get_donor_groups():
                            remove_donor_group(gid)
                            send_message(vk, user_id, f"✅ Группа удалена!", get_donor_groups_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не найдена.", get_back_admin_keyboard())
                    
                    elif mode == "add_word":
                        word = text.strip().lower()
                        add_forbidden_word(word)
                        send_message(vk, user_id, f"✅ '{word}' добавлено!", get_forbidden_words_keyboard())
                    
                    elif mode == "del_word":
                        word = text.strip().lower()
                        if word in get_forbidden_words():
                            remove_forbidden_word(word)
                            send_message(vk, user_id, f"✅ '{word}' удалено!", get_forbidden_words_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не найдено.", get_forbidden_words_keyboard())
                    
                    admin_state.pop(user_id, None)
                    continue
            
            # ─── ПОДДЕРЖКА ───
            if user_id in waiting_support:
                if text.lower() in ["🔙 отмена", "/cancel"]:
                    waiting_support.discard(user_id)
                    kb = get_admin_main_keyboard() if is_admin else get_main_keyboard()
                    send_message(vk, user_id, "❌ Отменено.", kb)
                else:
                    waiting_support.discard(user_id)
                    msg_id = event.message_id if hasattr(event, 'message_id') else event.id
                    if ADMIN_ID:
                        try:
                            vk.messages.send(
                                user_id=ADMIN_ID,
                                message=f"📨 ОБРАЩЕНИЕ\nhttps://vk.com/gim{GROUP_ID}?sel={user_id}",
                                random_id=0, forward_messages=msg_id, group_id=GROUP_ID
                            )
                            send_message(vk, user_id, "✅ Отправлено!", get_main_keyboard())
                        except:
                            send_message(vk, user_id, "❌ Ошибка.", get_main_keyboard())
                continue
            
            # ─── ОСНОВНЫЕ ───
            text_lower = text.lower()
            
            if text_lower in ["начать", "меню", "start"]:
                kb = get_admin_main_keyboard() if is_admin else get_main_keyboard()
                send_message(vk, user_id, "👋 Привет!", kb)
                continue
            
            if text_lower == "🗑 удалить мой пост":
                posts = get_user_posts(user_id)
                if not posts:
                    send_message(vk, user_id, "📭 Нет постов.", get_main_keyboard())
                else:
                    send_message(vk, user_id, f"📋 Постов: {len(posts)}", get_posts_keyboard(posts))
                continue
            
            if text_lower == "🆘 написать в поддержку":
                waiting_support.add(user_id)
                send_message(vk, user_id, "📝 Пишите:", get_cancel_keyboard())
                continue
            
            if text_lower == "🔙 отмена":
                kb = get_admin_main_keyboard() if is_admin else get_main_keyboard()
                send_message(vk, user_id, "Меню:", kb)
                continue
            
            if text_lower == "❌ нет":
                selected_post.pop(user_id, None)
                send_message(vk, user_id, "Отменено.", get_main_keyboard())
                continue
            
            if text_lower == "✅ да, удалить":
                if user_id in selected_post:
                    pid = selected_post[user_id]
                    if get_post_author(pid) == user_id:
                        try:
                            vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                            delete_user_post(user_id, pid)
                            send_message(vk, user_id, f"✅ Пост #{pid} удалён!", get_main_keyboard())
                            selected_post.pop(user_id, None)
                        except Exception as e:
                            send_message(vk, user_id, f"❌ {e}", get_main_keyboard())
                    else:
                        send_message(vk, user_id, "❌ Не ваш пост!", get_main_keyboard())
                else:
                    send_message(vk, user_id, "Сначала выберите пост.", get_main_keyboard())
                continue
            
            if text_lower.startswith("🗑 "):
                match = re.search(r"🗑 (\d+)\.", text)
                if match:
                    idx = int(match.group(1)) - 1
                    posts = get_user_posts(user_id)
                    if 0 <= idx < len(posts):
                        selected_post[user_id] = posts[idx]['post_id']
                        send_message(vk, user_id, f"⚠️ Удалить пост #{posts[idx]['post_id']}?", get_confirm_keyboard())
                continue
            
            # ─── АДМИН ───
            if is_admin:
                if text_lower in ["🔙 назад в админку", "🔙 назад"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                    continue
                
                if text_lower == "🔙 пользовательское меню":
                    send_message(vk, user_id, "Меню:", get_main_keyboard())
                    continue
                
                if text_lower == "📢 модерация":
                    posts = get_moderation_posts()
                    if not posts:
                        send_message(vk, user_id, "✅ Пусто.", get_admin_main_keyboard())
                    else:
                        for p in posts[:5]:
                            msg = f"🚨 #{p['post_id']} ({p['reason']})\n\n{p['text'][:300]}"
                            send_message(vk, user_id, msg, get_moderation_keyboard(p['post_id']))
                    continue
                
                if text_lower == "👥 группы-доноры":
                    send_message(vk, user_id, "Группы-доноры:", get_donor_groups_keyboard())
                    continue
                
                if text_lower == "🚫 запрет-слова":
                    send_message(vk, user_id, "Слова:", get_forbidden_words_keyboard())
                    continue
                
                if text_lower == "📊 статистика":
                    s = get_stats()
                    msg = f"📊 Статистика:\n• Постов: {s['total_user_posts']}\n• Взято: {s['total_grabbed']}\n• Модерация: {s['pending_moderation']}\n• Доноров: {s['donor_count']}"
                    send_message(vk, user_id, msg, get_admin_main_keyboard())
                    continue
                
                if text_lower == "📋 список групп":
                    donors = get_donor_groups()
                    if donors:
                        lines = []
                        for g in donors:
                            try:
                                name = get_group_name(vk_user, g)
                                lines.append(f"• {g} — {name}")
                            except:
                                lines.append(f"• {g}")
                        send_message(vk, user_id, "\n".join(lines), get_donor_groups_keyboard())
                    else:
                        send_message(vk, user_id, "📭 Пусто.", get_donor_groups_keyboard())
                    continue
                
                if text_lower == "➕ добавить группу":
                    admin_state[user_id] = {"mode": "add_donor"}
                    send_message(vk, user_id, "Введите ID или ссылку:", get_back_admin_keyboard())
                    continue
                
                if text_lower == "➖ удалить группу":
                    donors = get_donor_groups()
                    if donors:
                        send_message(vk, user_id, "Выберите:", get_remove_donor_keyboard(donors, vk_user))
                    else:
                        send_message(vk, user_id, "📭 Пусто.", get_donor_groups_keyboard())
                    continue
                
                if text_lower.startswith("➖ "):
                    donors = get_donor_groups()
                    for g in donors:
                        try:
                            name = get_group_name(vk_user, g)
                        except:
                            name = str(g)
                        if text_lower == f"➖ {name}".lower()[:40]:
                            remove_donor_group(g)
                            send_message(vk, user_id, f"✅ [{name}] удалена!", get_donor_groups_keyboard())
                            break
                    continue
                
                if text_lower == "📋 список слов":
                    words = get_forbidden_words()
                    if words:
                        send_message(vk, user_id, "📋 " + ", ".join(words), get_forbidden_words_keyboard())
                    else:
                        send_message(vk, user_id, "📭 Пусто.", get_forbidden_words_keyboard())
                    continue
                
                if text_lower == "➕ добавить слово":
                    admin_state[user_id] = {"mode": "add_word"}
                    send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())
                    continue
                
                if text_lower == "➖ удалить слово":
                    admin_state[user_id] = {"mode": "del_word"}
                    send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())
                    continue
                
                if text_lower.startswith("✅ опубл "):
                    pid = int(text.split()[-1])
                    try:
                        posts = vk_user.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)
                        for p in posts.get("items", []):
                            if p["id"] == pid:
                                ptext = p.get("text", "")
                                uid = p.get("from_id", 0)
                                anon = contains_anonymous(ptext)
                                final = f"{ptext}\n\nАвтор: Аноним" if anon else f"{ptext}\n\nАвтор: [id{uid}|{get_user_name(vk_user, uid)[0]} {get_user_name(vk_user, uid)[1]}]"
                                r = vk_user.wall.post(owner_id=-GROUP_ID, message=final, attachments=build_attachments(p), from_group=1)
                                vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                                add_published_post(r["post_id"], uid, ptext)
                                remove_from_moderation(pid)
                                send_message(vk, user_id, f"✅ Опубликован!", get_admin_main_keyboard())
                                break
                    except Exception as e:
                        send_message(vk, user_id, f"❌ {e}", get_admin_main_keyboard())
                    continue
                
                if text_lower.startswith("❌ удалить "):
                    pid = int(text.split()[-1])
                    try:
                        vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                    except:
                        pass
                    remove_from_moderation(pid)
                    send_message(vk, user_id, f"❌ Удалён.", get_admin_main_keyboard())
                    continue
                
                if text_lower.startswith("⏭ пропустить "):
                    pid = int(text.split()[-1])
                    remove_from_moderation(pid)
                    send_message(vk, user_id, f"⏭ Пропущен.", get_admin_main_keyboard())
                    continue
            
            else:
                kb = get_admin_main_keyboard() if is_admin else get_main_keyboard()
                send_message(vk, user_id, "Нажмите кнопку.", kb)
