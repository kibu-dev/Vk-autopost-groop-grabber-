import re
import logging
import vk_api
import requests as req
from vk_api.longpoll import VkLongPoll, VkEventType
from datetime import datetime
from config import *
from utils import *
from keyboards import *
from ai_poster import generate_variants, parse_variants, load_prompt, ai_log, generate_text, translate_text
from holidays import (
    get_holidays_config, save_holidays_config, generate_holidays_list,
    get_holiday_publish_time, create_holiday_post, generate_holiday_text
)

waiting_support = set()
selected_post = {}
admin_state = {}

def run_messenger():
    vk_session = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131")
    vk = vk_session.get_api()
    vk_user_session = vk_api.VkApi(token=USER_TOKEN, api_version="5.131")
    vk_user = vk_user_session.get_api()
    longpoll = VkLongPoll(vk_session, group_id=GROUP_ID, mode=2, preload_messages=True)
    logging.info("🤖 ЛС бот запущен")

    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
            continue

        user_id = event.user_id
        text = event.text.strip() if event.text else ""
        is_admin = (user_id == ADMIN_ID)

        if is_admin and user_id in admin_state:
            state = admin_state[user_id]
            mode = state.get("mode")
            t = text.lower()

            if mode == "ai_post":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                attachments = []
                try:
                    msg = vk.messages.getById(message_ids=event.message_id, group_id=GROUP_ID)
                    if msg and msg.get("items"):
                        for att in msg["items"][0].get("attachments", []):
                            att_type = att.get("type"); att_obj = att.get(att_type, {})
                            oid = att_obj.get("owner_id"); iid = att_obj.get("id")
                            if oid and iid: attachments.append(f"{att_type}{oid}_{iid}")
                except: pass
                admin_state[user_id] = {"mode": "ai_choose", "text": text, "variants": [], "attachments": attachments}
                send_message(vk, user_id, "⏳ Генерирую пост...")
                result = generate_variants(text)
                if result:
                    variants = parse_variants(result)
                    if variants and len(variants[0]) > 20:
                        admin_state[user_id]["variants"] = variants
                        send_message(vk, user_id, f"🤖 Готовый пост:\n\n{variants[0]}", get_variants_keyboard())
                    else:
                        send_message(vk, user_id, "❌ Не удалось.", get_admin_main_keyboard())
                        admin_state.pop(user_id, None)
                else:
                    send_message(vk, user_id, "❌ Ошибка ИИ.", get_admin_main_keyboard())
                    admin_state.pop(user_id, None)
                continue

            if mode == "ai_choose":
                if t == "✅ опубликовать":
                    chosen = state["variants"][0] if state.get("variants") else state["text"]
                    att = ",".join(state.get("attachments", [])) or None
                    r = vk_user.wall.post(owner_id=-GROUP_ID, message=chosen, attachments=att, from_group=1)
                    add_published_post(r["post_id"], ADMIN_ID, chosen)
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "✅ Опубликовано!" + (" 📎" if att else ""), get_admin_main_keyboard())
                elif t == "✏️ свой текст": admin_state[user_id] = {"mode": "ai_custom"}; send_message(vk, user_id, "✏️ Напишите свой текст:", get_cancel_keyboard())
                elif t == "🔄 ещё вариант":
                    result = generate_variants(state["text"])
                    if result:
                        variants = parse_variants(result)
                        if variants and len(variants[0]) > 20:
                            state["variants"] = variants
                            send_message(vk, user_id, f"🤖 Новый вариант:\n\n{variants[0]}", get_variants_keyboard())
                        else: send_message(vk, user_id, "❌ Не удалось.", get_admin_main_keyboard())
                    else: send_message(vk, user_id, "❌ Ошибка ИИ.", get_admin_main_keyboard())
                elif t == "❌ отмена": admin_state.pop(user_id, None); send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                continue

            if mode == "ai_custom":
                if t in ["🔙 отмена", "❌ отмена"]: admin_state.pop(user_id, None); send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard()); continue
                att = ",".join(state.get("attachments", [])) or None
                r = vk_user.wall.post(owner_id=-GROUP_ID, message=text, attachments=att, from_group=1)
                add_published_post(r["post_id"], ADMIN_ID, text); admin_state.pop(user_id, None)
                send_message(vk, user_id, "✅ Опубликовано!", get_admin_main_keyboard()); continue

            if mode == "reddit_edit":
                if t in ["🔙 отмена", "❌ отмена"]: admin_state.pop(user_id, None); send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard()); continue
                draft_id = state.get("draft_id")
                from reddit_handler import load_drafts, save_drafts
                drafts = load_drafts()
                if draft_id in drafts: drafts[draft_id]["text"] = text; save_drafts(drafts); send_message(vk, user_id, "✅ Текст обновлён!", get_admin_main_keyboard())
                else: send_message(vk, user_id, "❌ Черновик не найден.", get_admin_main_keyboard())
                admin_state.pop(user_id, None); continue

            if mode == "horoscope_photo":
                if t in ["🔙 отмена", "❌ отмена"]: admin_state.pop(user_id, None); send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard()); continue
                photo_saved = False
                try:
                    msg = vk.messages.getById(message_ids=event.message_id, group_id=GROUP_ID)
                    if msg and msg.get("items"):
                        for att in msg["items"][0].get("attachments", []):
                            if att.get("type") == "photo":
                                att_obj = att.get("photo", {}); sizes = att_obj.get("sizes", [])
                                if sizes:
                                    biggest = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
                                    if biggest.get("url"):
                                        img_data = req.get(biggest["url"]).content
                                        up_server = vk_user.photos.getWallUploadServer(group_id=GROUP_ID)
                                        up = req.post(up_server['upload_url'], files={'photo': ('h.jpg', img_data, 'image/jpeg')}).json()
                                        if 'photo' in up and up['photo']:
                                            saved = vk_user.photos.saveWallPhoto(photo=up['photo'], server=up['server'], hash=up['hash'], group_id=GROUP_ID)
                                            if saved: set_horoscope_photo(f"photo{saved[0]['owner_id']}_{saved[0]['id']}"); photo_saved = True
                                        break
                except: pass
                send_message(vk, user_id, "✅ Фото сохранено!" if photo_saved else "❌ Не удалось.", get_horoscope_keyboard())
                admin_state.pop(user_id, None); continue

            if mode == "holiday_post":
                if t in ["🔙 отмена", "❌ отмена"]: admin_state.pop(user_id, None); send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard()); continue
                photo_saved = False
                try:
                    msg = vk.messages.getById(message_ids=event.message_id, group_id=GROUP_ID)
                    if msg and msg.get("items"):
                        for att in msg["items"][0].get("attachments", []):
                            if att.get("type") == "photo":
                                att_obj = att.get("photo", {}); sizes = att_obj.get("sizes", [])
                                if sizes:
                                    biggest = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
                                    if biggest.get("url"):
                                        img_data = req.get(biggest["url"]).content
                                        up_server = vk_user.photos.getWallUploadServer(group_id=GROUP_ID)
                                        up = req.post(up_server['upload_url'], files={'photo': ('hol.jpg', img_data, 'image/jpeg')}).json()
                                        if 'photo' in up and up['photo']:
                                            saved = vk_user.photos.saveWallPhoto(photo=up['photo'], server=up['server'], hash=up['hash'], group_id=GROUP_ID)
                                            if saved:
                                                config = get_holidays_config(); config["photo_id"] = f"photo{saved[0]['owner_id']}_{saved[0]['id']}"; save_holidays_config(config); photo_saved = True
                                        break
                except: pass
                if photo_saved:
                    config = get_holidays_config(); name = config.get("selected_name", "")
                    send_message(vk, user_id, f"✅ Фото сохранено!\n⏳ Генерирую для: {name}")
                    txt = generate_holiday_text(name)
                    if txt: config["generated_text"] = txt; save_holidays_config(config); send_message(vk, user_id, f"🤖 Готово:\n\n{txt[:1500]}", get_holiday_confirm_keyboard())
                    else: send_message(vk, user_id, "❌ Не удалось.", get_holidays_keyboard())
                else: send_message(vk, user_id, "❌ Не удалось загрузить фото.", get_holidays_keyboard())
                admin_state.pop(user_id, None); continue

            if mode == "holiday_custom":
                if t in ["🔙 отмена", "❌ отмена"]: admin_state.pop(user_id, None); send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard()); continue
                config = get_holidays_config(); config["generated_text"] = text; save_holidays_config(config); admin_state.pop(user_id, None)
                send_message(vk, user_id, f"📝 Ваш текст:\n\n{text[:500]}...", get_holiday_confirm_keyboard()); continue

            if t in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                admin_state.pop(user_id, None); send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard()); continue

            if mode == "add_donor":
                gid = resolve_group_id(vk_user, text.strip())
                if gid: add_donor_group(gid); send_message(vk, user_id, f"✅ [{get_group_name(vk_user, gid)}] добавлена!", get_donor_groups_keyboard())
                else: send_message(vk, user_id, "❌ Не найдена.", get_back_admin_keyboard())
            elif mode == "add_word": add_forbidden_word(text.strip().lower()); send_message(vk, user_id, "✅ Добавлено!", get_forbidden_words_keyboard())
            elif mode == "del_word":
                w = text.strip().lower()
                if w in get_forbidden_words(): remove_forbidden_word(w); send_message(vk, user_id, "✅ Удалено!", get_forbidden_words_keyboard())
                else: send_message(vk, user_id, "❌ Не найдено.", get_forbidden_words_keyboard())
            elif mode == "add_liker":
                gid = resolve_group_id(vk_user, text.strip())
                if gid: add_liker_group(gid); send_message(vk, user_id, f"✅ [{get_group_name(vk_user, gid)}] добавлена!", get_liker_keyboard())
                else: send_message(vk, user_id, "❌ Не найдена.", get_back_admin_keyboard())
            admin_state.pop(user_id, None)
            continue

        if user_id in waiting_support:
            waiting_support.discard(user_id)
            if text.lower() not in ["🔙 отмена", "/cancel"]:
                if ADMIN_ID:
                    try:
                        vk.messages.send(user_id=ADMIN_ID, message=f"📨 ОБРАЩЕНИЕ\nhttps://vk.com/gim{GROUP_ID}?sel={user_id}", random_id=0, forward_messages=event.message_id, group_id=GROUP_ID)
                        send_message(vk, user_id, "✅ Отправлено!", get_main_keyboard())
                    except: send_message(vk, user_id, "❌ Ошибка.", get_main_keyboard())
            else: send_message(vk, user_id, "Отменено.", get_admin_main_keyboard() if is_admin else get_main_keyboard())
            continue

        t = text.lower()
        t_orig = text.strip()

        if t in ["начать", "меню", "start"]:
            send_message(vk, user_id, "👋 Привет!", get_admin_main_keyboard() if is_admin else get_main_keyboard())
        elif t == "🗑 удалить мой пост":
            posts = get_user_posts(user_id)
            send_message(vk, user_id, f"📋 Постов: {len(posts)}" if posts else "📭 Нет постов.", get_posts_keyboard(posts) if posts else get_main_keyboard())
        elif t == "🆘 написать в поддержку": waiting_support.add(user_id); send_message(vk, user_id, "📝 Пишите:", get_cancel_keyboard())
        elif t == "🔙 отмена": send_message(vk, user_id, "Меню:", get_admin_main_keyboard() if is_admin else get_main_keyboard())
        elif t == "❌ нет": selected_post.pop(user_id, None); send_message(vk, user_id, "Отменено.", get_main_keyboard())
        elif t == "✅ да, удалить" and user_id in selected_post:
            pid = selected_post[user_id]
            if get_post_author(pid) == user_id:
                try: vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid); delete_user_post(user_id, pid); send_message(vk, user_id, f"✅ #{pid} удалён!", get_main_keyboard())
                except: send_message(vk, user_id, "❌ Ошибка.", get_main_keyboard())
            else: send_message(vk, user_id, "❌ Не ваш пост!", get_main_keyboard())
            selected_post.pop(user_id, None)
        elif t.startswith("🗑 "):
            m = re.search(r"🗑 (\d+)\.", t)
            if m:
                idx = int(m.group(1)) - 1; posts = get_user_posts(user_id)
                if 0 <= idx < len(posts): selected_post[user_id] = posts[idx]['post_id']; send_message(vk, user_id, f"⚠️ Удалить #{posts[idx]['post_id']}?", get_confirm_keyboard())

        elif is_admin:
            if t in ["🔙 назад в админку", "🔙 назад"]: admin_state.pop(user_id, None); send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
            elif t == "🔙 пользовательское меню": send_message(vk, user_id, "Меню:", get_main_keyboard())
            elif t == "📢 модерация":
                posts = get_moderation_posts(); pending = get_pending_grabs()
                if posts:
                    send_message(vk, user_id, f"👤 Подозрительные ({len(posts)}):", get_admin_main_keyboard())
                    for p in posts[:10]: send_message(vk, user_id, f"🚨 #{p['post_id']} ({p['reason']})\n\n{p['text'][:300]}", get_moderation_keyboard(p['post_id']))
                if pending:
                    send_message(vk, user_id, f"🎣 Граббер ({len(pending)}):", get_admin_main_keyboard())
                    for i, p in enumerate(pending[:10]): send_message(vk, user_id, f"🚨 #{i+1} ({p['reason']})\nИз: {p['from_group']}\n\n{p['post']['text'][:300]}", get_pending_grab_keyboard(i))
                if not posts and not pending: send_message(vk, user_id, "✅ Пусто.", get_admin_main_keyboard())
            elif t == "📅 очередь постов":
                sched = get_scheduled_posts()
                if sched:
                    msg = "📅 Запланированные:\n\n"
                    for p in sched[:10]: msg += f"• {datetime.fromtimestamp(p['time']).strftime('%d.%m %H:%M')} — {p['text'][:50]}...\n"
                    send_message(vk, user_id, msg, get_scheduled_keyboard())
                else: send_message(vk, user_id, "📭 Пусто.", get_admin_main_keyboard())
            elif t == "👥 группы-доноры": send_message(vk, user_id, "Группы:", get_donor_groups_keyboard())
            elif t == "🚫 запрет-слова": send_message(vk, user_id, "Слова:", get_forbidden_words_keyboard())

            elif t == "📱 reddit":
                from reddit_handler import load_drafts
                drafts = load_drafts(); pending = [v for v in drafts.values() if v.get("status") == "pending"]
                send_message(vk, user_id, f"📱 Reddit постов: {len(pending)}" if pending else "📱 Нет новых постов.", get_reddit_keyboard())

            elif t == "📋 просмотр постов":
                from reddit_handler import load_drafts
                drafts = load_drafts(); pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                if not pending: send_message(vk, user_id, "📱 Нет постов.", get_reddit_keyboard()); continue
                ids = list(pending.keys()); d = pending[ids[0]]
                msg = f"📱 Пост 1/{len(ids)} | {d.get('subreddit', '')}\n\n"
                if d.get('title'): msg += f"📌 {d['title']}\n\n"
                if d.get('text'): msg += f"{d['text'][:500]}\n\n"
                if d.get('images'): msg += f"🖼 Фото: {len(d['images'])} шт.\n"
                if d.get('url'): msg += f"🔗 {d['url']}"
                admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": 0}
                send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip())))

            elif t == "🗑 очистить всё":
                from reddit_handler import load_drafts, save_drafts
                drafts = load_drafts(); drafts = {k: v for k, v in drafts.items() if v.get("status") != "pending"}
                save_drafts(drafts); send_message(vk, user_id, "🗑 Все посты Reddit удалены.", get_admin_main_keyboard())

            # === REDDIT NAVIGATION ===
            elif is_admin and user_id in admin_state and admin_state[user_id].get("mode") == "reddit_view":
                state = admin_state[user_id]
                from reddit_handler import load_drafts, save_drafts
                drafts = load_drafts(); pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                ids = state.get("ids", []); idx = state.get("index", 0)

                if not pending: admin_state.pop(user_id, None); send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard()); continue

                if t == "⬅️ предыдущий": idx = (idx - 1) % len(ids)
                elif t == "➡️ следующий": idx = (idx + 1) % len(ids)
                elif t == "✅ в очередь":
                    draft_id = ids[idx]; d = pending[draft_id]
                    attachments = []
                    for img_url in d.get('images', [])[:10]:
                        try:
                            resp = req.get(img_url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
                            if resp.status_code != 200 or len(resp.content) < 1000: continue
                            up_server = vk_user.photos.getWallUploadServer(group_id=GROUP_ID)
                            up = req.post(up_server['upload_url'], files={'photo': ('r.jpg', resp.content, 'image/jpeg')}).json()
                            if 'photo' in up and up['photo']:
                                saved = vk_user.photos.saveWallPhoto(photo=up['photo'], server=up['server'], hash=up['hash'], group_id=GROUP_ID)
                                if saved: attachments.append(f"photo{saved[0]['owner_id']}_{saved[0]['id']}")
                        except: pass
                    post_text = d.get('text', '')
                    if d.get('title') and not post_text: post_text = d['title']
                    elif d.get('title'): post_text = f"{d['title']}\n\n{post_text}"
                    pub_time = get_next_free_hour()
                    vk_user.wall.post(owner_id=-GROUP_ID, message=post_text[:4000], attachments=",".join(attachments) if attachments else None, from_group=1, publish_date=pub_time)
                    add_scheduled_post(pub_time, post_text[:200], 0)
                    del drafts[draft_id]; save_drafts(drafts)
                    send_message(vk, user_id, f"✅ В очереди на {datetime.fromtimestamp(pub_time).strftime('%H:%M')}!", get_admin_main_keyboard())
                    admin_state.pop(user_id, None); continue

                elif "ии перевод" in t:
                    draft_id = ids[idx]; d = pending[draft_id]
                    original = d.get("original_text", d.get("text", ""))
                    if original:
                        send_message(vk, user_id, "⏳ Перевожу...")
                        translated = translate_text(original)
                        if translated:
                            drafts[draft_id]["text"] = translated; drafts[draft_id]["translated"] = True; save_drafts(drafts)
                            send_message(vk, user_id, f"✅ Переведено!\n\n{translated[:500]}", get_admin_main_keyboard())
                        else: send_message(vk, user_id, "❌ Ошибка перевода.", get_admin_main_keyboard())
                    admin_state.pop(user_id, None); continue

                elif "ии рерайт" in t:
                    draft_id = ids[idx]; d = pending[draft_id]
                    original = d.get("text", "")
                    if original:
                        send_message(vk, user_id, "⏳ Перефразирую...")
                        rewritten = generate_text(f"Перефразируй этот текст своими словами, сохрани смысл:\n\n{original[:2000]}")
                        if rewritten:
                            drafts[draft_id]["text"] = rewritten; save_drafts(drafts)
                            send_message(vk, user_id, f"✅ Готово!\n\n{rewritten[:500]}", get_admin_main_keyboard())
                        else: send_message(vk, user_id, "❌ Ошибка.", get_admin_main_keyboard())
                    admin_state.pop(user_id, None); continue

                elif "редактировать" in t:
                    admin_state[user_id] = {"mode": "reddit_edit", "draft_id": ids[idx]}
                    send_message(vk, user_id, "✏️ Напишите новый текст:", get_cancel_keyboard()); continue

                elif "удалить" in t:
                    del drafts[ids[idx]]; save_drafts(drafts)
                    send_message(vk, user_id, "🗑 Удалён.", get_admin_main_keyboard())
                    admin_state.pop(user_id, None); continue

                elif t == "🔙 назад": admin_state.pop(user_id, None); send_message(vk, user_id, "📱 Reddit", get_reddit_keyboard()); continue

                # Refresh
                pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}; ids = list(pending.keys())
                if not ids: admin_state.pop(user_id, None); send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard()); continue
                idx = min(idx, len(ids) - 1); d = pending[ids[idx]]
                msg = f"📱 Пост {idx+1}/{len(ids)} | {d.get('subreddit', '')}\n\n"
                if d.get('title'): msg += f"📌 {d['title']}\n\n"
                if d.get('text'): msg += f"{d['text'][:500]}\n\n"
                if d.get('images'): msg += f"🖼 Фото: {len(d['images'])} шт.\n"
                if d.get('url'): msg += f"🔗 {d['url']}"
                admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
                send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip())))

            elif t == "📊 статистика":
                s = get_stats()
                from reddit_handler import load_drafts
                drafts = load_drafts(); reddit_pending = len([v for v in drafts.values() if v.get("status") == "pending"])
                msg = f"📊 Статистика:\n• Опубликовано: {s['total_published']}\n• Запланировано: {s['scheduled_count']}\n• Взято граббером: {s['total_grabbed']}\n• На модерации: {s['pending_moderation']}\n• Reddit: {reddit_pending}\n• Доноров: {s['donor_count']}"
                send_message(vk, user_id, msg, get_admin_main_keyboard())

            elif t == "📋 список групп":
                donors = get_donor_groups()
                if donors: send_message(vk, user_id, "\n".join([f"• {g} — {get_group_name(vk_user, g)}" for g in donors]), get_donor_groups_keyboard())
                else: send_message(vk, user_id, "📭 Пусто.", get_donor_groups_keyboard())
            elif t == "➕ добавить группу": admin_state[user_id] = {"mode": "add_donor"}; send_message(vk, user_id, "Введите ID/ссылку:", get_back_admin_keyboard())
            elif t == "➖ удалить группу":
                donors = get_donor_groups()
                send_message(vk, user_id, "Выберите:" if donors else "📭 Пусто.", get_remove_donor_keyboard(donors, vk_user) if donors else get_donor_groups_keyboard())
            elif t.startswith("➖ "):
                donors = get_donor_groups()
                for g in donors:
                    try: name = get_group_name(vk_user, g)
                    except: name = str(g)
                    if t == f"➖ {name}".lower()[:40]: remove_donor_group(g); send_message(vk, user_id, f"✅ [{name}] удалена!", get_donor_groups_keyboard()); break

            elif t == "📋 список слов":
                words = get_forbidden_words()
                send_message(vk, user_id, "📋 " + ", ".join(words) if words else "📭 Пусто.", get_forbidden_words_keyboard())
            elif t == "➕ добавить слово": admin_state[user_id] = {"mode": "add_word"}; send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())
            elif t == "➖ удалить слово": admin_state[user_id] = {"mode": "del_word"}; send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())

            elif t.startswith("✅ опубл "):
                pid = int(t.split()[-1])
                try:
                    posts = vk_user.wall.get(owner_id=-GROUP_ID, filter="suggests", count=100)
                    for p in posts.get("items", []):
                        if p["id"] == pid:
                            pt = p.get("text", ""); puid = p.get("from_id", 0)
                            fn = f"{pt}\n\nАвтор: Аноним" if contains_anonymous(pt) else f"{pt}\n\nАвтор: [id{puid}|{get_user_name(vk_user, puid)[0]} {get_user_name(vk_user, puid)[1]}]"
                            r = vk_user.wall.post(owner_id=-GROUP_ID, message=fn, attachments=build_attachments(p), from_group=1)
                            vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid); add_published_post(r["post_id"], puid, pt); remove_from_moderation(pid)
                            send_message(vk, user_id, "✅ Опубликован!", get_admin_main_keyboard()); break
                except Exception as e: send_message(vk, user_id, f"❌ {e}", get_admin_main_keyboard())

            elif t.startswith("✅ граббер "):
                try:
                    idx = int(t.split()[-1]); pending = get_pending_grabs()
                    if 0 <= idx < len(pending):
                        p = pending[idx]; pub_time = get_next_free_hour()
                        vk_user.wall.post(owner_id=-GROUP_ID, message=p["post"]["text"], attachments=p["post"]["attachments"], from_group=1, publish_date=pub_time)
                        add_scheduled_post(pub_time, p["post"]["text"][:200], p["from_group"]); remove_pending_grab(idx)
                        send_message(vk, user_id, f"✅ Запланирован на {datetime.fromtimestamp(pub_time).strftime('%H:%M')}!", get_admin_main_keyboard())
                except Exception as e: send_message(vk, user_id, f"❌ {e}", get_admin_main_keyboard())

            elif t.startswith("❌ удалить "):
                pid = int(t.split()[-1])
                try: vk_user.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                except: pass
                remove_from_moderation(pid); send_message(vk, user_id, "❌ Удалён.", get_admin_main_keyboard())

            elif t.startswith("❌ граббер "):
                try: idx = int(t.split()[-1]); remove_pending_grab(idx); send_message(vk, user_id, "❌ Удалён.", get_admin_main_keyboard())
                except: send_message(vk, user_id, "❌ Ошибка.", get_admin_main_keyboard())

            elif t == "⚙️ автоматизация": send_message(vk, user_id, "⚙️ Автоматизация:", get_automation_keyboard())
            elif t == "❤️ автолайкер": send_message(vk, user_id, f"❤️ Автолайкер: {'Включен ✅' if is_liker_enabled() else 'Выключен ❌'}", get_liker_keyboard())
            elif t == "▶️ включить лайкер": set_liker_enabled(True); send_message(vk, user_id, "❤️ Включен!", get_liker_keyboard())
            elif t == "⏸️ выключить лайкер": set_liker_enabled(False); send_message(vk, user_id, "❤️ Выключен.", get_liker_keyboard())
            elif t == "📋 лайк группы":
                groups = get_liker_groups()
                send_message(vk, user_id, "\n".join([f"• {g} — {get_group_name(vk_user, g)}" for g in groups]) if groups else "📭 Пусто.", get_liker_keyboard())
            elif t == "➕ лайк группу": admin_state[user_id] = {"mode": "add_liker"}; send_message(vk, user_id, "Введите ID группы:", get_back_admin_keyboard())
            elif t == "➖ лайк группу":
                groups = get_liker_groups()
                send_message(vk, user_id, "Выберите:" if groups else "📭 Пусто.", get_remove_liker_keyboard(groups, vk_user) if groups else get_liker_keyboard())
            elif t.startswith("❤➖ "):
                groups = get_liker_groups()
                for g in groups:
                    try: name = get_group_name(vk_user, g)
                    except: name = str(g)
                    if t == f"❤➖ {name}".lower()[:40]: remove_liker_group(g); send_message(vk, user_id, f"✅ [{name}] удалена!", get_liker_keyboard()); break
            elif t == "📊 лайк стата":
                s = get_liker_stats(); send_message(vk, user_id, f"❤️ Статистика:\n• Сегодня: {s['today']}/20\n• Всего: {s['total']}", get_liker_keyboard())

            elif t == "🟢 вечный онлайн": send_message(vk, user_id, f"🟢 Онлайн: {'Включен ✅' if is_online_enabled() else 'Выключен ❌'}", get_online_keyboard())
            elif t == "▶️ включить онлайн": set_online_enabled(True); send_message(vk, user_id, "🟢 Включен!", get_online_keyboard())
            elif t == "⏸️ выключить онлайн": set_online_enabled(False); send_message(vk, user_id, "🟢 Выключен.", get_online_keyboard())

            elif t == "🤝 приём друзей":
                s = get_friend_stats(); send_message(vk, user_id, f"🤝 Друзья: {'Включен ✅' if is_friend_enabled() else 'Выключен ❌'}\nПринято: {s['accepted']}", get_friend_keyboard())
            elif t == "▶️ включить друзей": set_friend_enabled(True); send_message(vk, user_id, "🤝 Включено!", get_friend_keyboard())
            elif t == "⏸️ выключить друзей": set_friend_enabled(False); send_message(vk, user_id, "🤝 Выключено.", get_friend_keyboard())

            elif t == "👥 приём в группу":
                s = get_group_accept_stats(); send_message(vk, user_id, f"👥 Приём в группу: {'Включен ✅' if is_group_accept_enabled() else 'Выключен ❌'}\nПринято: {s['accepted']}", get_group_accept_keyboard())
            elif t == "▶️ включить группу": set_group_accept_enabled(True); send_message(vk, user_id, "👥 Включен!", get_group_accept_keyboard())
            elif t == "⏸️ выключить группу": set_group_accept_enabled(False); send_message(vk, user_id, "👥 Выключен.", get_group_accept_keyboard())

            elif t == "🔮 гороскоп":
                config = load_json("horoscope_config.json", {})
                next_m = get_horoscope_next_monday(); next_str = datetime.fromisoformat(next_m).strftime("%d.%m %H:%M") if next_m else "не запланирован"
                msg = f"🔮 Гороскоп: {'Включен ✅' if get_horoscope_enabled() else 'Выключен ❌'}\nСледующий: {next_str}"
                if config.get("text"): msg += f"\n\n📝 Текст:\n{config['text'][:2500]}"
                send_message(vk, user_id, msg, get_horoscope_keyboard())
            elif t == "удалить и пересоздать":
                config = load_json("horoscope_config.json", {}); config["next_monday"] = ""; save_json("horoscope_config.json", config)
                send_message(vk, user_id, "🔄 Создаю новый гороскоп...")
                from weekly_horoscope import create_horoscope
                if create_horoscope():
                    config = load_json("horoscope_config.json", {}); next_m = config.get("next_monday", "")
                    next_str = datetime.fromisoformat(next_m).strftime("%d.%m %H:%M") if next_m else "не запланирован"
                    msg = f"✅ Готово!\n🔮 Гороскоп: {'Включен ✅' if get_horoscope_enabled() else 'Выключен ❌'}\nСледующий: {next_str}"
                    if config.get("text"): msg += f"\n\n📝 Текст:\n{config['text'][:2500]}"
                    send_message(vk, user_id, msg, get_horoscope_keyboard())
                else: send_message(vk, user_id, "❌ Ошибка.", get_horoscope_keyboard())
            elif t == "▶️ включить гороскоп": set_horoscope_enabled(True); send_message(vk, user_id, "🔮 Включен!", get_horoscope_keyboard())
            elif t == "⏸️ выключить гороскоп": set_horoscope_enabled(False); send_message(vk, user_id, "🔮 Выключен.", get_horoscope_keyboard())
            elif t == "📋 промт гороскопа":
                try:
                    with open("horoscope_prompt.txt", "r", encoding="utf-8") as f: prompt_text = f.read()
                except: prompt_text = "Файл не найден"
                send_message(vk, user_id, f"📋 Промт гороскопа:\n\n{prompt_text}", get_horoscope_keyboard())
            elif t == "🖼️ сменить фото": admin_state[user_id] = {"mode": "horoscope_photo"}; send_message(vk, user_id, "📷 Пришлите новое фото:", get_cancel_keyboard())

            elif t == "🎉 праздники":
                config = get_holidays_config()
                if not config.get("holidays_list"):
                    send_message(vk, user_id, "⏳ Загружаю..."); holidays = generate_holidays_list()
                    if holidays: config["holidays_list"] = holidays; config["current_index"] = 0; save_holidays_config(config)
                    else: send_message(vk, user_id, "❌ Не удалось.", get_admin_main_keyboard()); continue
                holidays = config.get("holidays_list", []); idx = config.get("current_index", 0)
                if 0 <= idx < len(holidays):
                    h = holidays[idx]; config["selected_name"] = h["name"]; config["selected_date"] = h["date"]; save_holidays_config(config)
                    msg = f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}"
                else: msg = "📭 Список пуст."
                send_message(vk, user_id, msg, get_holidays_keyboard())
            elif t == "⬅️ предыдущий":
                config = get_holidays_config(); holidays = config.get("holidays_list", [])
                if holidays:
                    idx = (config.get("current_index", 0) - 1) % len(holidays); config["current_index"] = idx
                    h = holidays[idx]; config["selected_name"] = h["name"]; config["selected_date"] = h["date"]; save_holidays_config(config)
                    send_message(vk, user_id, f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
            elif t == "➡️ следующий":
                config = get_holidays_config(); holidays = config.get("holidays_list", [])
                if holidays:
                    idx = (config.get("current_index", 0) + 1) % len(holidays); config["current_index"] = idx
                    h = holidays[idx]; config["selected_name"] = h["name"]; config["selected_date"] = h["date"]; save_holidays_config(config)
                    send_message(vk, user_id, f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
            elif t == "✍️ создать поздравление":
                config = get_holidays_config(); name = config.get("selected_name", "")
                if not name: send_message(vk, user_id, "❌ Сначала выберите праздник.", get_holidays_keyboard()); continue
                admin_state[user_id] = {"mode": "holiday_post"}; send_message(vk, user_id, f"📷 Пришлите фото для: {name}", get_cancel_keyboard())
            elif t == "✅ опубликовать (праздник)":
                config = get_holidays_config(); text = config.get("generated_text", ""); date_str = config.get("selected_date", "")
                if not text: send_message(vk, user_id, "❌ Сначала сгенерируйте текст.", get_holidays_keyboard()); continue
                send_message(vk, user_id, f"⏳ Планирую на {date_str}...")
                if create_holiday_post(vk_user): send_message(vk, user_id, f"✅ Запланировано!\n📅 {date_str} 10:00", get_admin_main_keyboard())
                else: send_message(vk, user_id, "❌ Ошибка.", get_holidays_keyboard())
            elif t == "✏️ написать свой текст": admin_state[user_id] = {"mode": "holiday_custom"}; send_message(vk, user_id, "✏️ Напишите свой текст:", get_cancel_keyboard())
            elif t == "🔄 сгенерировать ещё":
                config = get_holidays_config(); name = config.get("selected_name", ""); send_message(vk, user_id, "⏳ Генерирую...")
                text = generate_holiday_text(name)
                if text: config["generated_text"] = text; save_holidays_config(config); send_message(vk, user_id, f"🤖 Новый вариант:\n\n{text[:1500]}", get_holiday_confirm_keyboard())
                else: send_message(vk, user_id, "❌ Ошибка.", get_holidays_keyboard())
            elif t == "🔄 обновить список":
                send_message(vk, user_id, "⏳ Обновляю..."); holidays = generate_holidays_list()
                if holidays:
                    config = get_holidays_config(); config["holidays_list"] = holidays; config["current_index"] = 0; save_holidays_config(config)
                    h = holidays[0]; config["selected_name"] = h["name"]; config["selected_date"] = h["date"]; save_holidays_config(config)
                    send_message(vk, user_id, f"✅ Обновлено! ({len(holidays)})\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
                else: send_message(vk, user_id, "❌ Не удалось.", get_holidays_keyboard())

            elif t == "🤖 ai-постер": send_message(vk, user_id, "🤖 AI-постер:", get_ai_keyboard())
            elif t == "📋 промт": send_message(vk, user_id, f"📋 Текущий промт:\n\n{load_prompt()}", get_ai_keyboard())
            elif t == "✍️ создать пост": admin_state[user_id] = {"mode": "ai_post"}; send_message(vk, user_id, "📝 Пришлите текст и фото:", get_cancel_keyboard())

        else:
            send_message(vk, user_id, "Нажмите кнопку.", get_admin_main_keyboard() if is_admin else get_main_keyboard())
