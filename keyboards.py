# keyboards.py — полностью

import json
from datetime import datetime, timedelta
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def get_main_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("📝 Предложить пост", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("🗑 Удалить мой пост", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🆘 Написать в поддержку", VkKeyboardColor.SECONDARY)
    return k

def get_posts_keyboard(posts):
    k = VkKeyboard(inline=True, one_time=False)
    for i, p in enumerate(posts[:10], 1):
        preview = (p["text"][:20] + "...") if len(p["text"]) > 20 else p["text"]
        k.add_button(f"🗑 {i}. #{p['post_id']}: {preview}", VkKeyboardColor.SECONDARY)
        if i % 2 == 0 and i != len(posts[:10]):
            k.add_line()
    k.add_line()
    k.add_button("🔙 Назад", VkKeyboardColor.PRIMARY)
    return k

def get_confirm_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("✅ Да, удалить", VkKeyboardColor.NEGATIVE)
    k.add_button("❌ Нет", VkKeyboardColor.SECONDARY)
    return k

def get_cancel_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("🔙 Отмена", VkKeyboardColor.SECONDARY)
    return k

def get_admin_main_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("📅 Очередь постов", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("👥 Группы-доноры", VkKeyboardColor.PRIMARY)
    k.add_button("🚫 Запрет-слова", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("📱 Reddit", VkKeyboardColor.PRIMARY)
    k.add_button("📊 Статистика", VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("🔮 Гороскоп", VkKeyboardColor.PRIMARY)
    k.add_button("🤖 AI-постер", VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("🎉 Праздники", VkKeyboardColor.SECONDARY)
    k.add_button("🔙 Польз. меню", VkKeyboardColor.SECONDARY)
    return k

def get_reddit_post_keyboard(has_text, has_title=False):
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("⬅️ Назад", VkKeyboardColor.PRIMARY)
    k.add_button("➡️ Вперёд", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("✅ Опубликовать", VkKeyboardColor.POSITIVE)
    k.add_button("📷 Только фото", VkKeyboardColor.POSITIVE)
    if has_text or has_title:
        k.add_line()
        k.add_button("🌐 Перевести", VkKeyboardColor.PRIMARY)
        if has_text:
            k.add_button("✍️ Перефразировать", VkKeyboardColor.PRIMARY)
    k.add_line()
    if has_text or has_title:
        k.add_button("✏️ Править", VkKeyboardColor.PRIMARY)
    k.add_button("❌ Удалить", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 В админку", VkKeyboardColor.SECONDARY)
    return k

def get_reddit_date_keyboard():
    """Инлайн-выбор даты публикации: сегодня + ближайшие дни."""
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
        k.add_button(f"📅 {name} {day.strftime('%d.%m')}", VkKeyboardColor.PRIMARY)
        if i % 2 == 1 and i != days - 1:
            k.add_line()
    k.add_line()
    k.add_button("🔙 В админку", VkKeyboardColor.SECONDARY)
    return k

def get_reddit_range_keyboard():
    """Выбор диапазона времени суток."""
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("🌅 Утро (8-12)", VkKeyboardColor.PRIMARY)
    k.add_button("☀️ День (12-17)", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🌆 Вечер (17-21)", VkKeyboardColor.PRIMARY)
    k.add_button("🌙 Ночь (21-8)", VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("🔙 В админку", VkKeyboardColor.SECONDARY)
    return k

def get_reddit_hour_keyboard(busy_hours, start_hour, end_hour):
    """Сетка часов для выбранного диапазона. Занятые — красным."""
    k = VkKeyboard(inline=True, one_time=False)
    busy = set(busy_hours or [])
    
    added = 0
    for h in range(start_hour, end_hour + 1):
        color = VkKeyboardColor.NEGATIVE if h in busy else VkKeyboardColor.SECONDARY
        hour_str = f"{h:02d}:00"
        k.add_button(hour_str, color)
        added += 1
        if added % 3 == 0 and h != end_hour:
            k.add_line()
    
    k.add_line()
    k.add_button("⬅️ К диапазонам", VkKeyboardColor.PRIMARY)
    k.add_button("🔙 В админку", VkKeyboardColor.SECONDARY)
    return k

def get_donor_groups_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("➕ Добавить группу", VkKeyboardColor.POSITIVE)
    k.add_button("➖ Удалить группу", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_forbidden_words_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("➕ Добавить слово", VkKeyboardColor.POSITIVE)
    k.add_button("➖ Удалить слово", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_scheduled_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_back_admin_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("🔙 Назад в админку", VkKeyboardColor.PRIMARY)
    return k

def get_remove_donor_keyboard(donors, vk_user=None):
    k = VkKeyboard(inline=True, one_time=False)
    for i, g in enumerate(donors[:10], 1):
        try:
            from utils import get_group_name
            name = get_group_name(vk_user, g) if vk_user else str(g)
        except:
            name = str(g)
        k.add_button(f"➖ {name}"[:40], VkKeyboardColor.NEGATIVE)
        if i % 2 == 0 and i != len(donors[:10]):
            k.add_line()
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_horoscope_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("🗑 Пересоздать", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("▶️ Включить", VkKeyboardColor.POSITIVE)
    k.add_button("⏸️ Выключить", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🖼️ Фото", VkKeyboardColor.PRIMARY)
    k.add_button("📋 Промт", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔙 Назад", VkKeyboardColor.SECONDARY)
    return k

def get_ai_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("✍️ Создать пост", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("📋 Промт", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔙 Назад", VkKeyboardColor.SECONDARY)
    return k

def get_variants_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("✅ Опубликовать", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("✏️ Свой текст", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔄 Ещё вариант", VkKeyboardColor.SECONDARY)
    k.add_button("❌ Отмена", VkKeyboardColor.NEGATIVE)
    return k

def get_holidays_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("⬅️ Предыдущий", VkKeyboardColor.PRIMARY)
    k.add_button("➡️ Следующий", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("✍️ Создать", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("🔄 Обновить", VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("🔙 Назад", VkKeyboardColor.SECONDARY)
    return k

def get_holiday_confirm_keyboard():
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button("✅ Опубликовать", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("✏️ Свой текст", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔄 Ещё вариант", VkKeyboardColor.SECONDARY)
    k.add_button("❌ Отмена", VkKeyboardColor.NEGATIVE)
    return k

def get_moderation_keyboard(post_id):
    """Клавиатура для модерации подозрительных постов."""
    k = VkKeyboard(inline=True, one_time=False)
    k.add_button(f"✅ Опубликовать #{post_id}", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button(f"❌ Отклонить #{post_id}", VkKeyboardColor.NEGATIVE)
    return k
