import re
import time
import logging
import vk_api
import requests as req
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from datetime import datetime, timedelta
from config import *
from utils import *
from keyboards import *
from ai_poster import generate_variants, parse_variants, load_prompt, ai_log, generate_text, translate_text, rewrite_text
from holidays import (
    get_holidays_config, save_holidays_config, generate_holidays_list,
    get_holiday_publish_time, create_holiday_post, generate_holiday_text
)
from reddit_handler import load_drafts, save_drafts, upload_photos_to_vk

waiting_support = set()
selected_post = {}
admin_state = {}


def format_reddit_preview(d, idx, total):
    msg = f"📱 Пост {idx+1}/{total} | {d.get('subreddit', '')}\n\n"
    if d.get('title'):
        msg += f"📌 {d['title']}\n\n"
    if d.get('text'):
        msg += f"{d['text'][:500]}\n\n"
    if d.get('images'):
        msg += f"🖼 Фото: {len(d['images'])} шт.\n"
    if d.get('url'):
        msg += f"🔗 {d['url']}"
    return msg


def show_reddit_draft(vk, user_id, drafts, ids, idx):
    pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
    ids[:] = list(pending.keys())
    if not ids:
        admin_state.pop(user_id, None)
        send_message(vk, user_id, "📱 Все посты обработаны!", get_admin_main_keyboard())
        return
    idx = min(idx, len(ids) - 1)
    d = pending[ids[idx]]
    msg = format_reddit_preview(d, idx, len(ids))
    admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
    send_or_edit(vk, user_id, msg, get_reddit_post_keyboard(
        bool(d.get('text', '').strip()),
        bool(d.get('title', '').strip())
    ))


def upload_photo_from_message(vk, user_id, message_id):
    from photo_utils import upload_photo_to_group
    try:
        msg_data = vk.messages.getById(message_ids=message_id, group_id=GROUP_ID)
        if msg_data and msg_data.get("items"):
            for att in msg_data["items"][0].get("attachments", []):
                if att.get("type") == "photo":
                    return upload_photo_to_group(vk, att["photo"])
    except Exception as e:
        logging.error(f"Ошибка загрузки фото: {e}")
    return None


def _handle_suggested_post(vk, post: dict):
    """Обрабатывает предложенный пост (WALL_POST_NEW с post_type='suggest')."""
    from photo_utils import copy_attachments

    post_id = post.get("id")
    from_id = post.get("from_id") or post.get("signer_id") or 0
    text = post.get("text", "")
    attachments = post.get("attachments", [])
    photo_count = sum(1 for a in attachments if a.get("type") == "photo")

    logging.info(f"📬 Предложка #{post_id} от id{from_id}: текст={bool(text)}, фото={photo_count}")

    if contains_any_link(text) or is_spam(text):
        reason = "ссылки" if contains_any_link(text) else "спам-слова"
        att_str = ",".join(
            f"photo{a['photo']['owner_id']}_{a['photo']['id']}"
            for a in attachments if a.get("type") == "photo"
        )
        moderate_post(vk, post_id, from_id, text, att_str,
                      f"{reason} (предложка)", "suggestion")
        logging.info(f"  ⚠️ Предложка #{post_id} → модерация ({reason})")
        return

    new_attachments = copy_attachments(vk, attachments)

    if contains_anonymous(text):
        final_text = f"{text}\n\nАвтор: Аноним"
    elif from_id and from_id > 0:
        try:
            name = get_user_name(vk, from_id)
            final_text = f"{text}\n\nАвтор: [id{from_id}|{name[0]} {name[1]}]"
        except Exception:
            final_text = f"{text}\n\nАвтор: id{from_id}"
    else:
        final_text = text

    slot = get_next_schedule_time(PUBLISH_INTERVAL)
    kwargs = {"owner_id": -GROUP_ID, "message": final_text, "from_group": 1}
    if new_attachments:
        kwargs["attachments"] = ",".join(new_attachments)

    for _ in range(96):
        try:
            kwargs["publish_date"] = slot
            vk.wall.post(**kwargs)
            add_scheduled_post(slot, final_text[:200], from_id)
            when = datetime.fromtimestamp(slot).strftime("%d.%m %H:%M")
            logging.info(f"✅ Предложка #{post_id} → отложен на {when} "
                         f"({'фото: ' + str(len(new_attachments)) if new_attachments else 'без фото'})")

            if ADMIN_ID:
                try:
                    try:
                        name = get_user_name(vk, from_id)
                        author = f"{name[0]} {name[1]}"
                    except Exception:
                        author = f"id{from_id}"
                    msg = f"📨 Новая предложка от {author}!\n📝 {text[:200]}"
                    if photo_count:
                        msg += f"\n📷 Фото: {photo_count} шт."
                    msg += f"\n\n🕒 Отложен на {when}"
                    vk.messages.send(user_id=ADMIN_ID, message=msg, random_id=0, group_id=GROUP_ID)
                except Exception as e:
                    logging.warning(f"Не удалось уведомить админа: {e}")
            return
        except vk_api.exceptions.ApiError as e:
            if e.code == 214 or "already scheduled" in str(e).lower():
                slot += PUBLISH_INTERVAL
                continue
            logging.error(f"❌ VK API ошибка предложки #{post_id}: {e}")
            return
        except Exception as e:
            logging.error(f"❌ Ошибка публикации предложки #{post_id}: {e}")
            return


def run_messenger():
    vk_session = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.131")
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID, wait=25)
    logging.info("🤖 ЛС бот запущен")

    while True:
        try:
            for event in longpoll.listen():
                # === ПРЕДЛОЖЕННЫЙ ПОСТ (кнопка «Предложить запись» в группе) ===
                if event.type == VkBotEventType.WALL_POST_NEW:
                    post = event.object
                    if post.get("post_type") == "suggest":
                        _handle_suggested_post(vk, post)
                    continue

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

                if user_id in admin_state:
                    state = admin_state[user_id]
                    mode = state.get("mode")
                    t = text.lower()

                    if mode == "user_post":
                        if t in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_main_keyboard())
                            continue

                        post_data = {
                            "post_id": message_id,
                            "from_id": user_id,
                            "text": text,
                            "time": int(datetime.now().timestamp())
                        }
                        admin_state.pop(user_id, None)

                        slot = schedule_user_post(vk, post_data)
                        if slot:
                            when = datetime.fromtimestamp(slot).strftime("%H:%M")
                            send_message(vk, user_id, f"✅ Пост принят! Он выйдет из отложенных в {when}.", get_main_keyboard())
                            if ADMIN_ID:
                                try:
                                    author_name = get_user_name(vk, user_id)
                                    author_str = f"{author_name[0]} {author_name[1]}"
                                except:
                                    author_str = f"id{user_id}"
                                vk.messages.send(
                                    user_id=ADMIN_ID,
                                    message=f"📨 Новый пост от {author_str}!\n📝 {text[:200]}\n\n🕒 Отложен на {when}",
                                    random_id=0,
                                    group_id=GROUP_ID
                                )
                        else:
                            send_message(vk, user_id, "❌ Не удалось запланировать пост, попробуй позже.", get_main_keyboard())
                        continue

                    if not is_admin:
                        continue

                    if mode == "reddit_view":
                        drafts = load_drafts()
                        pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                        ids = state.get("ids", [])
                        idx = state.get("index", 0)

                        if not pending:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                            continue

                        if t == "⬅️ назад":
                            idx = (idx - 1) % len(ids)
                            show_reddit_draft(vk, user_id, drafts, ids, idx)
                            continue
                        elif t == "➡️ вперёд":
                            idx = (idx + 1) % len(ids)
                            show_reddit_draft(vk, user_id, drafts, ids, idx)
                            continue
                        elif t == "✅ опубликовать":
                            draft_id = ids[idx]
                            admin_state[user_id] = {"mode": "reddit_pick_date", "draft_id": draft_id, "photo_only": False}
                            send_message(vk, user_id, "📅 Выбери дату публикации:", get_reddit_date_keyboard())
                            continue
                        elif t == "📷 только фото":
                            draft_id = ids[idx]
                            d = pending[draft_id]
                            if not d.get('images'):
                                send_message(vk, user_id, "❌ Нет фото в этом посте.")
                                continue
                            admin_state[user_id] = {"mode": "reddit_pick_date", "draft_id": draft_id, "photo_only": True}
                            send_message(vk, user_id, "📅 Выбери дату публикации:", get_reddit_date_keyboard())
                            continue
                        elif "перевести" in t:
                            draft_id = ids[idx]
                            d = pending[draft_id]
                            original_text = d.get("original_text", d.get("text", ""))
                            original_title = d.get("original_title", d.get("title", ""))
                            send_or_edit(vk, user_id, "⏳ Перевожу...")
                            if original_title:
                                translated_title = translate_text(original_title)
                                if translated_title:
                                    drafts[draft_id]["title"] = translated_title
                            if original_text:
                                translated_text = translate_text(original_text)
                                if translated_text:
                                    drafts[draft_id]["text"] = translated_text
                                    drafts[draft_id]["translated"] = True
                            save_drafts(drafts)
                            show_reddit_draft(vk, user_id, drafts, ids, idx)
                            continue
                        elif "перефразировать" in t:
                            draft_id = ids[idx]
                            d = pending[draft_id]
                            original = d.get("text", "")
                            if original:
                                send_or_edit(vk, user_id, "⏳ Перефразирую...")
                                rewritten = rewrite_text(original)
                                if rewritten:
                                    drafts[draft_id]["text"] = rewritten
                                    save_drafts(drafts)
                            show_reddit_draft(vk, user_id, drafts, ids, idx)
                            continue
                        elif "править" in t:
                            admin_state[user_id] = {"mode": "reddit_edit_title", "draft_id": ids[idx]}
                            send_message(vk, user_id, "✏️ Введите новый заголовок (или '-' чтобы оставить):", get_cancel_keyboard())
                            continue
                        elif "удалить" in t:
                            del drafts[ids[idx]]
                            save_drafts(drafts)
                            show_reddit_draft(vk, user_id, drafts, ids, idx)
                            continue
                        elif t == "🔙 в админку":
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                            continue
                        show_reddit_draft(vk, user_id, drafts, ids, idx)
                        continue

                    if mode == "reddit_pick_date":
                        if t in ["🔙 в админку", "❌ отмена", "🔙 отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                            continue
                        m = re.search(r'(\d{2})\.(\d{2})', text)
                        if not m:
                            send_or_edit(vk, user_id, "📅 Выбери дату кнопкой:", get_reddit_date_keyboard())
                            continue
                        day, month = int(m.group(1)), int(m.group(2))
                        base = datetime.now()
                        chosen = None
                        for i in range(0, 14):
                            cand = base + timedelta(days=i)
                            if cand.day == day and cand.month == month:
                                chosen = cand
                                break
                        if not chosen:
                            send_or_edit(vk, user_id, "📅 Не понял дату, выбери кнопкой:", get_reddit_date_keyboard())
                            continue
                        date_str = chosen.strftime("%Y-%m-%d")
                        state["mode"] = "reddit_pick_range"
                        state["date"] = date_str
                        admin_state[user_id] = state
                        send_or_edit(vk, user_id, f"📅 {chosen.strftime('%d.%m')} — выбери время суток:", get_reddit_range_keyboard())
                        continue

                    if mode == "reddit_pick_range":
                        if t in ["🔙 в админку", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                            continue
                        date_str = state.get("date")
                        busy = [datetime.fromtimestamp(p["time"]).hour
                                for p in get_scheduled_posts()
                                if datetime.fromtimestamp(p["time"]).strftime("%Y-%m-%d") == date_str
                                and datetime.fromtimestamp(p["time"]).minute == 0]
                        ranges = {"🌅 утро": (8, 11), "☀️ день": (12, 16), "🌆 вечер": (17, 20), "🌙 ночь": (21, 23)}
                        matched = None
                        for label, (start, end) in ranges.items():
                            if label in t:
                                matched = (start, end)
                                break
                        if not matched:
                            send_or_edit(vk, user_id, "🕒 Выбери диапазон кнопкой:", get_reddit_range_keyboard())
                            continue
                        start, end = matched
                        state["mode"] = "reddit_pick_hour"
                        admin_state[user_id] = state
                        send_or_edit(vk, user_id, f"🕒 Выбери час ({start}:00 – {end}:00):", get_reddit_hour_keyboard(busy, start, end))
                        continue

                    if mode == "reddit_pick_hour":
                        if t == "⬅️ к диапазонам":
                            date_str = state.get("date")
                            state["mode"] = "reddit_pick_range"
                            admin_state[user_id] = state
                            send_or_edit(vk, user_id, "🕒 Выбери время суток:", get_reddit_range_keyboard())
                            continue
                        if t in ["🔙 в админку", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                            continue
                        m = re.match(r'^\s*(\d{1,2}):00\s*$', text)
                        if not m:
                            send_or_edit(vk, user_id, "🕒 Выбери час кнопкой или введи вручную (например 15):")
                            continue
                        hour = int(m.group(1))
                        date_str = state.get("date")
                        try:
                            base_dt = datetime.strptime(f"{date_str} {hour:02d}:00", "%Y-%m-%d %H:%M")
                        except:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Ошибка даты.", get_admin_main_keyboard())
                            continue
                        pub_time = int(base_dt.timestamp())
                        if pub_time <= int(time.time()) + 60:
                            send_or_edit(vk, user_id, "⏰ Это время уже прошло, выбери другой час.")
                            continue
                        logging.info(f"📅 Публикация Reddit поста на {datetime.fromtimestamp(pub_time).strftime('%d.%m %H:%M')}")
                        publish_reddit_draft(vk, user_id, state["draft_id"], pub_time, state.get("photo_only", False))
                        admin_state.pop(user_id, None)
                        continue

                    if mode == "ai_post":
                        if t in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        attachments = ""
                        try:
                            msg_data = vk.messages.getById(message_ids=message_id, group_id=GROUP_ID)
                            if msg_data and msg_data.get("items"):
                                attachments = build_attachments(msg_data["items"][0])
                        except:
                            pass
                        admin_state[user_id] = {"mode": "ai_choose", "text": text, "variants": [], "attachments": attachments}
                        send_message(vk, user_id, "⏳ Генерирую пост...")
                        result = generate_variants(text)
                        if result:
                            variants = parse_variants(result)
                            if variants and len(variants[0]) > 20:
                                admin_state[user_id]["variants"] = variants
                                send_or_edit(vk, user_id, f"🤖 Готовый пост:\n\n{variants[0]}", get_variants_keyboard())
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
                            att = state.get("attachments", "") or None
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
                                    send_or_edit(vk, user_id, f"🤖 Новый вариант:\n\n{variants[0]}", get_variants_keyboard())
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
                        att = state.get("attachments", "") or None
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
                        drafts = load_drafts()
                        if draft_id in drafts:
                            if t != "-":
                                drafts[draft_id]["text"] = text
                            save_drafts(drafts)
                            pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                            ids = list(pending.keys())
                            if ids:
                                try:
                                    idx = ids.index(draft_id)
                                except ValueError:
                                    idx = 0
                                show_reddit_draft(vk, user_id, drafts, ids, idx)
                            else:
                                admin_state.pop(user_id, None)
                                send_message(vk, user_id, "📱 Все посты обработаны!", get_admin_main_keyboard())
                        else:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Черновик не найден.", get_admin_main_keyboard())
                        continue

                    if mode == "horoscope_photo":
                        if t in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        photo_id = upload_photo_from_message(vk, user_id, message_id)
                        if photo_id:
                            set_horoscope_photo(photo_id)
                            send_message(vk, user_id, "✅ Фото сохранено!", get_horoscope_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не удалось загрузить фото.", get_horoscope_keyboard())
                        admin_state.pop(user_id, None)
                        continue

                    if mode == "holiday_post":
                        if t in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        photo_id = upload_photo_from_message(vk, user_id, message_id)
                        if photo_id:
                            config = get_holidays_config()
                            config["photo_id"] = photo_id
                            save_holidays_config(config)
                            name = config.get("selected_name", "")
                            send_or_edit(vk, user_id, f"✅ Фото сохранено!\n⏳ Генерирую для: {name}")
                            txt = generate_holiday_text(name)
                            if txt:
                                config["generated_text"] = txt
                                save_holidays_config(config)
                                send_or_edit(vk, user_id, f"🤖 Готово:\n\n{txt[:1500]}", get_holiday_confirm_keyboard())
                            else:
                                send_message(vk, user_id, "❌ Не удалось сгенерировать текст.", get_holidays_keyboard())
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
                        admin_state.pop(user_id, None)
                        continue

                    if mode == "add_word":
                        add_forbidden_word(text.strip().lower())
                        send_message(vk, user_id, "✅ Добавлено!", get_forbidden_words_keyboard())
                        admin_state.pop(user_id, None)
                        continue

                    if mode == "del_word":
                        w = text.strip().lower()
                        if w in get_forbidden_words():
                            remove_forbidden_word(w)
                            send_message(vk, user_id, "✅ Удалено!", get_forbidden_words_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не найдено.", get_forbidden_words_keyboard())
                        admin_state.pop(user_id, None)
                        continue

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

                elif is_admin:
                    if t in ["🔙 назад в админку", "🔙 назад"]:
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "Админ-меню:", get_admin_main_keyboard())
                    elif t == "🔙 польз. меню":
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
                        drafts = load_drafts()
                        pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                        if not pending:
                            send_message(vk, user_id, "📱 Нет постов.", get_admin_main_keyboard())
                            continue
                        ids = list(pending.keys())
                        d = pending[ids[0]]
                        msg = format_reddit_preview(d, 0, len(ids))
                        admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": 0}
                        send_message(vk, user_id, msg, get_reddit_post_keyboard(bool(d.get('text', '').strip()), bool(d.get('title', '').strip())))
                    elif t == "📊 статистика":
                        s = get_stats()
                        drafts = load_drafts()
                        reddit_pending = len([v for v in drafts.values() if v.get("status") == "pending"])
                        msg = f"📊 Статистика:\n• Опубликовано: {s['total_published']}\n• Запланировано: {s['scheduled_count']}\n• Reddit постов: {reddit_pending}"
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
                        if config.get("text"):
                            msg += f"\n\n📝 Текст:\n{config['text'][:2500]}"
                        send_message(vk, user_id, msg, get_horoscope_keyboard())
                    elif t == "🗑 пересоздать":
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
                            if config.get("text"):
                                msg += f"\n\n📝 Текст:\n{config['text'][:2500]}"
                            send_message(vk, user_id, msg, get_horoscope_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Ошибка.", get_horoscope_keyboard())
                    elif t == "▶️ включить":
                        set_horoscope_enabled(True)
                        send_message(vk, user_id, "🔮 Включен!", get_horoscope_keyboard())
                    elif t == "⏸️ выключить":
                        set_horoscope_enabled(False)
                        send_message(vk, user_id, "🔮 Выключен.", get_horoscope_keyboard())
                    elif t == "📋 промт":
                        try:
                            with open("horoscope_prompt.txt", "r", encoding="utf-8") as f:
                                prompt_text = f.read()
                        except:
                            prompt_text = "Файл не найден"
                        send_message(vk, user_id, f"📋 Промт гороскопа:\n\n{prompt_text}", get_horoscope_keyboard())
                    elif t == "🖼️ фото":
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
                            send_or_edit(vk, user_id, f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
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
                            send_or_edit(vk, user_id, f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}", get_holidays_keyboard())
                    elif t == "✍️ создать":
                        config = get_holidays_config()
                        name = config.get("selected_name", "")
                        if not name:
                            send_message(vk, user_id, "❌ Сначала выберите праздник.", get_holidays_keyboard())
                            continue
                        admin_state[user_id] = {"mode": "holiday_post"}
                        send_message(vk, user_id, f"📷 Пришлите фото для: {name}", get_cancel_keyboard())
                    elif t == "✅ опубликовать":
                        config = get_holidays_config()
                        text_msg = config.get("generated_text", "")
                        date_str = config.get("selected_date", "")
                        if not text_msg:
                            send_message(vk, user_id, "❌ Сначала сгенерируйте текст.", get_holidays_keyboard())
                            continue
                        send_message(vk, user_id, f"⏳ Планирую на {date_str}...")
                        if create_holiday_post(vk):
                            send_message(vk, user_id, f"✅ Запланировано!\n📅 {date_str} 10:00", get_admin_main_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Ошибка.", get_holidays_keyboard())
                    elif t == "✏️ свой текст":
                        admin_state[user_id] = {"mode": "holiday_custom"}
                        send_message(vk, user_id, "✏️ Напишите свой текст:", get_cancel_keyboard())
                    elif t == "🔄 ещё вариант":
                        config = get_holidays_config()
                        name = config.get("selected_name", "")
                        send_message(vk, user_id, "⏳ Генерирую...")
                        text_msg = generate_holiday_text(name)
                        if text_msg:
                            config["generated_text"] = text_msg
                            save_holidays_config(config)
                            send_or_edit(vk, user_id, f"🤖 Новый вариант:\n\n{text_msg[:1500]}", get_holiday_confirm_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Ошибка.", get_holidays_keyboard())
                    elif t == "🔄 обновить":
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

        except Exception as e:
            logging.error(f"LongPoll error: {e}")
            time.sleep(5)


def publish_reddit_draft(vk, user_id, draft_id, pub_time, photo_only=False):
    drafts = load_drafts()
    d = drafts.get(draft_id)
    if not d:
        send_message(vk, user_id, "❌ Черновик не найден.", get_admin_main_keyboard())
        return
    attachments = []
    if d.get("images"):
        logging.info(f"📸 Загружаю {len(d['images'])} фото для Reddit поста {draft_id}...")
        send_or_edit(vk, user_id, "⏳ Загружаю фото...")
        try:
            attachments, errors = upload_photos_to_vk(d.get("images", [])[:10])
            if errors:
                logging.warning(f"📸 Ошибки загрузки фото: {errors}")
            logging.info(f"📸 Загружено {len(attachments)} фото")
        except Exception as e:
            logging.error(f"📸 Ошибка загрузки фото: {e}")
            attachments = []
    if photo_only:
        if not attachments:
            send_message(vk, user_id, "❌ Не удалось загрузить фото.", get_admin_main_keyboard())
            return
        post_text = d.get("title", "")
    else:
        post_text = d.get("text", "")
        if d.get("title") and not post_text:
            post_text = d["title"]
        elif d.get("title"):
            post_text = f"{d['title']}\n\n{post_text}"
        if not post_text and attachments:
            post_text = d.get("title", "")
    posted = False
    for _ in range(48):
        try:
            vk.wall.post(owner_id=-GROUP_ID, message=post_text[:4000] if post_text else "",
                         attachments=",".join(attachments) if attachments else None, from_group=1, publish_date=pub_time)
            posted = True
            break
        except vk_api.exceptions.ApiError as e:
            if e.code == 214 or "already scheduled" in str(e).lower():
                pub_time += 3600
                continue
            logging.error(f"❌ VK API ошибка: code={e.code}, msg={e}")
            break
        except Exception as e:
            logging.error(f"❌ Ошибка публикации Reddit: {e}")
            break
    if posted:
        add_scheduled_post(pub_time, post_text[:200] if post_text else "Фото из Reddit", 0)
        del drafts[draft_id]
        save_drafts(drafts)
        when = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
        total_images = len(d.get("images", []))
        msg = f"✅ Запланировано на {when}!"
        if attachments:
            msg += f" 📸 {len(attachments)}/{total_images} фото"
        send_message(vk, user_id, msg, get_admin_main_keyboard())
    else:
        send_message(vk, user_id, "❌ Ошибка публикации.", get_admin_main_keyboard())


def schedule_user_post(vk, post_data):
    from photo_utils import copy_photos_from_message
    post_id = post_data["post_id"]
    from_id = post_data["from_id"]
    text = post_data["text"]
    logging.info(f"📨 Публикация поста #{post_id}: текст={text[:50] if text else 'нет'}")
    new_attachments = copy_photos_from_message(vk, post_id, GROUP_ID)
    if new_attachments:
        logging.info(f"📷 Загружено фото: {len(new_attachments)} шт.")
    if contains_anonymous(text):
        final_text = f"{text}\n\nАвтор: Аноним"
    else:
        try:
            name = get_user_name(vk, from_id)
            final_text = f"{text}\n\nАвтор: [id{from_id}|{name[0]} {name[1]}]"
        except:
            final_text = f"{text}\n\nАвтор: id{from_id}"
    slot = get_next_schedule_time(PUBLISH_INTERVAL)
    kwargs = {"owner_id": -GROUP_ID, "message": final_text, "from_group": 1}
    if new_attachments:
        kwargs["attachments"] = ",".join(new_attachments)
    logging.info(f"===== WALL.POST (отложено) =====")
    logging.info(f"message_len={len(kwargs['message'])}, attachments={kwargs.get('attachments', 'нет')}")
    for _ in range(96):
        try:
            kwargs["publish_date"] = slot
            vk.wall.post(**kwargs)
            add_scheduled_post(slot, final_text[:200], from_id)
            logging.info(f"✅ Пост #{post_id} отложен на {datetime.fromtimestamp(slot).strftime('%H:%M')}")
            return slot
        except vk_api.exceptions.ApiError as e:
            if e.code == 214 or "already scheduled" in str(e).lower():
                slot += PUBLISH_INTERVAL
                continue
            logging.error(f"❌ VK API ошибка #{post_id}: code={e.code}, msg={e}")
            return None
        except Exception as e:
            logging.error(f"❌ Ошибка публикации #{post_id}: {e}")
            return None
    return None
