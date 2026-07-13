# messenger.py — полностью (с логами, исправлен add_donor, snackbar, возврат в Reddit)

import re
import time
import logging
import json
import vk_api
import requests as req
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from datetime import datetime, timedelta, timezone
from config import *
from utils import *
from keyboards import *
from ai_poster import generate_variants, parse_variants, load_prompt, ai_log, generate_text, translate_text, rewrite_text
from holidays import (
    get_holidays_config, save_holidays_config, generate_holidays_list,
    get_holiday_publish_time, create_holiday_post, generate_holiday_text
)
from reddit_handler import load_drafts, save_drafts

waiting_support = set()
selected_post = {}
admin_state = {}

IRK_TZ = timezone(timedelta(hours=8))


def now_irk():
    return datetime.now(IRK_TZ)


def ts_to_irk_str(ts):
    return datetime.fromtimestamp(ts, IRK_TZ).strftime('%d.%m %H:%M')


def answer_callback(vk, event, text="", keyboard=None, snackbar=None):
    try:
        event_data = json.dumps({"type": "show_snackbar", "text": snackbar}) if snackbar else None
        vk.messages.sendMessageEventAnswer(
            event_id=event.object["event_id"],
            user_id=event.object["user_id"],
            peer_id=event.object["peer_id"],
            event_data=event_data
        )
        if text or keyboard:
            conv_msg_id = event.object.get("conversation_message_id")
            send_or_edit(vk, event.object["user_id"], text, keyboard, conv_msg_id)
    except Exception as e:
        logging.error(f"Callback answer error: {e}")


def format_reddit_preview(d, idx, total):
    msg = f"📱 Пост {idx+1}/{total} | {d.get('subreddit', '')}\n\n"
    if d.get('text'):
        msg += f"{d['text'][:500]}\n\n"
    if d.get('vk_attachments'):
        msg += f"🖼 Фото: {len(d['vk_attachments'])} шт.\n"
    if d.get('url'):
        msg += f"🔗 {d['url']}"
    return msg


def show_reddit_draft(vk, user_id, drafts, ids, idx, conv_msg_id=None):
    pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
    ids[:] = list(pending.keys())
    if not ids:
        admin_state.pop(user_id, None)
        send_or_edit(vk, user_id, "📱 Все посты обработаны!", get_admin_main_keyboard())
        return
    idx = min(idx, len(ids) - 1)
    d = pending[ids[idx]]
    msg = format_reddit_preview(d, idx, len(ids))
    admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
    attachments = d.get("vk_attachments", [])
    attachment_str = ",".join(attachments) if attachments else None
    send_or_edit(vk, user_id, msg, get_reddit_post_keyboard(
        bool(d.get('text', '').strip()),
        bool(d.get('title', '').strip())
    ), conv_msg_id, attachment_str)


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


def _extract_photo_from_text(text):
    match = re.search(r'photo(-?\d+_\d+)', text)
    if match:
        return f"photo{match.group(1)}"
    return None


def _handle_suggested_post(vk, post: dict):
    post_id = post.get("id")
    from_id = post.get("from_id") or post.get("signer_id") or 0
    text = post.get("text", "")
    attachments = post.get("attachments", [])
    photo_count = sum(1 for a in attachments if a.get("type") == "photo")

    logging.info(f"📬 Предложка #{post_id} от id{from_id}: текст={bool(text)}, фото={photo_count}")

    if contains_any_link(text) or is_spam(text):
        reason = "ссылки" if contains_any_link(text) else "спам-слова"
        att_str = build_attachments(post)
        moderate_post(vk, post_id, from_id, text, att_str, f"{reason} (предложка)", "suggestion")
        logging.info(f"  ⚠️ Предложка #{post_id} → модерация ({reason})")
        return

    att_str = build_attachments(post)
    new_attachments = att_str.split(",") if att_str else []

    if contains_anonymous(text):
        final_text = f"{text}\n\nАвтор: Аноним"
    elif from_id and from_id > 0:
        try:
            name = get_user_name(vk, from_id)
            final_text = f"{text}\n\nАвтор: [id{from_id}|{name[0]} {name[1]}]"
        except:
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
            logging.info(f"✅ Предложка #{post_id} → отложен на {ts_to_irk_str(slot)} (фото: {len(new_attachments)})")
            try:
                vk.wall.delete(owner_id=-GROUP_ID, post_id=post_id)
            except:
                pass
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
    vk_session = vk_api.VkApi(token=GROUP_TOKEN, api_version="5.199")
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID, wait=25)
    logging.info("🤖 ЛС бот запущен")

    while True:
        try:
            for event in longpoll.listen():

                if event.type == VkBotEventType.MESSAGE_EVENT:
                    payload = event.object.get("payload", {})
                    cmd = payload.get("cmd", "")
                    user_id = event.object["user_id"]
                    is_admin = (user_id == ADMIN_ID)
                    conv_msg_id = event.object.get("conversation_message_id")

                    # ==================== АДМИН-МЕНЮ ====================
                    if cmd == "queue":
                        logging.info(f"📅 [CALLBACK] queue от {user_id}")
                        sched = get_scheduled_posts()
                        msg = "📅 Запланированные:\n\n" + "\n".join(
                            f"• {ts_to_irk_str(p['time'])} — {p['text'][:50]}..."
                            for p in sched[:10]
                        ) if sched else "📭 Пусто."
                        answer_callback(vk, event, msg, get_scheduled_keyboard())

                    elif cmd == "donors":
                        logging.info(f"👥 [CALLBACK] donors от {user_id}")
                        donors = get_donor_groups()
                        logging.info(f"👥 Список доноров: {donors}")
                        msg = "Группы-доноры:\n" + "\n".join(f"• {g} — {get_group_name(vk, g)}" for g in donors) if donors else "📭 Список пуст."
                        answer_callback(vk, event, msg, get_donor_groups_keyboard())

                    elif cmd == "forbidden_words":
                        words = get_forbidden_words()
                        msg = "Запрет-слова:\n📋 " + ", ".join(words) if words else "📭 Список пуст."
                        answer_callback(vk, event, msg, get_forbidden_words_keyboard())

                    elif cmd == "stats":
                        s = get_stats()
                        drafts = load_drafts()
                        reddit_pending = len([v for v in drafts.values() if v.get("status") == "pending"])
                        msg = f"📊 Статистика:\n• Опубликовано: {s['total_published']}\n• Запланировано: {s['scheduled_count']}\n• Reddit постов: {reddit_pending}"
                        answer_callback(vk, event, msg, get_admin_main_keyboard())

                    elif cmd == "admin_menu":
                        logging.info(f"🔙 [CALLBACK] admin_menu от {user_id}")
                        admin_state.pop(user_id, None)
                        drafts = load_drafts()
                        reddit_count = len([v for v in drafts.values() if v.get("status") == "pending"])
                        answer_callback(vk, event, "Админ-меню:", get_admin_main_keyboard(reddit_count))

                    elif cmd == "user_menu":
                        answer_callback(vk, event, "Меню:", get_main_keyboard())

                    # ==================== ДОНОРЫ / СЛОВА ====================
                    elif cmd == "add_donor":
                        logging.info(f"➕ [CALLBACK] add_donor от {user_id}")
                        admin_state[user_id] = {"mode": "add_donor"}
                        answer_callback(vk, event, "Введите ID/ссылку:", get_back_admin_keyboard())

                    elif cmd == "remove_donor_menu":
                        donors = get_donor_groups()
                        answer_callback(vk, event, "Выберите:" if donors else "📭 Пусто.", get_remove_donor_keyboard(donors, vk) if donors else get_donor_groups_keyboard())

                    elif cmd == "remove_donor":
                        gid = payload["group_id"]
                        logging.info(f"➖ [CALLBACK] remove_donor {gid} от {user_id}")
                        remove_donor_group(gid)
                        answer_callback(vk, event, f"✅ Удалена!", get_donor_groups_keyboard(), "Группа удалена")

                    elif cmd == "add_word":
                        admin_state[user_id] = {"mode": "add_word"}
                        answer_callback(vk, event, "Введите слово:", get_back_admin_keyboard())

                    elif cmd == "remove_word_menu":
                        admin_state[user_id] = {"mode": "del_word"}
                        answer_callback(vk, event, "Введите слово:", get_back_admin_keyboard())

                    # ==================== REDDIT ====================
                    elif cmd == "reddit":
                        logging.info(f"📱 [CALLBACK] reddit от {user_id}")
                        drafts = load_drafts()
                        pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                        logging.info(f"📱 Черновиков Reddit: {len(pending)}")
                        if not pending:
                            answer_callback(vk, event, "📱 Нет постов.", get_admin_main_keyboard())
                            continue
                        ids = list(pending.keys())
                        d = pending[ids[0]]
                        msg = format_reddit_preview(d, 0, len(ids))
                        admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": 0}
                        attachments = d.get("vk_attachments", [])
                        attachment_str = ",".join(attachments) if attachments else None
                        send_or_edit(vk, user_id, msg, get_reddit_post_keyboard(
                            bool(d.get('text', '').strip()),
                            bool(d.get('title', '').strip())
                        ), conv_msg_id, attachment_str)

                    elif cmd == "reddit_prev":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            drafts = load_drafts()
                            ids = state.get("ids", [])
                            idx = (state.get("index", 0) - 1) % len(ids) if ids else 0
                            show_reddit_draft(vk, user_id, drafts, ids, idx, conv_msg_id)

                    elif cmd == "reddit_next":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            drafts = load_drafts()
                            ids = state.get("ids", [])
                            idx = (state.get("index", 0) + 1) % len(ids) if ids else 0
                            show_reddit_draft(vk, user_id, drafts, ids, idx, conv_msg_id)

                    elif cmd == "reddit_publish":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            ids = state.get("ids", [])
                            idx = state.get("index", 0)
                            if ids:
                                admin_state[user_id] = {"mode": "reddit_pick_date", "draft_id": ids[idx], "photo_only": False}
                                answer_callback(vk, event, "📅 Выбери дату публикации:", get_reddit_date_keyboard())

                    elif cmd == "reddit_photo_only":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            ids = state.get("ids", [])
                            idx = state.get("index", 0)
                            if ids:
                                admin_state[user_id] = {"mode": "reddit_pick_date", "draft_id": ids[idx], "photo_only": True}
                                answer_callback(vk, event, "📅 Выбери дату публикации:", get_reddit_date_keyboard())

                    elif cmd == "reddit_translate":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            drafts = load_drafts()
                            ids = state.get("ids", [])
                            idx = state.get("index", 0)
                            if ids and ids[idx] in drafts:
                                d = drafts[ids[idx]]
                                d["title"] = translate_text(d.get("original_title", d.get("title", ""))) or d["title"]
                                d["text"] = translate_text(d.get("original_text", d.get("text", ""))) or d["text"]
                                d["translated"] = True
                                save_drafts(drafts)
                            show_reddit_draft(vk, user_id, drafts, ids, idx, conv_msg_id)

                    elif cmd == "reddit_rewrite":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            drafts = load_drafts()
                            ids = state.get("ids", [])
                            idx = state.get("index", 0)
                            if ids and ids[idx] in drafts:
                                rewritten = rewrite_text(drafts[ids[idx]].get("text", ""))
                                if rewritten:
                                    drafts[ids[idx]]["text"] = rewritten
                                    save_drafts(drafts)
                            show_reddit_draft(vk, user_id, drafts, ids, idx, conv_msg_id)

                    elif cmd == "reddit_edit":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            ids = state.get("ids", [])
                            idx = state.get("index", 0)
                            if ids:
                                admin_state[user_id] = {"mode": "reddit_edit_title", "draft_id": ids[idx]}
                                answer_callback(vk, event, "✏️ Введите новый заголовок:", get_cancel_keyboard())

                    elif cmd == "reddit_delete":
                        state = admin_state.get(user_id, {})
                        if state.get("mode") == "reddit_view":
                            drafts = load_drafts()
                            ids = state.get("ids", [])
                            idx = state.get("index", 0)
                            if ids and ids[idx] in drafts:
                                del drafts[ids[idx]]
                                save_drafts(drafts)
                            show_reddit_draft(vk, user_id, drafts, ids, idx, conv_msg_id)

                    elif cmd == "pick_date":
                        state = admin_state.get(user_id, {})
                        state["mode"] = "reddit_pick_range"
                        state["date"] = payload["date"]
                        admin_state[user_id] = state
                        answer_callback(vk, event, f"📅 {payload['date']} — выбери время суток:", get_reddit_range_keyboard())

                    elif cmd == "pick_range":
                        state = admin_state.get(user_id, {})
                        state["mode"] = "reddit_pick_hour"
                        admin_state[user_id] = state
                        start, end = payload["start"], payload["end"]
                        date_str = state.get("date", "")
                        busy = [datetime.fromtimestamp(p["time"]).hour for p in get_scheduled_posts()
                                if datetime.fromtimestamp(p["time"]).strftime("%Y-%m-%d") == date_str
                                and datetime.fromtimestamp(p["time"]).minute == 0]
                        answer_callback(vk, event, f"🕒 Выбери час ({start}:00 – {end}:00):", get_reddit_hour_keyboard(busy, start, end))

                    elif cmd == "back_to_ranges":
                        state = admin_state.get(user_id, {})
                        state["mode"] = "reddit_pick_range"
                        admin_state[user_id] = state
                        answer_callback(vk, event, "🕒 Выбери время суток:", get_reddit_range_keyboard())

                    elif cmd == "pick_hour":
                        state = admin_state.get(user_id, {})
                        date_str = state.get("date", "")
                        hour = payload["hour"]
                        try:
                            base_dt = datetime.strptime(f"{date_str} {hour:02d}:00", "%Y-%m-%d %H:%M").replace(tzinfo=IRK_TZ)
                            pub_time = int(base_dt.timestamp())
                            if pub_time <= int(time.time()) + 60:
                                answer_callback(vk, event, "⏰ Это время уже прошло.", snackbar="Время прошло")
                                continue

                            logging.info(f"📅 Публикация Reddit черновика {state['draft_id']} на {ts_to_irk_str(pub_time)}")
                            publish_reddit_draft(vk, user_id, state["draft_id"], pub_time, state.get("photo_only", False))

                            drafts = load_drafts()
                            pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                            ids = list(pending.keys())
                            when = datetime.fromtimestamp(pub_time, IRK_TZ).strftime('%d.%m %H:%M')
                            snackbar_text = f"✅ Запланировано на {when}"

                            if ids:
                                idx = 0
                                d = pending[ids[idx]]
                                msg = format_reddit_preview(d, idx, len(ids))
                                admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
                                attachments = d.get("vk_attachments", [])
                                attachment_str = ",".join(attachments) if attachments else None
                                send_or_edit(vk, user_id, msg, get_reddit_post_keyboard(
                                    bool(d.get('text', '').strip()),
                                    bool(d.get('title', '').strip())
                                ), conv_msg_id, attachment_str)
                                vk.messages.sendMessageEventAnswer(
                                    event_id=event.object["event_id"],
                                    user_id=user_id,
                                    peer_id=event.object["peer_id"],
                                    event_data=json.dumps({"type": "show_snackbar", "text": snackbar_text})
                                )
                            else:
                                admin_state.pop(user_id, None)
                                answer_callback(vk, event, "📱 Все посты обработаны!", get_admin_main_keyboard(), snackbar=snackbar_text)
                        except:
                            answer_callback(vk, event, "❌ Ошибка даты.", get_admin_main_keyboard())

                    elif cmd == "ai_poster":
                        answer_callback(vk, event, "🤖 AI-постер:", get_ai_keyboard())

                    elif cmd == "ai_create":
                        admin_state[user_id] = {"mode": "ai_post"}
                        answer_callback(vk, event, "📝 Пришлите текст:", get_cancel_keyboard())

                    elif cmd == "ai_prompt":
                        answer_callback(vk, event, f"📋 Текущий промт:\n\n{load_prompt()}", get_ai_keyboard())

                    elif cmd == "ai_publish":
                        state = admin_state.get(user_id, {})
                        chosen = (state.get("variants", [""])[0]) if state.get("variants") else state.get("text", "")
                        vk.wall.post(owner_id=-GROUP_ID, message=chosen, from_group=1)
                        admin_state.pop(user_id, None)
                        answer_callback(vk, event, "✅ Опубликовано!", get_admin_main_keyboard(), "Опубликовано")

                    elif cmd == "ai_custom":
                        admin_state[user_id] = {"mode": "ai_custom"}
                        answer_callback(vk, event, "✏️ Напишите свой текст:", get_cancel_keyboard())

                    elif cmd == "ai_retry":
                        state = admin_state.get(user_id, {})
                        result = generate_variants(state.get("text", ""))
                        if result:
                            variants = parse_variants(result)
                            if variants and len(variants[0]) > 20:
                                state["variants"] = variants
                                admin_state[user_id] = state
                                answer_callback(vk, event, f"🤖 Новый вариант:\n\n{variants[0]}", get_variants_keyboard())
                            else:
                                answer_callback(vk, event, "❌ Не удалось.", get_admin_main_keyboard())

                    elif cmd == "ai_cancel":
                        admin_state.pop(user_id, None)
                        answer_callback(vk, event, "❌ Отменено.", get_admin_main_keyboard())

                    elif cmd == "horoscope":
                        config = load_json("horoscope_config.json", {})
                        next_m = get_horoscope_next_monday()
                        next_str = datetime.fromisoformat(next_m).strftime("%d.%m %H:%M") if next_m else "не запланирован"
                        msg = f"🔮 Гороскоп: {'Включен ✅' if get_horoscope_enabled() else 'Выключен ❌'}\nСледующий: {next_str}"
                        if config.get("photo_id"):
                            msg += f"\n🖼 Фото: {config['photo_id']}"
                        if config.get("text"):
                            msg += f"\n\n📝 Текст:\n{config['text'][:2500]}"
                        answer_callback(vk, event, msg, get_horoscope_keyboard())

                    elif cmd == "horoscope_enable":
                        set_horoscope_enabled(True)
                        answer_callback(vk, event, "🔮 Включен!", get_horoscope_keyboard(), "Включен")

                    elif cmd == "horoscope_disable":
                        set_horoscope_enabled(False)
                        answer_callback(vk, event, "🔮 Выключен.", get_horoscope_keyboard(), "Выключен")

                    elif cmd == "horoscope_photo":
                        admin_state[user_id] = {"mode": "horoscope_photo"}
                        answer_callback(vk, event, "📷 Пришлите фото или ссылку вида https://vk.com/photo-XXXX_YYYY:", get_cancel_keyboard())

                    elif cmd == "horoscope_prompt":
                        try:
                            with open("horoscope_prompt.txt", "r") as f:
                                pt = f.read()
                        except:
                            pt = "Файл не найден"
                        answer_callback(vk, event, f"📋 Промт:\n\n{pt}", get_horoscope_keyboard())

                    elif cmd == "horoscope_recreate":
                        config = load_json("horoscope_config.json", {})
                        config["next_monday"] = ""
                        save_json("horoscope_config.json", config)
                        from weekly_horoscope import create_horoscope
                        if create_horoscope(vk, vk):
                            answer_callback(vk, event, "✅ Создан!", get_horoscope_keyboard(), "Готово")
                        else:
                            answer_callback(vk, event, "❌ Ошибка.", get_horoscope_keyboard())

                    elif cmd == "holidays":
                        config = get_holidays_config()
                        if not config.get("holidays_list"):
                            holidays = generate_holidays_list()
                            if holidays:
                                config["holidays_list"] = holidays
                                config["current_index"] = 0
                                save_holidays_config(config)
                        holidays = config.get("holidays_list", [])
                        idx = config.get("current_index", 0)
                        if holidays and 0 <= idx < len(holidays):
                            h = holidays[idx]
                            config["selected_name"] = h["name"]
                            config["selected_date"] = h["date"]
                            save_holidays_config(config)
                            msg = f"🎉 Праздник ({idx+1}/{len(holidays)}):\n📅 {h['date']} — {h['name']}"
                        else:
                            msg = "📭 Список пуст."
                        answer_callback(vk, event, msg, get_holidays_keyboard())

                    elif cmd == "holiday_prev":
                        config = get_holidays_config()
                        holidays = config.get("holidays_list", [])
                        if holidays:
                            idx = (config.get("current_index", 0) - 1) % len(holidays)
                            config["current_index"] = idx
                            h = holidays[idx]
                            config["selected_name"] = h["name"]
                            config["selected_date"] = h["date"]
                            save_holidays_config(config)
                            answer_callback(vk, event, f"🎉 ({idx+1}/{len(holidays)}): {h['date']} — {h['name']}", get_holidays_keyboard())

                    elif cmd == "holiday_next":
                        config = get_holidays_config()
                        holidays = config.get("holidays_list", [])
                        if holidays:
                            idx = (config.get("current_index", 0) + 1) % len(holidays)
                            config["current_index"] = idx
                            h = holidays[idx]
                            config["selected_name"] = h["name"]
                            config["selected_date"] = h["date"]
                            save_holidays_config(config)
                            answer_callback(vk, event, f"🎉 ({idx+1}/{len(holidays)}): {h['date']} — {h['name']}", get_holidays_keyboard())

                    elif cmd == "holiday_create":
                        config = get_holidays_config()
                        name = config.get("selected_name", "")
                        if name:
                            admin_state[user_id] = {"mode": "holiday_post"}
                            answer_callback(vk, event, f"📷 Пришлите фото или ссылку для: {name}", get_cancel_keyboard())
                        else:
                            answer_callback(vk, event, "❌ Сначала выберите праздник.", get_holidays_keyboard())

                    elif cmd == "holiday_publish":
                        config = get_holidays_config()
                        if create_holiday_post(vk):
                            answer_callback(vk, event, f"✅ Запланировано!", get_admin_main_keyboard(), "Опубликовано")
                        else:
                            answer_callback(vk, event, "❌ Ошибка.", get_holidays_keyboard())

                    elif cmd == "holiday_refresh":
                        holidays = generate_holidays_list()
                        if holidays:
                            config = get_holidays_config()
                            config["holidays_list"] = holidays
                            config["current_index"] = 0
                            h = holidays[0]
                            config["selected_name"] = h["name"]
                            config["selected_date"] = h["date"]
                            save_holidays_config(config)
                            answer_callback(vk, event, f"✅ Обновлено! ({len(holidays)})", get_holidays_keyboard(), "Обновлено")

                    elif cmd == "suggest_post":
                        if is_admin:
                            answer_callback(vk, event, "Ты админ, используй AI или Reddit.", get_admin_main_keyboard())
                        else:
                            admin_state[user_id] = {"mode": "user_post"}
                            answer_callback(vk, event, "📝 Напиши текст поста:", get_cancel_keyboard())

                    elif cmd == "delete_my_post":
                        posts = get_user_posts(user_id)
                        if posts:
                            answer_callback(vk, event, f"📋 Постов: {len(posts)}", get_posts_keyboard(posts))
                        else:
                            answer_callback(vk, event, "📭 Нет постов.", get_main_keyboard())

                    elif cmd == "support":
                        waiting_support.add(user_id)
                        answer_callback(vk, event, "📝 Пишите:", get_cancel_keyboard())

                    elif cmd == "confirm_delete" and user_id in selected_post:
                        pid = selected_post[user_id]
                        if get_post_author(pid) == user_id:
                            try:
                                vk.wall.delete(owner_id=-GROUP_ID, post_id=pid)
                                delete_user_post(user_id, pid)
                                answer_callback(vk, event, f"✅ #{pid} удалён!", get_main_keyboard(), "Удалено")
                            except:
                                answer_callback(vk, event, "❌ Ошибка.", get_main_keyboard())
                        selected_post.pop(user_id, None)

                    elif cmd == "cancel_delete":
                        selected_post.pop(user_id, None)
                        answer_callback(vk, event, "Отменено.", get_main_keyboard())

                    elif cmd == "select_post":
                        posts = get_user_posts(user_id)
                        idx = payload.get("idx", 0)
                        if 0 <= idx < len(posts):
                            selected_post[user_id] = posts[idx]['post_id']
                            answer_callback(vk, event, f"⚠️ Удалить #{posts[idx]['post_id']}?", get_confirm_keyboard())

                    elif cmd == "cancel":
                        admin_state.pop(user_id, None)
                        answer_callback(vk, event, "❌ Отменено.", get_admin_main_keyboard() if is_admin else get_main_keyboard())

                    elif cmd == "back_to_main":
                        answer_callback(vk, event, "Меню:", get_main_keyboard())

                    continue

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

                    if mode == "user_post":
                        if text.lower() in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_main_keyboard())
                            continue
                        post_data = {"post_id": message_id, "from_id": user_id, "text": text, "time": int(now_irk().timestamp())}
                        admin_state.pop(user_id, None)
                        slot = schedule_user_post(vk, post_data)
                        if slot:
                            send_message(vk, user_id, f"✅ Пост принят! Выйдет в {ts_to_irk_str(slot)}.", get_main_keyboard())
                        else:
                            send_message(vk, user_id, "❌ Не удалось.", get_main_keyboard())
                        continue

                    if not is_admin:
                        continue

                    if mode == "add_donor":
                        gid = resolve_group_id(vk, text.strip())
                        logging.info(f"🔍 add_donor: '{text.strip()}' → {gid}")
                        if gid:
                            add_donor_group(gid)
                            current = get_donor_groups()
                            logging.info(f"📝 Список доноров после добавления: {current}")
                            send_or_edit(vk, user_id, f"✅ [{get_group_name(vk, gid)}] добавлена! (всего: {len(current)})", get_donor_groups_keyboard())
                        else:
                            logging.info(f"❌ Не удалось найти группу: {text.strip()}")
                            send_or_edit(vk, user_id, "❌ Не найдена.", get_back_admin_keyboard())
                        admin_state.pop(user_id, None)
                        continue

                    if mode == "add_word":
                        add_forbidden_word(text.strip().lower())
                        admin_state.pop(user_id, None)
                        send_or_edit(vk, user_id, "✅ Добавлено!", get_forbidden_words_keyboard())
                        continue

                    if mode == "del_word":
                        w = text.strip().lower()
                        admin_state.pop(user_id, None)
                        send_or_edit(vk, user_id, "✅ Удалено!" if w in get_forbidden_words() and not remove_forbidden_word(w) else "❌ Не найдено.", get_forbidden_words_keyboard())
                        continue

                    if mode == "ai_post":
                        if text.lower() in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        admin_state[user_id] = {"mode": "ai_choose", "text": text, "variants": []}
                        result = generate_variants(text)
                        if result:
                            variants = parse_variants(result)
                            if variants and len(variants[0]) > 20:
                                admin_state[user_id]["variants"] = variants
                                send_or_edit(vk, user_id, f"🤖 Готовый пост:\n\n{variants[0]}", get_variants_keyboard())
                            else:
                                admin_state.pop(user_id, None)
                                send_or_edit(vk, user_id, "❌ Не удалось.", get_admin_main_keyboard())
                        else:
                            admin_state.pop(user_id, None)
                            send_or_edit(vk, user_id, "❌ Ошибка ИИ.", get_admin_main_keyboard())
                        continue

                    if mode == "ai_custom":
                        if text.lower() in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        vk.wall.post(owner_id=-GROUP_ID, message=text, from_group=1)
                        admin_state.pop(user_id, None)
                        send_message(vk, user_id, "✅ Опубликовано!", get_admin_main_keyboard())
                        continue

                    if mode == "reddit_edit_title":
                        if text.lower() in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        draft_id = state["draft_id"]
                        drafts = load_drafts()
                        if draft_id in drafts:
                            if text != "-":
                                drafts[draft_id]["title"] = text
                                drafts[draft_id]["text"] = text
                            save_drafts(drafts)
                            admin_state[user_id] = {"mode": "reddit_edit_text", "draft_id": draft_id}
                            send_or_edit(vk, user_id, "✏️ Введите новый текст:", get_cancel_keyboard())
                        continue

                    if mode == "reddit_edit_text":
                        if text.lower() in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        draft_id = state["draft_id"]
                        drafts = load_drafts()
                        if draft_id in drafts:
                            if text != "-":
                                drafts[draft_id]["text"] = text
                            save_drafts(drafts)
                            admin_state.pop(user_id, None)
                            pending = {k: v for k, v in drafts.items() if v.get("status") == "pending"}
                            ids = list(pending.keys())
                            if ids:
                                idx = ids.index(draft_id) if draft_id in ids else 0
                                admin_state[user_id] = {"mode": "reddit_view", "ids": ids, "index": idx}
                                d = pending[ids[idx]]
                                msg = format_reddit_preview(d, idx, len(ids))
                                attachments = d.get("vk_attachments", [])
                                attachment_str = ",".join(attachments) if attachments else None
                                send_or_edit(vk, user_id, msg, get_reddit_post_keyboard(
                                    bool(d.get('text', '').strip()),
                                    bool(d.get('title', '').strip())
                                ), attachment=attachment_str)
                            else:
                                send_or_edit(vk, user_id, "📱 Все посты обработаны!", get_admin_main_keyboard())
                        continue

                    if mode in ("horoscope_photo", "holiday_post"):
                        if text.lower() in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue

                        photo_id = upload_photo_from_message(vk, user_id, message_id)
                        if not photo_id:
                            photo_id = _extract_photo_from_text(text)

                        if mode == "horoscope_photo":
                            if photo_id:
                                set_horoscope_photo(photo_id)
                                send_or_edit(vk, user_id, f"✅ Фото сохранено: {photo_id}", get_horoscope_keyboard())
                            else:
                                send_or_edit(vk, user_id, "❌ Не удалось. Пришли фото или ссылку вида https://vk.com/photo-XXXX_YYYY", get_horoscope_keyboard())
                        else:
                            if photo_id:
                                config = get_holidays_config()
                                config["photo_id"] = photo_id
                                save_holidays_config(config)
                                name = config.get("selected_name", "")
                                txt = generate_holiday_text(name)
                                if txt:
                                    config["generated_text"] = txt
                                    save_holidays_config(config)
                                    send_or_edit(vk, user_id, f"🤖 Готово:\n\n{txt[:1500]}", get_holiday_confirm_keyboard())
                                else:
                                    send_or_edit(vk, user_id, "❌ Не удалось.", get_holidays_keyboard())
                            else:
                                send_or_edit(vk, user_id, "❌ Не удалось. Пришли фото или ссылку вида https://vk.com/photo-XXXX_YYYY", get_holidays_keyboard())
                        admin_state.pop(user_id, None)
                        continue

                    if mode == "holiday_custom":
                        if text.lower() in ["🔙 отмена", "❌ отмена"]:
                            admin_state.pop(user_id, None)
                            send_message(vk, user_id, "❌ Отменено.", get_admin_main_keyboard())
                            continue
                        config = get_holidays_config()
                        config["generated_text"] = text
                        save_holidays_config(config)
                        admin_state.pop(user_id, None)
                        send_or_edit(vk, user_id, f"📝 Сохранено.", get_holiday_confirm_keyboard())
                        continue

                if user_id in waiting_support:
                    waiting_support.discard(user_id)
                    if text.lower() not in ["🔙 отмена", "/cancel"] and ADMIN_ID:
                        vk.messages.send(user_id=ADMIN_ID, message=f"📨 ОБРАЩЕНИЕ\nhttps://vk.com/gim{GROUP_ID}?sel={user_id}", random_id=0, forward_messages=message_id, group_id=GROUP_ID)
                        send_message(vk, user_id, "✅ Отправлено!", get_main_keyboard())
                    else:
                        send_message(vk, user_id, "Отменено.", get_main_keyboard())
                    continue

                t = text.lower()
                if t in ["начать", "меню", "start"]:
                    drafts = load_drafts()
                    reddit_count = len([v for v in drafts.values() if v.get("status") == "pending"])
                    k = get_admin_main_keyboard(reddit_count) if is_admin else get_main_keyboard()
                    vk.messages.send(
                        user_id=user_id,
                        message="👋 Привет! Выбери действие:",
                        random_id=0,
                        keyboard=k.get_keyboard()
                    )

        except Exception as e:
            logging.error(f"LongPoll error: {e}")
            time.sleep(5)


def publish_reddit_draft(vk, user_id, draft_id, pub_time, photo_only=False):
    drafts = load_drafts()
    d = drafts.get(draft_id)
    if not d:
        send_message(vk, user_id, "❌ Черновик не найден.", get_admin_main_keyboard())
        return

    attachments = d.get("vk_attachments", [])
    post_text = "" if photo_only else d.get("text", "")

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
            break
        except:
            break

    if posted:
        add_scheduled_post(pub_time, post_text[:200] if post_text else "Фото из Reddit", 0)
        del drafts[draft_id]
        save_drafts(drafts)
    else:
        send_message(vk, user_id, "❌ Ошибка публикации.", get_admin_main_keyboard())


def schedule_user_post(vk, post_data):
    from photo_utils import copy_photos_from_message
    post_id = post_data["post_id"]
    from_id = post_data["from_id"]
    text = post_data["text"]
    new_attachments = copy_photos_from_message(vk, post_id, GROUP_ID)

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

    for _ in range(96):
        try:
            kwargs["publish_date"] = slot
            vk.wall.post(**kwargs)
            add_scheduled_post(slot, final_text[:200], from_id)
            return slot
        except vk_api.exceptions.ApiError as e:
            if e.code == 214 or "already scheduled" in str(e).lower():
                slot += PUBLISH_INTERVAL
                continue
            return None
        except:
            return None
    return None
