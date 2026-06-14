import re
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from config import *
from db import *
from utils import *
from keyboards import *

# Состояния
waiting_support = set()
selected_post_for_delete = {}
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
            
            # ─── ОБРАБОТКА АДМИНСКИХ СОСТОЯНИЙ ───
            if is_admin and user_id in admin_state:
                state = admin_state[user_id]
                mode = state.get("mode")
                
                # Добавление группы
                if mode == "add_donor":
                    if text.lower() in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    else:
                        group_id = resolve_group_id(vk_user, text.strip())
                        if group_id:
                            add_donor_group(group_id)
                            name = get_group_name(vk_user, group_id)
                            send_message(vk, user_id, f"✅ Группа [{name}] добавлена!", get_donor_groups_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не удалось найти группу. Проверьте ссылку или ID.", get_back_admin_keyboard())
                        admin_state.pop(user_id, None)
                    continue
                
                # Удаление группы
                if mode == "del_donor":
                    if text.lower() in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    else:
                        group_id = resolve_group_id(vk_user, text.strip())
                        if group_id:
                            donors = get_donor_groups()
                            if group_id in donors:
                                remove_donor_group(group_id)
                                send_message(vk, user_id, f"✅ Группа {group_id} удалена!", get_donor_groups_keyboard())
                            else:
                                send_message(vk, user_id, "❌ Группа не найдена в списке доноров.", get_donor_groups_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не удалось найти группу.", get_back_admin_keyboard())
                        admin_state.pop(user_id, None)
                    continue
                
                # Добавление слова
                if mode == "add_word":
                    if text.lower() in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    else:
                        word = text.strip().lower()
                        add_forbidden_word(word)
                        send_message(vk, user_id, f"✅ Слово '{word}' добавлено!", get_forbidden_words_keyboard())
                        admin_state.pop(user_id, None)
                    continue
                
                # Удаление слова
                if mode == "del_word":
                    if text.lower() in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    else:
                        word = text.strip().lower()
                        words = get_forbidden_words()
                        if word in words:
                            remove_forbidden_word(word)
                            send_message(vk, user_id, f"✅ Слово '{word}' удалено!", get_forbidden_words_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Слово не найдено.", get_forbidden_words_keyboard())
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
                            dialog_link = f"https://vk.com/gim{GROUP_ID}?sel={user_id}"
                            vk.messages.send(
                                user_id=ADMIN_ID,
                                message=f"📨 ОБРАЩЕНИЕ В ПОДДЕРЖКУ\n\n{dialog_link}",
                                random_id=0,
                                forward_messages=msg_id,
                                group_id=GROUP_ID
                            )
                            send_message(vk, user_id, "✅ Сообщение отправлено!", get_main_keyboard())
                        except:
                            send_message(vk, user_id, "❌ Ошибка.", get_main_keyboard())
                continue
            
            # ─── ОСНОВНЫЕ КОМАНДЫ ───
            text_lower = text.lower()
            
            if text_lower in ["начать", "меню", "start"]:
                kb = get_admin_main_keyboard() if is_admin else get_main_keyboard()
                send_message(vk, user_id, "👋 Добро пожаловать!", kb)
                continue
            
            # ─── ПОЛЬЗОВАТЕЛЬСКИЕ ───
            if text_lower == "🗑 удалить мой пост":
                posts = get_user_posts(user_id)
                if not posts:
                    send_message(vk, user_id, "📭 У вас нет опубликованных постов.", get_main_keyboard())
                else:
                    send_message(vk, user_id, f"📋 У вас {len(posts)} пост(ов).\nВыберите:", get_posts_keyboard(posts))
                continue
            
            if text_lower == "🆘 написать в поддержку":
                waiting_support.add(user_id)
                send_message(vk, user_id, "📝 Напишите ваше сообщение.\nНажмите «Отмена» для возврата.", get_cancel_keyboard())
                continue
            
            if text_lower == "🔙 отмена":
                kb = get_admin_main_keyboard() if is_admin else get_main_keyboard()
                send_message(vk, user_id, "Меню:", kb)
                continue
            
            if text_lower == "❌ нет":
                selected_post_for_delete.pop(user_id, None)
                send_message(vk, user_id, "Удаление отменено.", get_main_keyboard())
                continue
            
            if text_lower == "✅ да, удалить":
                if user_id in selected_post_for_delete:
                    post_id = selected_post_for_delete[user_id]
                    if get_post_author(post_id) == user_id:
                        try:
                            vk_user.wall.delete(owner_id=-GROUP_ID, post_id=post_id)
                            delete_user_post(user_id, post_id)
                            send_message(vk, user_id, f"✅ Пост #{post_id} удален!", get_main_keyboard())
                            selected_post_for_delete.pop(user_id, None)
                        except Exception as e:
                            send_message(vk, user_id, f"❌ Ошибка: {e}", get_main_keyboard())
                    else:
                        send_message(vk, user_id, "❌ Это не ваш пост!", get_main_keyboard())
                else:
                    send_message(vk, user_id, "Сначала выберите пост.", get_main_keyboard())
                continue
            
            if text_lower.startswith("🗑 "):
                try:
                    match = re.search(r"🗑 (\d+)\.", text)
                    if match:
                        idx = int(match.group(1)) - 1
                        posts = get_user_posts(user_id)
                        if 0 <= idx < len(posts):
                            post_id = posts[idx]['post_id']
                            selected_post_for_delete[user_id] = post_id
                            send_message(vk, user_id, f"⚠️ Удалить пост #{post_id}?", get_confirm_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Пост не найден", get_main_keyboard())
                except:
                    pass
                continue
            
            # ─── АДМИНСКИЕ ───
            if is_admin:
                if text_lower in ["🔙 назад в админку", "🔙 назад"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                    continue
                
                if text_lower == "🔙 пользовательское меню":
                    send_message(vk, user_id, "Пользовательское меню:", get_main_keyboard())
                    continue
                
                if text_lower == "📢 модерация":
                    posts = get_moderation_posts()
                    if not posts:
                        send_message(vk, user_id, "✅ Нет постов на модерации.", get_admin_main_keyboard())
                    else:
                        for p in posts[:5]:
                            msg = f"🚨 Пост #{p['post_id']} ({p['reason']})\n\n{p['text'][:300]}"
                            send_message(vk, user_id, msg, get_moderation_keyboard(p['post_id']))
                    continue
                
                if text_lower == "👥 группы-доноры":
                    send_message(vk, user_id, "Управление группами-донорами:", get_donor_groups_keyboard())
                    continue
                
                if text_lower == "🚫 запрет-слова":
                    send_message(vk, user_id, "Управление запрещёнными словами:", get_forbidden_words_keyboard())
                    continue
                
                if text_lower == "📊 статистика":
                    stats = get_stats()
                    msg = (
                        f"📊 Статистика:\n"
                        f"• Постов от пользователей: {stats['total_user_posts']}\n"
                        f"• Постов от граббера: {stats['total_grab_posts']}\n"
                        f"• В очереди граббера: {stats['pending_grab']}\n"
                        f"• На модерации: {stats['pending_moderation']}\n"
                        f"• Групп-доноров: {stats['donor_count']}"
                    )
                    send_message(vk, user_id, msg, get_admin_main_keyboard())
                    continue
                
                if text_lower == "📋 список групп":
                    donors = get_donor_groups()
                    if not donors:
                        send_message(vk, user_id, "📭 Список пуст.", get_donor_groups_keyboard())
                    else:
                        lines = []
                        for g in donors:
                            try:
                                name = get_group_name(vk_user, g)
                                lines.append(f"• {g} — {name}")
                            except:
                                lines.append(f"• {g}")
                        send_message(vk, user_id, "📋 Группы-доноры:\n" + "\n".join(lines), get_donor_groups_keyboard())
                    continue
                
                if text_lower == "➕ добавить":
                    admin_state[user_id] = {"mode": "add_donor"}
                    send_message(vk, user_id, "Введите ID группы или ссылку:", get_back_admin_keyboard())
                    continue
                
                if text_lower == "➖ удалить":
                    admin_state[user_id] = {"mode": "del_donor"}
                    send_message(vk, user_id, "Введите ID группы или ссылку для удаления:", get_back_admin_keyboard())
                    continue
                
                if text_lower == "📋 список слов":
                    words = get_forbidden_words()
                    if not words:
                        send_message(vk, user_id, "📭 Список пуст.", get_forbidden_words_keyboard())
                    else:
                        send_message(vk, user_id, "📋 Запрещённые слова:\n" + ", ".join(words), get_forbidden_words_keyboard())
                    continue
                
                if text_lower == "➕ добавить" and user_id not in admin_state:
                    admin_state[user_id] = {"mode": "add_word"}
                    send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())
                    continue
                
                if text_lower == "➖ удалить" and user_id not in admin_state:
                    admin_state[user_id] = {"mode": "del_word"}
                    send_message(vk, user_id, "Введите слово для удаления:", get_back_admin_keyboard())
                    continue
                
                if text_lower.startswith("✅ опубл "):
                    try:
                        post_id = int(text.split()[-1])
                        posts = vk_user.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)
                        for p in posts.get("items", []):
                            if p["id"] == post_id:
                                uid = p.get("from_id", 0)
                                post_text = p.get("text", "")
                                anonymous = contains_anonymous(post_text)
                                if anonymous:
                                    final = f"{post_text}\n\nАвтор: Аноним"
                                else:
                                    first, last = get_user_name(vk_user, uid)
                                    final = f"{post_text}\n\nАвтор: [id{uid}|{first} {last}]"
                                attachments = build_attachments(p)
                                result = vk_user.wall.post(owner_id=-GROUP_ID, message=final, attachments=attachments, from_group=1)
                                vk_user.wall.delete(owner_id=-GROUP_ID, post_id=post_id)
                                add_user_post(uid, result["post_id"], post_text)
                                remove_from_moderation(post_id)
                                send_message(vk, user_id, f"✅ Пост #{post_id} опубликован!", get_admin_main_keyboard())
                                break
                    except Exception as e:
                        send_message(vk, user_id, f"❌ Ошибка: {e}", get_admin_main_keyboard())
                    continue
                
                if text_lower.startswith("❌ удалить "):
                    try:
                        post_id = int(text.split()[-1])
                        try:
                            vk_user.wall.delete(owner_id=-GROUP_ID, post_id=post_id)
                        except:
                            pass
                        remove_from_moderation(post_id)
                        send_message(vk, user_id, f"❌ Пост #{post_id} удалён.", get_admin_main_keyboard())
                    except Exception as e:
                        send_message(vk, user_id, f"❌ Ошибка: {e}", get_admin_main_keyboard())
                    continue
                
                if text_lower.startswith("⏭ пропустить "):
                    try:
                        post_id = int(text.split()[-1])
                        remove_from_moderation(post_id)
                        send_message(vk, user_id, f"⏭ Пост #{post_id} пропущен.", get_admin_main_keyboard())
                    except:
                        pass
                    continue
            
            # ─── НЕИЗВЕСТНАЯ КОМАНДА ───
            else:
                kb = get_admin_main_keyboard() if is_admin else get_main_keyboard()
                send_message(vk, user_id, "Нажмите на кнопку в меню", kb)
