# keyboards.py — полностью (со счётчиком Reddit)

import json
from datetime import datetime, timedelta
from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def get_main_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("📝 Предложить пост", VkKeyboardColor.POSITIVE, payload={"cmd": "suggest_post"})
    k.add_line()
    k.add_callback_button("🗑 Удалить мой пост", VkKeyboardColor.NEGATIVE, payload={"cmd": "delete_my_post"})
    k.add_line()
    k.add_callback_button("🆘 Написать в поддержку", VkKeyboardColor.SECONDARY, payload={"cmd": "support"})
    return k


def get_posts_keyboard(posts):
    k = VkKeyboard(inline=True, one_time=False)
    for i, p in enumerate(posts[:10], 1):
        preview = (p["text"][:20] + "...") if len(p["text"]) > 20 else p["text"]
        k.add_callback_button(f"🗑 {i}. #{p['post_id']}: {preview}", VkKeyboardColor.SECONDARY, payload={"cmd": "select_post", "post_id": p['post_id'], "idx": i - 1})
        if i % 2 == 0 and i != len(posts[:10]):
            k.add_line()
    k.add_line()
    k.add_callback_button("🔙 Назад", VkKeyboardColor.PRIMARY, payload={"cmd": "back_to_main"})
    return k


def get_confirm_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("✅ Да, удалить", VkKeyboardColor.NEGATIVE, payload={"cmd": "confirm_delete"})
    k.add_callback_button("❌ Нет", VkKeyboardColor.SECONDARY, payload={"cmd": "cancel_delete"})
    return k


def get_cancel_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("🔙 Отмена", VkKeyboardColor.SECONDARY, payload={"cmd": "cancel"})
    return k


def get_admin_main_keyboard(reddit_count=0):
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("📅 Очередь постов", VkKeyboardColor.PRIMARY, payload={"cmd": "queue"})
    k.add_line()
    k.add_callback_button("👥 Группы-доноры", VkKeyboardColor.PRIMARY, payload={"cmd": "donors"})
    k.add_callback_button("🚫 Запрет-слова", VkKeyboardColor.NEGATIVE, payload={"cmd": "forbidden_words"})
    k.add_line()
    reddit_label = f"📱 Reddit (+{reddit_count})" if reddit_count > 0 else "📱 Reddit"
    k.add_callback_button(reddit_label, VkKeyboardColor.PRIMARY, payload={"cmd": "reddit"})
    k.add_callback_button("📊 Статистика", VkKeyboardColor.SECONDARY, payload={"cmd": "stats"})
    k.add_line()
    k.add_callback_button("🔮 Гороскоп", VkKeyboardColor.PRIMARY, payload={"cmd": "horoscope"})
    k.add_callback_button("🤖 AI-постер", VkKeyboardColor.SECONDARY, payload={"cmd": "ai_poster"})
    k.add_line()
    k.add_callback_button("🎉 Праздники", VkKeyboardColor.SECONDARY, payload={"cmd": "holidays"})
    k.add_callback_button("🔙 Польз. меню", VkKeyboardColor.SECONDARY, payload={"cmd": "user_menu"})
    return k


def get_reddit_post_keyboard(has_text, has_title=False):
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("⬅️ Назад", VkKeyboardColor.PRIMARY, payload={"cmd": "reddit_prev"})
    k.add_callback_button("➡️ Вперёд", VkKeyboardColor.PRIMARY, payload={"cmd": "reddit_next"})
    k.add_line()
    k.add_callback_button("✅ Опубликовать", VkKeyboardColor.POSITIVE, payload={"cmd": "reddit_publish"})
    k.add_callback_button("📷 Только фото", VkKeyboardColor.POSITIVE, payload={"cmd": "reddit_photo_only"})
    if has_text or has_title:
        k.add_line()
        k.add_callback_button("🌐 Перевести", VkKeyboardColor.PRIMARY, payload={"cmd": "reddit_translate"})
        if has_text:
            k.add_callback_button("✍️ Перефразировать", VkKeyboardColor.PRIMARY, payload={"cmd": "reddit_rewrite"})
    k.add_line()
    if has_text or has_title:
        k.add_callback_button("✏️ Править", VkKeyboardColor.PRIMARY, payload={"cmd": "reddit_edit"})
    k.add_callback_button("❌ Удалить", VkKeyboardColor.NEGATIVE, payload={"cmd": "reddit_delete"})
    k.add_line()
    k.add_callback_button("🔙 В админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_reddit_date_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    now = datetime.now()
    days = 6
    for i in range(days):
        day = now + timedelta(days=i)
        if i == 0:
            name = "Сегодня"
        elif i == 1:
            name = "Завтра"
        else:
            name = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][day.weekday()]
        date_str = day.strftime('%Y-%m-%d')
        k.add_callback_button(f"📅 {name} {day.strftime('%d.%m')}", VkKeyboardColor.PRIMARY, payload={"cmd": "pick_date", "date": date_str})
        if i % 2 == 1 and i != days - 1:
            k.add_line()
    k.add_line()
    k.add_callback_button("🔙 В админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_reddit_range_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("🌅 Утро (8-12)", VkKeyboardColor.PRIMARY, payload={"cmd": "pick_range", "start": 8, "end": 11})
    k.add_callback_button("☀️ День (12-17)", VkKeyboardColor.PRIMARY, payload={"cmd": "pick_range", "start": 12, "end": 16})
    k.add_line()
    k.add_callback_button("🌆 Вечер (17-21)", VkKeyboardColor.PRIMARY, payload={"cmd": "pick_range", "start": 17, "end": 20})
    k.add_callback_button("🌙 Ночь (21-8)", VkKeyboardColor.SECONDARY, payload={"cmd": "pick_range", "start": 21, "end": 23})
    k.add_line()
    k.add_callback_button("🔙 В админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_reddit_hour_keyboard(busy_hours, start_hour, end_hour):
    k = VkKeyboard(inline=True, one_time=False)
    busy = set(busy_hours or [])
    added = 0
    for h in range(start_hour, end_hour + 1):
        color = VkKeyboardColor.NEGATIVE if h in busy else VkKeyboardColor.SECONDARY
        hour_str = f"{h:02d}:00"
        k.add_callback_button(hour_str, color, payload={"cmd": "pick_hour", "hour": h})
        added += 1
        if added % 3 == 0 and h != end_hour:
            k.add_line()
    k.add_line()
    k.add_callback_button("⬅️ К диапазонам", VkKeyboardColor.PRIMARY, payload={"cmd": "back_to_ranges"})
    k.add_callback_button("🔙 В админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_donor_groups_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("➕ Добавить группу", VkKeyboardColor.POSITIVE, payload={"cmd": "add_donor"})
    k.add_callback_button("➖ Удалить группу", VkKeyboardColor.NEGATIVE, payload={"cmd": "remove_donor_menu"})
    k.add_line()
    k.add_callback_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_forbidden_words_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("➕ Добавить слово", VkKeyboardColor.POSITIVE, payload={"cmd": "add_word"})
    k.add_callback_button("➖ Удалить слово", VkKeyboardColor.NEGATIVE, payload={"cmd": "remove_word_menu"})
    k.add_line()
    k.add_callback_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_scheduled_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_back_admin_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("🔙 Назад в админку", VkKeyboardColor.PRIMARY, payload={"cmd": "admin_menu"})
    return k


def get_remove_donor_keyboard(donors, vk_user=None):
    k = VkKeyboard(inline=True, one_time=False)
    for i, g in enumerate(donors[:10], 1):
        try:
            from utils import get_group_name
            name = get_group_name(vk_user, g) if vk_user else str(g)
        except:
            name = str(g)
        k.add_callback_button(f"➖ {name}"[:40], VkKeyboardColor.NEGATIVE, payload={"cmd": "remove_donor", "group_id": g})
        if i % 2 == 0 and i != len(donors[:10]):
            k.add_line()
    k.add_line()
    k.add_callback_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_horoscope_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("🗑 Пересоздать", VkKeyboardColor.NEGATIVE, payload={"cmd": "horoscope_recreate"})
    k.add_line()
    k.add_callback_button("▶️ Включить", VkKeyboardColor.POSITIVE, payload={"cmd": "horoscope_enable"})
    k.add_callback_button("⏸️ Выключить", VkKeyboardColor.NEGATIVE, payload={"cmd": "horoscope_disable"})
    k.add_line()
    k.add_callback_button("🖼️ Фото", VkKeyboardColor.PRIMARY, payload={"cmd": "horoscope_photo"})
    k.add_callback_button("📋 Промт", VkKeyboardColor.PRIMARY, payload={"cmd": "horoscope_prompt"})
    k.add_line()
    k.add_callback_button("🔙 Назад", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_ai_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("✍️ Создать пост", VkKeyboardColor.POSITIVE, payload={"cmd": "ai_create"})
    k.add_line()
    k.add_callback_button("📋 Промт", VkKeyboardColor.PRIMARY, payload={"cmd": "ai_prompt"})
    k.add_line()
    k.add_callback_button("🔙 Назад", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_variants_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("✅ Опубликовать", VkKeyboardColor.POSITIVE, payload={"cmd": "ai_publish"})
    k.add_line()
    k.add_callback_button("✏️ Свой текст", VkKeyboardColor.PRIMARY, payload={"cmd": "ai_custom"})
    k.add_line()
    k.add_callback_button("🔄 Ещё вариант", VkKeyboardColor.SECONDARY, payload={"cmd": "ai_retry"})
    k.add_callback_button("❌ Отмена", VkKeyboardColor.NEGATIVE, payload={"cmd": "ai_cancel"})
    return k


def get_holidays_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("⬅️ Предыдущий", VkKeyboardColor.PRIMARY, payload={"cmd": "holiday_prev"})
    k.add_callback_button("➡️ Следующий", VkKeyboardColor.PRIMARY, payload={"cmd": "holiday_next"})
    k.add_line()
    k.add_callback_button("✍️ Создать", VkKeyboardColor.POSITIVE, payload={"cmd": "holiday_create"})
    k.add_line()
    k.add_callback_button("🔄 Обновить", VkKeyboardColor.SECONDARY, payload={"cmd": "holiday_refresh"})
    k.add_line()
    k.add_callback_button("🔙 Назад", VkKeyboardColor.SECONDARY, payload={"cmd": "admin_menu"})
    return k


def get_holiday_confirm_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button("✅ Опубликовать", VkKeyboardColor.POSITIVE, payload={"cmd": "holiday_publish"})
    k.add_line()
    k.add_callback_button("✏️ Свой текст", VkKeyboardColor.PRIMARY, payload={"cmd": "holiday_custom_text"})
    k.add_line()
    k.add_callback_button("🔄 Ещё вариант", VkKeyboardColor.SECONDARY, payload={"cmd": "holiday_retry"})
    k.add_callback_button("❌ Отмена", VkKeyboardColor.NEGATIVE, payload={"cmd": "holiday_cancel"})
    return k


def get_moderation_keyboard(post_id):
    k = VkKeyboard(inline=True, one_time=False)
    k.add_callback_button(f"✅ Опубликовать #{post_id}", VkKeyboardColor.POSITIVE, payload={"cmd": "mod_approve", "post_id": post_id})
    k.add_line()
    k.add_callback_button(f"❌ Отклонить #{post_id}", VkKeyboardColor.NEGATIVE, payload={"cmd": "mod_reject", "post_id": post_id})
    return k
