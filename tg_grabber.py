import logging
import json
import requests
import vk_api
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import *

DRAFTS_FILE = "tg_drafts.json"
seen = set()

# ─── Черновая работа с черновиками ───

def load_drafts():
    try:
        with open(DRAFTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_drafts(data):
    with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ─── VK ───

def vk_upload_photo(file_bytes):
    vk = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    upload = vk.photos.getWallUploadServer(group_id=GROUP_ID)
    r = requests.post(upload["upload_url"], files={"photo": file_bytes}).json()
    if 'photo' in r and r['photo']:
        saved = vk.photos.saveWallPhoto(photo=r['photo'], server=r['server'], hash=r['hash'], group_id=GROUP_ID)
        if saved:
            p = saved[0]
            return f"photo{p['owner_id']}_{p['id']}"
    return None

def vk_post(text, attachments, publish_time=None):
    vk = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    try:
        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text or "",
            attachments=",".join(attachments) if attachments else None,
            from_group=1,
            publish_date=publish_time
        )
        return True
    except Exception as e:
        logging.error(f"TG VK post error: {e}")
        return False

def next_hour_timestamp():
    now = datetime.now()
    nxt = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return int(nxt.timestamp())

# ─── Клавиатура ───

def build_keyboard(msg_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Только фото", callback_data=f"photo:{msg_id}"),
            InlineKeyboardButton("📝 Только текст", callback_data=f"text:{msg_id}")
        ],
        [
            InlineKeyboardButton("📤 В VK (сейчас)", callback_data=f"send_now:{msg_id}"),
            InlineKeyboardButton("⏰ В VK (отложка)", callback_data=f"send_sched:{msg_id}")
        ],
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"del:{msg_id}")
        ]
    ])

# ─── Обработчики ───

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.message_id in seen:
        return
    seen.add(msg.message_id)

    text = msg.text or msg.caption or ""
    photos = []

    if msg.photo:
        file = await msg.photo[-1].get_file()
        file_bytes = await file.download_as_bytearray()
        photos.append(file_bytes.hex())  # храним как hex строку в JSON

    drafts = load_drafts()
    drafts[str(msg.message_id)] = {"text": text, "photos": photos}
    save_drafts(drafts)

    await msg.reply_text(
        f"📥 Пост получен\nТекст: {text[:100]}...\nФото: {len(photos)} шт.\n\nВыбери действие:",
        reply_markup=build_keyboard(msg.message_id)
    )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, msg_id = query.data.split(":")
    msg_id = int(msg_id)

    drafts = load_drafts()
    if str(msg_id) not in drafts:
        await query.edit_message_text("❌ Пост не найден")
        return

    d = drafts[str(msg_id)]

    if action == "photo":
        d["text"] = ""
        save_drafts(drafts)
        await query.edit_message_text("✅ Оставлено только фото")

    elif action == "text":
        d["photos"] = []
        save_drafts(drafts)
        await query.edit_message_text("✅ Оставлен только текст")

    elif action == "send_now":
        attachments = []
        for ph_hex in d["photos"]:
            file_bytes = bytes.fromhex(ph_hex)
            att = vk_upload_photo(file_bytes)
            if att:
                attachments.append(att)

        if vk_post(d["text"], attachments):
            del drafts[str(msg_id)]
            save_drafts(drafts)
            await query.edit_message_text("✅ Опубликовано в ВК!")
        else:
            await query.edit_message_text("❌ Ошибка публикации")

    elif action == "send_sched":
        attachments = []
        for ph_hex in d["photos"]:
            file_bytes = bytes.fromhex(ph_hex)
            att = vk_upload_photo(file_bytes)
            if att:
                attachments.append(att)

        pub_time = next_hour_timestamp()
        if vk_post(d["text"], attachments, pub_time):
            del drafts[str(msg_id)]
            save_drafts(drafts)
            pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
            await query.edit_message_text(f"✅ Запланировано на {pub_str}")
        else:
            await query.edit_message_text("❌ Ошибка публикации")

    elif action == "del":
        del drafts[str(msg_id)]
        save_drafts(drafts)
        await query.edit_message_text("🗑 Удалено")

# ─── Запуск ───

def run_tg_bot():
    if not TG_BOT_TOKEN:
        logging.warning("📡 ТГ-бот: не указан TG_BOT_TOKEN")
        return

    app = ApplicationBuilder().token(TG_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))
    app.add_handler(CallbackQueryHandler(on_button))

    logging.info("📡 ТГ-бот запущен")

    app.run_polling(
        poll_interval=2,
        timeout=10,
        drop_pending_updates=True
    )
