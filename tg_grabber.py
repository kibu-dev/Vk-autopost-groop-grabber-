import logging
import requests
import vk_api
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import *

drafts = {}
seen = set()

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

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.message_id in seen:
        return
    seen.add(msg.message_id)

    text = msg.text or msg.caption or ""
    photos = []

    if msg.photo:
        file = await msg.photo[-1].get_file()
        photos.append(file)

    drafts[msg.message_id] = {"text": text, "photos": photos}

    await msg.reply_text(
        f"📥 Пост получен\nТекст: {text[:100]}...\nФото: {len(photos)} шт.\n\nВыбери действие:",
        reply_markup=build_keyboard(msg.message_id)
    )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, msg_id = query.data.split(":")
    msg_id = int(msg_id)

    if msg_id not in drafts:
        await query.edit_message_text("❌ Пост не найден")
        return

    d = drafts[msg_id]

    if action == "photo":
        d["text"] = ""
        await query.edit_message_text("✅ Оставлено только фото")

    elif action == "text":
        d["photos"] = []
        await query.edit_message_text("✅ Оставлен только текст")

    elif action == "send_now":
        attachments = []
        for p in d["photos"]:
            file_bytes = await p.download_as_bytearray()
            att = vk_upload_photo(file_bytes)
            if att:
                attachments.append(att)

        if vk_post(d["text"], attachments):
            await query.edit_message_text("✅ Опубликовано в ВК!")
        else:
            await query.edit_message_text("❌ Ошибка публикации")

    elif action == "send_sched":
        attachments = []
        for p in d["photos"]:
            file_bytes = await p.download_as_bytearray()
            att = vk_upload_photo(file_bytes)
            if att:
                attachments.append(att)

        pub_time = next_hour_timestamp()
        if vk_post(d["text"], attachments, pub_time):
            pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
            await query.edit_message_text(f"✅ Запланировано на {pub_str}")
        else:
            await query.edit_message_text("❌ Ошибка публикации")

    elif action == "del":
        del drafts[msg_id]
        await query.edit_message_text("🗑 Удалено")

def run_tg_bot():
    if not TG_BOT_TOKEN:
        logging.warning("📡 ТГ-бот: не указан TG_BOT_TOKEN")
        return

    app = ApplicationBuilder().token(TG_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))
    app.add_handler(CallbackQueryHandler(on_button))

    logging.info("📡 ТГ-бот запущен")
    app.run_polling()
