import re
import time
import logging
import vk_api
import requests as req
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from datetime import datetime
from config import *
from utils import *
from keyboards import *
from ai_poster import generate_variants, parse_variants, load_prompt, ai_log, generate_text, translate_text, rewrite_text
from holidays import (
    get_holidays_config, save_holidays_config, generate_holidays_list,
    get_holiday_publish_time, create_holiday_post, generate_holiday_text
)

waiting_support = set()
selected_post = {}
admin_state = {}
pending_posts = []
last_user_post_time = 0

def run_messenger():
    global last_user_post_time

    vk_session = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131")
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID, wait=25)
    logging.info("🤖 ЛС бот запущен")

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        msg = event.object.get("message", {})
        user_id = msg.get("from_id")
        text = msg.get("text", "").strip()
        is_admin = (user_id == ADMIN_ID)
        message_id = msg.get("id")

        if not user_id or not text:
            continue

        logging.info(f"MSG: '{text[:80]}' | ADMIN: {is_admin} | STATE: {admin_state.get(user_id, {}).get('mode', 'none')}")

        # === РЕЖИМЫ АДМИНА ===
        if is_admin and user_id in admin_state:
            state = admin_state[user_id]
            mode = state.get("mode")
            t = text.lower()

            # === REDDIT NAVIGATION ===
            if mode == "reddit_view":
                logging.info("REDDIT VIEW MODE")
                from reddit_handler import load_drafts, save_drafts
                drafts = load_drafts()
                pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                ids = state.get("ids", [])
                idx = state.get("index", 0)

                if not pending:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                    continue

                if t == "⬅️ назад": idx = (idx - 1) % len(ids)
                elif t == "➡️ вперёд": idx = (idx + 1) % len(ids)

                elif t == "✅ опубликовать":
                    draft_id = ids[idx]; d = pending[draft_id]
                    attachments = []
                    
                    if d.get('images'):
                        send_message(vk, user_id, "⏳ Загружаю фото...")
                        from reddit_handler import upload_photos_to_vk
                        attachments, _ = upload_photos_to_vk(d.get('images', [])[:10])

                    post_text = d.get('text', '')
                    if d.get('title') and not post_text: post_text = d['title']
                    elif d.get('title'): post_text = f"{d['title']}\n\n{post_text}"
                    if not post_text and attachments: post_text = d.get('title', '')

                    pub_time = get_next_free_hour()
                    posted = False
                    for attempt in range(24):
                        try:
                            vk.wall.post(
                                owner_id=-GROUP_ID,
                                message=post_text[:4000] if post_text else "",
                                attachments=",".join(attachments) if attachments else None,
                                from_group=1,
                                publish_date=pub_time
                            )
                            posted = True
                            break
                        except Exception as e:
                            if "214" in str(e) or "already scheduled" in str(e):
                                pub_time += 3600
                                logging.info(f"⏰ Время занято, пробую {datetime.fromtimestamp(pub_time).strftime('%H:%M')}")
                            else:
                                logging.error(f"❌ Ошибка публикации: {e}")
                                break

                    if posted:
                        add_scheduled_post(pub_time, post_text[:200] if post_text else "Фото", 0)
                        del drafts[draft_id]; save_drafts(drafts)
                        total_images = len(d.get('images', []))
                        msg = f"✅ В очереди на {datetime.fromtimestamp(pub_time).strftime('%H:%M')}!"
                        if attachments: msg += f" 📸 {len(attachments)}/{total_images} фото"
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, msg, get_admin_main_keyboard())
                    else:
                        send_message(vk, user_id, "❌ Ошибка публикации.", get_admin_main_keyboard())
                        admin_state.pop(user_id, None)
                    continue

                elif t == "📷 только фото":
                    draft_id = ids[idx]; d = pending[draft_id]
                    
                    if not d.get('images'):
                        send_message(vk, user_id, "❌ Нет фото в этом посте.")
                        continue
                    
                    send_message(vk, user_id, "⏳ Загружаю фото...")
                    from reddit_handler import upload_photos_to_vk
                    attachments, _ = upload_photos_to_vk(d.get('images', [])[:10])
                    
                    if not attachments:
                        send_message(vk, user_id, "❌ Не удалось загрузить фото.")
                        continue

                    pub_time = get_next_free_hour()
                    posted = False
                    for attempt in range(24):
                        try:
                            vk.wall.post(
                                owner_id=-GROUP_ID,
                                attachments=",".join(attachments),
                                from_group=1,
                                publish_date=pub_time
                            )
                            posted = True
                            break
                        except Exception as e:
                            if "214" in str(e) or "already scheduled" in str(e):
                                pub_time += 3600
                            else:
                                break
                    if posted:
                        add_scheduled_post(pub_time, "Фото из Reddit", 0)
                        del drafts[draft_id]; save_drafts(drafts)
                        total_images = len(d.get('images', []))
                        msg = f"✅ Фото в очереди на {datetime.fromtimestamp(pub_time).strftime('%H:%M')}! 📸 {len(attachments)}/{total_images} фото"
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, msg, get_admin_main_keyboard())
                    else:
                        send_message(vk, user_id, "❌ Ошибка публикации.")
                    continue

                elif "перевести" in t:
                    draft_id = ids[idx]; d = pending[draft_id]
                    original_text = d.get("original_text", d.get("text", ""))
                    original_title = d.get("original_title", d.get("title", ""))

                    if original_title:
                        send_message(vk, user_id, "⏳ Перевожу заголовок...")
                        translated_title = translate_text(original_title)
                        if translated_title: drafts[draft_id]["title"] = translated_title

                    if original_text:
                        send_message(vk, user_id, "⏳ Перевожу текст...")
                        translated_text = translate_text(original_text)
                        if translated_text:
                            drafts[draft_id]["text"] = translated_text
                            drafts[draft_id]["translated"] = True

                    save_drafts(drafts)
                    send_message(vk, user_id, "✅ Переведено!")
                    pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                    ids = list(pending.keys())
                    if ids:
                        idx = min(idx, len(ids) - 1); d = pending[ids[idx]]
                        msg = f"📱 Пост {idx+1}/{len(ids)} | {d.get('subreddit', '')}\n\n"
                        if d.get('title'): msg += f"📌 {d['title']}\n\n"
                        if d.get('text'): msg += f"{d['text'][:500]}\n\n"
                        if d.get('images'): msg += f"🖼 Фото: {len(d['images'])} шт.\n"
                        if d.get('url'): msg += f"🔗 {d['url']}"
                        admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
                        send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip()), bool(d.get('title', '').strip())))
                    else:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                    continue

                elif "перефразировать" in t:
                    draft_id = ids[idx]; d = pending[draft_id]
                    original = d.get("text", "")
                    if original:
                        send_message(vk, user_id, "⏳ Перефразирую...")
                        rewritten = rewrite_text(original)
                        if rewritten:
                            drafts[draft_id]["text"] = rewritten; save_drafts(drafts)
                            send_message(vk, user_id, f"✅ Готово!")
                        else:
                            send_message(vk, user_id, "❌ Ошибка.")
                    pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                    ids = list(pending.keys())
                    if ids:
                        idx = min(idx, len(ids) - 1); d = pending[ids[idx]]
                        msg = f"📱 Пост {idx+1}/{len(ids)} | {d.get('subreddit', '')}\n\n"
                        if d.get('title'): msg += f"📌 {d['title']}\n\n"
                        if d.get('text'): msg += f"{d['text'][:500]}\n\n"
                        if d.get('images'): msg += f"🖼 Фото: {len(d['images'])} шт.\n"
                        if d.get('url'): msg += f"🔗 {d['url']}"
                        admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
                        send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip()), bool(d.get('title', '').strip())))
                    else:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                    continue

                elif "править" in t:
                    admin_state[user_id] = {"mode": "reddit_edit_title", "draft_id": ids[idx]}
                    send_message(vk, user_id, "✏️ Введите новый заголовок (или '-' чтобы оставить):", get_cancel_keyboard())
                    continue

                elif "удалить" in t:
                    del drafts[ids[idx]]; save_drafts(drafts)
                    pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                    ids = list(pending.keys())
                    if ids:
                        idx = min(idx, len(ids) - 1); d = pending[ids[idx]]
                        msg = f"📱 Пост {idx+1}/{len(ids)} | {d.get('subreddit', '')}\n\n"
                        if d.get('title'): msg += f"📌 {d['title']}\n\n"
                        if d.get('text'): msg += f"{d['text'][:500]}\n\n"
                        if d.get('images'): msg += f"🖼 Фото: {len(d['images'])} шт.\n"
                        if d.get('url'): msg += f"🔗 {d['url']}"
                        admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
                        send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip()), bool(d.get('title', '').strip())))
                    else:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                    continue

                elif t == "🔙 в админку":
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                    continue

                pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                ids = list(pending.keys())
                if not ids:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                    continue
                idx = min(idx, len(ids) - 1); d = pending[ids[idx]]
                msg = f"📱 Пост {idx+1}/{len(ids)} | {d.get('subreddit', '')}\n\n"
                if d.get('title'): msg += f"📌 {d['title']}\n\n"
                if d.get('text'): msg += f"{d['text'][:500]}\n\n"
                if d.get('images'): msg += f"🖼 Фото: {len(d['images'])} шт.\n"
                if d.get('url'): msg += f"🔗 {d['url']}"
                admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
                send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip()), bool(d.get('title', '').strip())))
                continue

            # AI-постер
            if mode == "ai_post":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                attachments = []
                try:
                    msg_data = vk.messages.getById(message_ids=message_id, group_id=GROUP_ID)
                    if msg_data and msg_data.get("items"):
                        for att in msg_data["items"][0].get("attachments", []):
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
                    r = vk.wall.post(owner_id=-GROUP_ID, message=chosen, attachments=att, from_group=1)
                    add_published_post(r["post_id"], ADMIN_ID, chosen)
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "✅ Опубликовано!" + (" 📎" if att else ""), get_admin_main_keyboard())
                elif t == "✏️ свой текст":
                    admin_state[user_id] = {"mode": "ai_custom"}
                    send_message(vk, user_id, "✏️ Напишите свой текст:", get_cancel_keyboard())
                elif t == "🔄 ещё вариант":
                    result = generate_variants(state["text"])
                    if result:
                        variants = parse_variants(result)
                        if variants and len(variants[0]) > 20:
                            state["variants"] = variants
                            send_message(vk, user_id, f"🤖 Новый вариант:\n\n{variants[0]}", get_variants_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не удалось.", get_admin_main_keyboard())
                    else:
                        send_message(vk, user_id, "❌ Ошибка ИИ.", get_admin_main_keyboard())
                elif t == "❌ отмена":
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                continue

            if mode == "ai_custom":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                att = ",".join(state.get("attachments", [])) or None
                r = vk.wall.post(owner_id=-GROUP_ID, message=text, attachments=att, from_group=1)
                add_published_post(r["post_id"], ADMIN_ID, text)
                admin_state.pop(user_id, None)
                send_message(vk, user_id, "✅ Опубликовано!", get_admin_main_keyboard())
                continue

            if mode == "reddit_edit_title":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                draft_id = state.get("draft_id")
                from reddit_handler import load_drafts, save_drafts
                drafts = load_drafts()
                if draft_id in drafts:
                    if t != "-":
                        drafts[draft_id]["title"] = text
                    save_drafts(drafts)
                    admin_state[user_id] = {"mode": "reddit_edit_text", "draft_id": draft_id}
                    send_message(vk, user_id, "✏️ Введите новый текст (или '-' чтобы оставить):", get_cancel_keyboard())
                else:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Черновик не найден.", get_admin_main_keyboard())
                continue

            if mode == "reddit_edit_text":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                draft_id = state.get("draft_id")
                from reddit_handler import load_drafts, save_drafts
                drafts = load_drafts()
                if draft_id in drafts:
                    if t != "-":
                        drafts[draft_id]["text"] = text
                    save_drafts(drafts)
                    send_message(vk, user_id, "✅ Текст обновлён!", get_admin_main_keyboard())
                else:
                    send_message(vk, user_id, "❌ Черновик не найден.", get_admin_main_keyboard())
                admin_state.pop(user_id, None)
                continue

            if mode == "horoscope_photo":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                photo_saved = False
                try:
                    msg_data = vk.messages.getById(message_ids=message_id, group_id=GROUP_ID)
                    if msg_data and msg_data.get("items"):
                        for att in msg_data["items"][0].get("attachments", []):
                            if att.get("type") == "photo":
                                att_obj = att.get("photo", {})
                                sizes = att_obj.get("sizes", [])
                                if sizes:
                                    biggest = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
                                    if biggest.get("url"):
                                        img_data = req.get(biggest["url"]).content
                                        up_server = vk.photos.getWallUploadServer(group_id=GROUP_ID)
                                        up = req.post(up_server['upload_url'], files={'photo': ('h.jpg', img_data, 'image/jpeg')}).json()
                                        if 'photo' in up and up['photo']:
                                            saved = vk.photos.saveWallPhoto(photo=up['photo'], server=up['server'], hash=up['hash'], group_id=GROUP_ID)
                                            if saved:
                                                set_horoscope_photo(f"photo{saved[0]['owner_id']}_{saved[0]['id']}")
                                                photo_saved = True
                                        break
                except: pass
                send_message(vk, user_id, "✅ Фото сохранено!" if photo_saved else "❌ Не удалось.", get_horoscope_keyboard())
                admin_state.pop(user_id, None)
                continue

            if mode == "holiday_post":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                photo_saved = False
                try:
                    msg_data = vk.messages.getById(message_ids=message_id, group_id=GROUP_ID)
                    if msg_data and msg_data.get("items"):
                        for att in msg_data["items"][0].get("attachments", []):
                            if att.get("type") == "photo":
                                att_obj = att.get("photo", {})
                                sizes = att_obj.get("sizes", [])
                                if sizes:
                                    biggest = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
                                    if biggest.get("url"):
                                        img_data = req.get(biggest["url"]).content
                                        up_server = vk.photos.getWallUploadServer(group_id=GROUP_ID)
                                        up = req.post(up_server['upload_url'], files={'photo': ('hol.jpg', img_data, 'image/jpeg')}).json()
                                        if 'photo' in up and up['photo']:
                                            saved = vk.photos.saveWallPhoto(photo=up['photo'], server=up['server'], hash=up['hash'], group_id=GROUP_ID)
                                            if saved:
                                                config = get_holidays_config()
                                                config["photo_id"] = f"photo{saved[0]['owner_id']}_{saved[0]['id']}"
                                                save_holidays_config(config)
                                                photo_saved = True
                                        break
                except: pass
                if photo_saved:
                    config = get_holidays_config()
                    name = config.get("selected_name", "")
                    send_message(vk, user_id, f"✅ Фото сохранено!\n⏳ Генерирую для: {name}")
                    txt = generate_holiday_text(name)
                    if txt:
                        config["generated_text"] = txt
                        save_holidays_config(config)
                        send_message(vk, user_id, f"🤖 Готово:\n\n{txt[:1500]}", get_holiday_confirm_keyboard())
                    else:
                        send_message(vk, user_id, "❌ Не удалось.", get_holidays_keyboard())
                else:
                    send_message(vk, user_id, "❌ Не удалось загрузить фото.", get_holidays_keyboard())
                admin_state.pop(user_id, None)
                continue

            if mode == "holiday_custom":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                    continue
                config = get_holidays_config()
                config["generated_text"] = text
                save_holidays_config(config)
                admin_state.pop(user_id, None)
                send_message(vk, user_id, f"📝 Ваш текст:\n\n{text[:500]}...", get_holiday_confirm_keyboard())
                continue

            # === ПОЛЬЗОВАТЕЛЬ ПРИСЫЛАЕТ ПОСТ ===
            if mode == "user_post":
                if t in ["🔙 отмена", "❌ отмена"]:
                    admin_state.pop(user_id, None)
                    send_message(vk, user_id, "❌ Отменено.", get_main_keyboard())
                    continue

                attachments = ""
                try:
                    msg_data = vk.messages.getById(message_ids=message_id, group_id=GROUP_ID)
                    if msg_data and msg_data.get("items"):
                        for att in msg_data["items"][0].get("attachments", []):
                            att_type = att.get("type")
                            att_obj = att.get(att_type, {})
                            oid = att_obj.get("owner_id")
                            iid = att_obj.get("id")
                            if oid and iid:
                                attachments += f"{att_type}{oid}_{iid},"
                except:
                    pass

                post_data = {
                    "post_id": int(datetime.now().timestamp()),
                    "from_id": user_id,
                    "text": text,
                    "attachments": attachments.rstrip(','),
                    "time": int(datetime.now().timestamp())
                }
                pending_posts.append(post_data)
                logging.info(f"📨 Пост от пользователя {user_id} (очередь: {len(pending_posts)})")

                if ADMIN_ID:
                    try:
                        author_name = get_user_name(vk, user_id)
                        author_str = f"{author_name[0]} {author_name[1]}"
                    except:
                        author_str = f"id{user_id}"
                    vk.messages.send(
                        user_id=ADMIN_ID,
                        message=f"📨 Новый пост от {author_str}!\n📝 {text[:200]}\n\nОчередь: {len(pending_posts)} постов",
                        random_id=0,
                        group_id=GROUP_ID
                    )

                admin_state.pop(user_id, None)
                send_message(vk, user_id, "✅ Пост принят! Он появится на стене в ближайшее время.", get_main_keyboard())
                publish_from_queue(vk)
                continue

            if t in ["🔙 отмена", "🔙 назад в админку", "🔙 назад"]:
                admin_state.pop(user_id, None)
                send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                continue

            if mode == "add_donor":
                gid = resolve_group_id(vk, text.strip())
                if gid:
                    add_donor_group(gid)
                    send_message(vk, user_id, f"✅ [{get_group_name(vk, gid)}] добавлена!", get_donor_groups_keyboard())
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
            
            if mode in ["add_donor", "add_word", "del_word"]:
                admin_state.pop(user_id, None)
                continue

        # === ОЖИДАНИЕ ПОДДЕРЖКИ ===
        if user_id in waiting_support:
            waiting_support.discard(user_id)
            if text.lower() not in ["🔙 отмена", "/cancel"]:
                if ADMIN_ID:
                    try:
                        vk.messages.send(
                            user_id=ADMIN_ID,
                            message=f"📨 ОБРАЩЕНИЕ\nhttps://vk.com/gim{GROUP_ID}?sel={user_id}",
                            random_id=0,
                            forward_messages=message_id,
                            group_id=GROUP_ID
                        )
                        send_message(vk, user_id, "✅ Отправлено!", get_main_keyboard())
                    except:
                        send_message(vk, user_id, "❌ Ошибка.", get_main_keyboard())
            else:
                send_message(vk, user_id, "Отменено.", get_main_keyboard())
            continue

        # === ОБРАБОТКА КНОПОК ===
        t = text.lower()

        if t in ["начать", "меню", "start"]:
            send_message(vk, user_id, "👋 Привет!", get_admin_main_keyboard() if is_admin else get_main_keyboard())

        elif t == "📝 предложить пост":
            if is_admin:
                send_message(vk, user_id, "Ты админ, можешь публиковать через AI-постер или Reddit.", get_admin_main_keyboard())
            else:
                admin_state[user_id] = {"mode": "user_post"}
                send_message(vk, user_id, "📝 Напиши текст поста (можно с фото).\nДля анонимности добавь 'анон' в текст.", get_cancel_keyboard())

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
            admin_state.pop(user_id, None)
            send_message(vk, user_id, "Меню:", get_admin_main_keyboard() if is_admin else get_main_keyboard())

        elif t == "❌ нет":
            selected_post.pop(user_id, None)
            send_message(vk, user_id, "Отменено.", get_main_keyboard())

        elif t == "✅ да, удалить" and user_id in selected_post:
            pid = selected_post[user_id]
            if get_post_author(pid) == user_id:
                try:
                    vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
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

        # === АДМИН-МЕНЮ ===
        elif is_admin:
            if t in ["🔙 назад в админку", "🔙 назад"]:
                admin_state.pop(user_id, None)
                send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
            elif t == "🔙 пользовательское меню":
                send_message(vk, user_id, "Меню:", get_main_keyboard())
            elif t == "📅 очередь постов":
                sched = get_scheduled_posts()
                if sched:
                    msg = "📅 Запланированные:\n\n"
                    for p in sched[:10]:
                        msg += f"• {datetime.fromtimestamp(p['time']).strftime('%d.%m %H:%M')} — {p['text'][:50]}...\n"
                    send_message(vk, user_id, msg, get_scheduled_keyboard())
                else:
                    send_message(vk, user_id, "📭 Пусто.", get_admin_main_keyboard())
            elif t == "👥 группы-доноры":
                donors = get_donor_groups()
                if donors:
                    send_message(vk, user_id, "Группы-доноры:\n" + "\n".join([f"• {g} — {get_group_name(vk, g)}" for g in donors]), get_donor_groups_keyboard())
                else:
                    send_message(vk, user_id, "📭 Список пуст.", get_donor_groups_keyboard())
            elif t == "🚫 запрет-слова":
                words = get_forbidden_words()
                if words:
                    send_message(vk, user_id, "Запрет-слова:\n📋 " + ", ".join(words), get_forbidden_words_keyboard())
                else:
                    send_message(vk, user_id, "📭 Список пуст.", get_forbidden_words_keyboard())

            elif t == "📱 reddit":
                from reddit_handler import load_drafts
                drafts = load_drafts()
                pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                if not pending:
                    send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                    continue
                ids = list(pending.keys())
                d = pending[ids[0]]
                msg = f"📱 Пост 1/{len(ids)} | {d.get('subreddit', '')}\n\n"
                if d.get('title'): msg += f"📌 {d['title']}\n\n"
                if d.get('text'): msg += f"{d['text'][:500]}\n\n"
                if d.get('images'): msg += f"🖼 Фото: {len(d['images'])} шт.\n"
                if d.get('url'): msg += f"🔗 {d['url']}"
                admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": 0}
                send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip()), bool(d.get('title', '').strip())))

            elif t == "📊 статистика":
                s = get_stats()
                from reddit_handler import load_drafts
                drafts = load_drafts()
                reddit_pending = len([v for v in drafts.values() if v.get("status") == "pending"])
                msg = f"📊 Статистика:\n• Опубликовано: {s['total_published']}\n• Запланировано: {s['scheduled_count']}\n• Взято граббером: {s['total_grabbed']}\n• На модерации: {s['pending_moderation']}\n• Reddit: {reddit_pending}\n• Доноров: {s['donor_count']}"
                send_message(vk, user_id, msg, get_admin_main_keyboard())

            elif t == "➕ добавить группу":
                admin_state[user_id] = {"mode": "add_donor"}
                send_message(vk, user_id, "Введите ID/ссылку:", get_back_admin_keyboard())
            elif t == "➖ удалить группу":
                donors = get_donor_groups()
                if donors:
                    send_message(vk, user_id, "Выберите:", get_remove_donor_keyboard(donors, vk))
                else:
                    send_message(vk, user_id, "📭 Пусто.", get_donor_groups_keyboard())
            elif t.startswith("➖ "):
                donors = get_donor_groups()
                for g in donors:
                    try:
                        name = get_group_name(vk, g)
                    except:
                        name = str(g)
                    if t == f"➖ {name}".lower()[:40]:
                        remove_donor_group(g)
                        send_message(vk, user_id, f"✅ [{name}] удалена!", get_donor_groups_keyboard())
                        break

            elif t == "➕ добавить слово":
                admin_state[user_id] = {"mode": "add_word"}
                send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())
            elif t == "➖ удалить слово":
                admin_state[user_id] = {"mode": "del_word"}
                send_message(vk, user_id, "Введите слово:", get_back_admin_keyboard())

            elif t == "🔮 гороскоп":
                config = load_json("horoscope_config.json", {})
                next_m = get_horoscope_next_monday()
                next_str = datetime.fromisoformat(next_m).strftime("%d.%m %H:%M") if next_m else "не запланирован"
                msg = f"🔮 Гороскоп: {'Включен ✅' if get_horoscope_enabled() else 'Выключен ❌'}\nСледующий: {next_str}"
                if config.get("text"): msg += f"\n\n📝 Текст:\n{config['text'][:2500]}"
                send_message(vk, user_id, msg, get_horoscope_keyboard())
            elif t == "удалить и пересоздать":
                config = load_json("horoscope_config.json", {})
                config["next_monday"] = ""
                save_json("horoscope_config.json", config)
                send_message(vk, user_id, "🔄 Создаю новый гороскоп...")
                from weekly_horoscope import create_horoscope
                if create_horoscope(vk, vk):
                    config = load_json("horoscope_config.json", {})
                    next_m = config.get("next_monday", "")
                    next_str = datetime.fromisoformat(next_m).strftime("%d.%m %H:%M") if next_m else "не запланирован"
                    msg = f"✅ Готово!\n🔮 Гороскоп: {'Включен ✅' if get_horoscope_enabled() else 'Выключен ❌'}\nСледующий: {next_str}"
                    if config.get("text"): msg += f"\n\n📝 Текст:\n{config['text'][:2500]}"
                    send_message(vk, user_id, msg, get_horoscope_keyboard())
                else:
                    send_message(vk, user_id, "❌ Ошибка.", get_horoscope_keyboard())
            elif t == "▶️ включить гороскоп":
                set_horoscope_enabled(True)
                send_message(vk, user_id, "🔮 Включен!", get_horoscope_keyboard())
            elif t == "⏸️ выключить гороскоп":
                set_horoscope_enabled(False)
                send_message(vk, user_id, "🔮 Выключен.", get_horoscope_keyboard())
            elif t == "📋 промт гороскопа":
                try:
                    with open("horoscope_prompt.txt", "r", encoding="utf-8") as f:
                        prompt_text = f.read()
                except:
                    prompt_text = "Файл не найден"
                send_message(vk, user_id, f"📋 Промт гороскопа:\n\n{prompt_text}", get_horoscope_keyboard())
            elif t == "🖼️ сменить фото":
                admin_state[user_id] = {"mode": "horoscope_photo"}
                send_message(vk, user_id, "📷 Пришлите новое фото:", get_cancel_keyboard())

            elif t == "🎉 праздники":
                config = get_holidays_config()
                if not config.get("holidays_list"):
                    send_message(vk, user_id, "⏳ Загружаю...")
                    holidays = generate_holidays_list()
                    if holidays:
                        config["holidays_list"] = holidays
                        config["current_index"] = 0
                        save_holidays_config(config)
                    else:
                        send_message(vk, user_id, "❌ Не удалось.", get_admin_main_keyboard())
                        continue
                holidays = config.get("holidays_list", [])
                idx = config.get("current_index", 0)
                if 0 <= idx < len(holidays):
                    h = holidays[idx]
                    config["selected_name"] = h["name"]
                    config["selected_date"] = h["date"]
                    save_holidays_config(config)
                    msg = f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}"
                else:
                    msg = "📭 Список пуст."
                send_message(vk, user_id, msg, get_holidays_keyboard())
            elif t == "⬅️ предыдущий":
                config = get_holidays_config()
                holidays = config.get("holidays_list", [])
                if holidays:
                    idx = (config.get("current_index", 0) - 1) % len(holidays)
                    config["current_index"] = idx
                    h = holidays[idx]
                    config["selected_name"] = h["name"]
                    config["selected_date"] = h["date"]
                    save_holidays_config(config)
                    send_message(vk, user_id, f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
            elif t == "➡️ следующий":
                config = get_holidays_config()
                holidays = config.get("holidays_list", [])
                if holidays:
                    idx = (config.get("current_index", 0) + 1) % len(holidays)
                    config["current_index"] = idx
                    h = holidays[idx]
                    config["selected_name"] = h["name"]
                    config["selected_date"] = h["date"]
                    save_holidays_config(config)
                    send_message(vk, user_id, f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
            elif t == "✍️ создать поздравление":
                config = get_holidays_config()
                name = config.get("selected_name", "")
                if not name:
                    send_message(vk, user_id, "❌ Сначала выберите праздник.", get_holidays_keyboard())
                    continue
                admin_state[user_id] = {"mode": "holiday_post"}
                send_message(vk, user_id, f"📷 Пришлите фото для: {name}", get_cancel_keyboard())
            elif t == "✅ опубликовать (праздник)":
                config = get_holidays_config()
                text = config.get("generated_text", "")
                date_str = config.get("selected_date", "")
                if not text:
                    send_message(vk, user_id, "❌ Сначала сгенерируйте текст.", get_holidays_keyboard())
                    continue
                send_message(vk, user_id, f"⏳ Планирую на {date_str}...")
                if create_holiday_post(vk):
                    send_message(vk, user_id, f"✅ Запланировано!\n📅 {date_str} 10:00", get_admin_main_keyboard())
                else:
                    send_message(vk, user_id, "❌ Ошибка.", get_holidays_keyboard())
            elif t == "✏️ написать свой текст":
                admin_state[user_id] = {"mode": "holiday_custom"}
                send_message(vk, user_id, "✏️ Напишите свой текст:", get_cancel_keyboard())
            elif t == "🔄 сгенерировать ещё":
                config = get_holidays_config()
                name = config.get("selected_name", "")
                send_message(vk, user_id, "⏳ Генерирую...")
                text = generate_holiday_text(name)
                if text:
                    config["generated_text"] = text
                    save_holidays_config(config)
                    send_message(vk, user_id, f"🤖 Новый вариант:\n\n{text[:1500]}", get_holiday_confirm_keyboard())
                else:
                    send_message(vk, user_id, "❌ Ошибка.", get_holidays_keyboard())
            elif t == "🔄 обновить список":
                send_message(vk, user_id, "⏳ Обновляю...")
                holidays = generate_holidays_list()
                if holidays:
                    config = get_holidays_config()
                    config["holidays_list"] = holidays
                    config["current_index"] = 0
                    save_holidays_config(config)
                    h = holidays[0]
                    config["selected_name"] = h["name"]
                    config["selected_date"] = h["date"]
                    save_holidays_config(config)
                    send_message(vk, user_id, f"✅ Обновлено! ({len(holidays)})\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
                else:
                    send_message(vk, user_id, "❌ Не удалось.", get_holidays_keyboard())

            elif t == "🤖 ai-постер":
                send_message(vk, user_id, "🤖 AI-постер:", get_ai_keyboard())
            elif t == "📋 промт":
                send_message(vk, user_id, f"📋 Текущий промт:\n\n{load_prompt()}", get_ai_keyboard())
            elif t == "✍️ создать пост":
                admin_state[user_id] = {"mode": "ai_post"}
                send_message(vk, user_id, "📝 Пришлите текст и фото:", get_cancel_keyboard())

            else:
                send_message(vk, user_id, "Нажмите кнопку.", get_admin_main_keyboard())

        else:
            send_message(vk, user_id, "Нажмите кнопку.", get_main_keyboard())

        # === ПЕРИОДИЧЕСКАЯ ПУБЛИКАЦИЯ ИЗ ОЧЕРЕДИ ===
        try:
            now = time.time()
            if now - last_user_post_time >= PUBLISH_INTERVAL and pending_posts:
                publish_from_queue(vk)
        except:
            pass


def publish_from_queue(vk):
    global pending_posts, last_user_post_time
    if not pending_posts:
        return

    now = time.time()
    if now - last_user_post_time < PUBLISH_INTERVAL:
        return

    post_data = pending_posts.pop(0)
    post_id = post_data["post_id"]
    from_id = post_data["from_id"]
    text = post_data["text"]
    attachments = post_data["attachments"]

    logging.info(f"📨 Планирование поста #{post_id}: текст={text[:50] if text else 'нет'}")

    if contains_anonymous(text):
        final_text = f"{text}\n\nАвтор: Аноним"
    else:
        try:
            author_name = get_user_name(vk, from_id)
            final_text = f"{text}\n\nАвтор: [id{from_id}|{author_name[0]} {author_name[1]}]"
        except:
            final_text = f"{text}\n\nАвтор: id{from_id}"

    pub_time = get_next_free_hour()
    posted = False
    for attempt in range(24):
        try:
            kwargs = {
                "owner_id": -GROUP_ID,
                "message": final_text,
                "from_group": 1,
                "publish_date": pub_time
            }
            if attachments:
                kwargs["attachments"] = attachments

            result = vk.wall.post(**kwargs)
            posted = True
            break
        except Exception as e:
            if "214" in str(e) or "already scheduled" in str(e):
                pub_time += 3600
                logging.info(f"⏰ Время занято, пробую {datetime.fromtimestamp(pub_time).strftime('%H:%M')}")
            else:
                logging.error(f"❌ Ошибка планирования #{post_id}: {e}")
                break

    if posted:
        add_scheduled_post(pub_time, text[:200], from_id)
        add_published_post(post_id, from_id, text)
        last_user_post_time = time.time()
        pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
        logging.info(f"✅ Пост #{post_id} запланирован на {pub_str} от {from_id}")

        if from_id:
            try:
                vk.messages.send(
                    user_id=from_id,
                    message=f"✅ Твой пост запланирован на {pub_str} МСК и появится на стене.",
                    random_id=0,
                    group_id=GROUP_ID
                )
            except:
                pass
    else:
        logging.error(f"❌ Не удалось запланировать пост #{post_id}")
