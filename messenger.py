import re
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from datetime import datetime
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
        if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
            continue

        user_id = event.user_id
        text = event.text.strip() if event.text else ""
        is_admin = (user_id == ADMIN_ID)

        # ─── СОСТОЯНИЯ ───
        if is_admin and user_id in admin_state:
            state = admin_state[user_id]
            mode = state.get("mode")
            if text.lower() in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                admin_state.pop(user_id, None)
                send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                continue

            if mode == "add_donor":
                gid = resolve_group_id(vk_user, text.strip())
                if gid:
                    add_donor_group(gid)
                    send_message(vk, user_id, f"✅ [{get_group_name(vk_user, gid)}] добавлена!", get_donor_groups_keyboard())
                else:
                    send_message(vk, user_id, "❌ Не найдена.", get_back_admin_keyboard())
            elif mode == "add_word":
                add_forbidden_word(text.strip().lower())
                send_message(vk, user_id, "✅ Добавлено!", get_forbidden_words_keyboard())
            elif mode == "del_word":
                w = text.strip().lower()
                if w in get_forbidden_words():
                    remove_forbidden_word(w)
                    send_message(vk, user_id, "✅ Удалено!", get_forbidden_words_keyboard())
                else:
                    send_message(vk, user_id, "❌ Не найдено.", get_forbidden_words_keyboard())
            admin_state.pop(user_id, None)
            continue

        # ─── ПОДДЕРЖКА ───
        if user_id in waiting_support:
            waiting_support.discard(user_id)
            if text.lower() not in ["🔙 отмена", "/cancel"]:
                if ADMIN_ID:
                    try:
                        vk.messages.send(user_id=ADMIN_ID, message=f"📨 ОБРАЩЕНИЕ\nhttps://vk.com/gim{GROUP_ID}?sel={user_id}",
                                         random_id=0, forward_messages=event.message_id, group_id=GROUP_ID)
                        send_message(vk, user_id, "✅ Отправлено!", get_main_keyboard())
                    except:
                        send_message(vk, user_id, "❌ Ошибка.", get_main_keyboard())
            else:
                send_message(vk, user_id, "Отменено.", get_admin_main_keyboard() if is_admin else get_main_keyboard())
            continue

        # ─── ОСНОВНЫЕ ───
        t = text.lower()

        if t in ["начать", "меню", "start"]:
            send_message(vk, user_id, "👋 Привет!", get_admin_main_keyboard() if is_admin else get_main_keyboard())
        elif t == "🗑 удалить мой пост":
            posts = get_user_posts(user_id)
            if posts:
                send_message(vk, user_id, f"📋 Постов: {len(posts)}", get_posts_keyboard(posts))
            else:
                send_message(vk, user_id, "📭 Нет постов.", get_main_keyboard())
        elif t == "🆘 написать в поддержку":
            waiting_support.add(user_id)
            send_message(vk, user_id, "📝 Пишите:", get_cancel_keyboard())
        elif t == "🔙 отмена":
            send_message(vk, user_id, "Меню:", get_admin_main_keyboard() if is_admin else get_main_keyboard())
        elif t == "❌ нет":
            selected_post.pop(user_id, None)
            send_message(vk, user_id, "Отменено.", get_main_keyboard())
        elif t == "✅ да, удалить" and user_id in selected_post:
            pid = selected_post[user_id]
            if get_post_author(pid) == user_id:
                try:
                    vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                    delete_user_post(user_id, pid)
                    send_message(vk, user_id, f"✅ #{pid} удалён!", get_main_keyboard())
                except:
                    send_message(vk, user_id, "❌ Ошибка.", get_main_keyboard())
            else:
                send_message(vk, user_id, "❌ Не ваш пост!", get_main_keyboard())
            selected_post.pop(user_id, None)
        elif t.startswith("🗑 "):
            m = re.search(r"🗑 (\d+)\.", t)
            if m:
                idx = int(m.group(1)) - 1
                posts = get_user_posts(user_id)
                if 0 <= idx < len(posts):
                    selected_post[user_id] = posts[idx]['post_id']
                    send_message(vk, user_id, f"⚠️ Удалить #{posts[idx]['post_id']}?", get_confirm_keyboard())

        # ─── АДМИН ───
        elif is_admin:
            if t in ["🔙 назад в админку", "🔙 назад"]:
                admin_state.pop(user_id, None)
                send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())

            elif t == "🔙 пользовательское меню":
                send_message(vk, user_id, "Меню:", get_main_keyboard())

            elif t == "📢 модерация":
                posts = get_moderation_posts()
                pending = get_pending_grabs()

                if posts or pending:
                    if posts:
                        send_message(vk, user_id, f"👤 Подозрительные от пользователей ({len(posts)}):", get_admin_main_keyboard())
                        for p in posts[:10]:
                            send_message(vk, user_id, f"🚨 #{p['post_id']} ({p['reason']})\n\n{p['text'][:300]}",
                                         get_moderation_keyboard(p['post_id']))
                    if pending:
                        send_message(vk, user_id, f"🎣 Подозрительные от граббера ({len(pending)}):", get_admin_main_keyboard())
                        for i, p in enumerate(pending[:10]):
                            msg = f"🚨 #{i+1} ({p['reason']})\nИз группы: {p['from_group']}\n\n{p['post']['text'][:300]}"
                            send_message(vk, user_id, msg, get_pending_grab_keyboard(i))
                else:
                    send_message(vk, user_id, "✅ Нет подозрительных постов.", get_admin_main_keyboard())

            elif t == "📅 очередь постов":
                scheduled = get_scheduled_posts()
                if scheduled:
                    msg = "📅 Запланированные:\n\n"
                    for p in scheduled[:10]:
                        t_str = datetime.fromtimestamp(p["time"]).strftime("%d.%m %H:%M")
                        msg += f"• {t_str} — {p['text'][:50]}...\n"
                    send_message(vk, user_id, msg, get_scheduled_keyboard())
                else:
                    send_message(vk, user_id, "📭 Пусто.", get_admin_main_keyboard())

            elif t == "👥 группы-доноры":
                send_message(vk, user_id, "Группы:", get_donor_groups_keyboard())

            elif t == "🚫 запрет-слова":
                send_message(vk, user_id, "Слова:", get_forbidden_words_keyboard())

            elif t == "📊 статистика":
                s = get_stats()
                msg = (f"📊 Статистика:\n"
                       f"• Опубликовано: {s['total_published']}\n"
                       f"• Запланировано: {s['scheduled_count']}\n"
                       f"• Взято граббером: {s['total_grabbed']}\n"
                       f"• На модерации: {s['pending_moderation']}\n"
                       f"• Доноров: {s['donor_count']}")
                send_message(vk, user_id, msg, get_admin_main_keyboard())

            elif t == "📋 список групп":
                donors = get_donor_groups()
                if donors:
                    lines = []
                    for g in donors:
                        try:
                            lines.append(f"• {g} — {get_group_name(vk_user, g)}")
                        except:
                            lines.append(f"• {g}")
                    send_message(vk, user_id, "\n".join(lines), get_donor_groups_keyboard())
                else:
                    send_message(vk, user_id, "📭 Пусто.", get_donor_groups_keyboard())

            elif t == "➕ добавить группу":
                admin_state[user_id] = {"mode": "add_donor"}
                send_message(vk, user_id, "Введите ID/ссылку:", get_back_admin_keyboard())

            elif t == "➖ удалить группу":
                donors = get_donor_groups()
                if donors:
                    send_message(vk, user_id, "Выберите:", get_remove_donor_keyboard(donors, vk_user))
                else:
                    send_message(vk, user_id, "📭 Пусто.", get_donor_groups_keyboard())

            elif t.startswith("➖ "):
                donors = get_donor_groups()
                for g in donors:
                    try:
                        name = get_group_name(vk_user, g)
                    except:
                        name = str(g)
                    if t == f"➖ {name}".lower()[:40]:
                        remove_donor_group(g)
                        send_message(vk, user_id, f"✅ [{name}] удалена!", get_donor_groups_keyboard())
                        break

            elif t == "📋 список слов":
                words = get_forbidden_words()
                if words:
                    send_message(vk, user_id, "📋 " + ", ".join(words), get_forbidden_words_keyboard())
                else:
                    send_message(vk, user_id, "📭 Пусто.", get_forbidden_words_keyboard())

            elif t == "➕ добавить слово":
                admin_state[user_id] = {"mode": "add_word"}
                send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())

            elif t == "➖ удалить слово":
                admin_state[user_id] = {"mode": "del_word"}
                send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())

            elif t.startswith("✅ опубл "):
                pid = int(t.split()[-1])
                try:
                    posts = vk_user.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)
                    for p in posts.get("items", []):
                        if p["id"] == pid:
                            pt = p.get("text", ""); puid = p.get("from_id", 0)
                            fn = (f"{pt}\n\nАвтор: Аноним" if contains_anonymous(pt)
                                  else f"{pt}\n\nАвтор: [id{puid}|{get_user_name(vk_user, puid)[0]} {get_user_name(vk_user, puid)[1]}]")
                            r = vk_user.wall.post(owner_id=-GROUP_ID, message=fn, attachments=build_attachments(p), from_group=1)
                            vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                            add_published_post(r["post_id"], puid, pt)
                            remove_from_moderation(pid)
                            send_message(vk, user_id, "✅ Опубликован!", get_admin_main_keyboard())
                            break
                except Exception as e:
                    send_message(vk, user_id, f"❌ {e}", get_admin_main_keyboard())

            elif t.startswith("✅ граббер "):
                try:
                    idx = int(t.split()[-1])
                    pending = get_pending_grabs()
                    if 0 <= idx < len(pending):
                        p = pending[idx]
                        pub_time = get_next_free_hour()
                        vk_user.wall.post(
                            owner_id=-GROUP_ID,
                            message=p["post"]["text"],
                            attachments=p["post"]["attachments"],
                            from_group=1,
                            publish_date=pub_time
                        )
                        add_scheduled_post(pub_time, p["post"]["text"][:200], p["from_group"])
                        remove_pending_grab(idx)
                        send_message(vk, user_id, f"✅ Запланирован на {datetime.fromtimestamp(pub_time).strftime('%H:%M')}!", get_admin_main_keyboard())
                except Exception as e:
                    send_message(vk, user_id, f"❌ {e}", get_admin_main_keyboard())

            elif t.startswith("❌ удалить "):
                pid = int(t.split()[-1])
                try:
                    vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                except:
                    pass
                remove_from_moderation(pid)
                send_message(vk, user_id, "❌ Удалён.", get_admin_main_keyboard())

            elif t.startswith("❌ граббер "):
                try:
                    idx = int(t.split()[-1])
                    remove_pending_grab(idx)
                    send_message(vk, user_id, "❌ Удалён.", get_admin_main_keyboard())
                except:
                    send_message(vk, user_id, "❌ Ошибка.", get_admin_main_keyboard())

        else:
            send_message(vk, user_id, "Нажмите кнопку.", get_admin_main_keyboard() if is_admin else get_main_keyboard())
