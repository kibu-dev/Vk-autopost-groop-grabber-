import time
import logging
import requests
import vk_api
from telethon import TelegramClient, events
from config import *
from utils import *

def run_tg_grabber():
    if not TG_API_ID or not TG_API_HASH:
        logging.warning("📡 ТГ-граббер: не указаны TG_API_ID/TG_API_HASH")
        return

    vk_user = vk_api.VkApi(token=USER_TOKEN, api_version="5.131").get_api()
    
    client = TelegramClient("tg_session", TG_API_ID, TG_API_HASH)
    
    logging.info("📡 ТГ-граббер запущен")

    async def main():
        channels = get_tg_channels()
        if channels:
            @client.on(events.NewMessage(chats=channels))
            async def handler(event):
                if not is_tg_grab_enabled():
                    return
                
                msg = event.message
                msg_id = msg.id
                channel = event.chat.username or str(event.chat.id)
                
                if is_tg_post_grabbed(msg_id, channel):
                    return
                
                add_tg_grabbed(msg_id, channel)
                
                text = msg.message or ""
                
                if contains_any_link(text) or is_spam(text):
                    reason = "ссылки" if contains_any_link(text) else "спам-слова"
                    logging.info(f"📡 ТГ пост {msg_id} → модерация ({reason})")
                    return
                
                attachments = []
                if msg.photo:
                    try:
                        file_bytes = await msg.download_media(bytes)
                        upload_server = vk_user.photos.getWallUploadServer(group_id=GROUP_ID)
                        files = {'photo': ('tg_image.jpg', file_bytes, 'image/jpeg')}
                        up = requests.post(upload_server['upload_url'], files=files).json()
                        if 'photo' in up and up['photo']:
                            saved = vk_user.photos.saveWallPhoto(
                                photo=up['photo'], server=up['server'], hash=up['hash'], group_id=GROUP_ID
                            )
                            if saved:
                                photo = saved[0]
                                attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
                    except Exception as e:
                        logging.error(f"📡 Ошибка загрузки фото: {e}")
                
                pub_time = get_next_free_hour()
                try:
                    vk_user.wall.post(
                        owner_id=-GROUP_ID,
                        message=text,
                        attachments=",".join(attachments) if attachments else None,
                        from_group=1,
                        publish_date=pub_time
                    )
                    pub_str = datetime.fromtimestamp(pub_time).strftime("%d.%m %H:%M")
                    logging.info(f"📡 ТГ пост {msg_id} запланирован на {pub_str}")
                except Exception as e:
                    logging.error(f"📡 Ошибка публикации: {e}")
        
        await client.run_until_disconnected()

    with client:
        client.loop.run_until_complete(main())
