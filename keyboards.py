from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def get_main_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("🗑 Удалить мой пост", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🆘 Написать в поддержку", VkKeyboardColor.SECONDARY)
    return k

def get_posts_keyboard(posts):
    k = VkKeyboard(one_time=True)
    for i, p in enumerate(posts[:10], 1):
        preview = (p["text"][:20] + "...") if len(p["text"]) > 20 else p["text"]
        k.add_button(f"🗑 {i}. #{p['post_id']}: {preview}", VkKeyboardColor.SECONDARY)
        if i % 2 == 0 and i != len(posts[:10]): k.add_line()
    k.add_line(); k.add_button("🔙 Назад", VkKeyboardColor.PRIMARY)
    return k

def get_confirm_keyboard():
    k = VkKeyboard(one_time=True)
    k.add_button("✅ Да, удалить", VkKeyboardColor.NEGATIVE)
    k.add_button("❌ Нет", VkKeyboardColor.SECONDARY)
    return k

def get_cancel_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("🔙 Отмена", VkKeyboardColor.SECONDARY)
    return k

def get_admin_main_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("📢 Модерация", VkKeyboardColor.PRIMARY)
    k.add_button("📅 Очередь постов", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("👥 Группы-доноры", VkKeyboardColor.PRIMARY)
    k.add_button("🚫 Запрет-слова", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("📱 Reddit", VkKeyboardColor.PRIMARY)
    k.add_button("📊 Статистика", VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("⚙️ Автоматизация", VkKeyboardColor.SECONDARY)
    k.add_button("🤖 AI-постер", VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("🎉 Праздники", VkKeyboardColor.SECONDARY)
    k.add_button("🔙 Польз. меню", VkKeyboardColor.SECONDARY)
    return k

def get_reddit_post_keyboard(has_text):
    k = VkKeyboard(one_time=False)
    k.add_button("⬅️ Предыдущий", VkKeyboardColor.PRIMARY)
    k.add_button("➡️ Следующий", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("✅ В очередь", VkKeyboardColor.POSITIVE)
    k.add_button("📷 Только фото", VkKeyboardColor.POSITIVE)
    k.add_line()
    if has_text:
        k.add_button("🤖 ИИ перевод", VkKeyboardColor.PRIMARY)
        k.add_line()
        k.add_button("🔄 ИИ рерайт", VkKeyboardColor.PRIMARY)
        k.add_line()
        k.add_button("✏️ Редактировать", VkKeyboardColor.PRIMARY)
        k.add_line()
    k.add_button("❌ Удалить", VkKeyboardColor.NEGATIVE)
    k.add_button("🗑 Очистить всё", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_donor_groups_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("➕ Добавить группу", VkKeyboardColor.POSITIVE)
    k.add_button("➖ Удалить группу", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_forbidden_words_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("➕ Добавить слово", VkKeyboardColor.POSITIVE)
    k.add_button("➖ Удалить слово", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_moderation_keyboard(post_id):
    k = VkKeyboard(one_time=True)
    k.add_button(f"✅ Опубл {post_id}", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button(f"❌ Удалить {post_id}", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_pending_grab_keyboard(index):
    k = VkKeyboard(one_time=True)
    k.add_button(f"✅ Граббер {index}", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button(f"❌ Граббер {index}", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_scheduled_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_back_admin_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("🔙 Назад в админку", VkKeyboardColor.PRIMARY)
    return k

def get_remove_donor_keyboard(donors, vk_user=None):
    k = VkKeyboard(one_time=True)
    for i, g in enumerate(donors[:10], 1):
        try:
            from utils import get_group_name
            name = get_group_name(vk_user, g) if vk_user else str(g)
        except: name = str(g)
        k.add_button(f"➖ {name}"[:40], VkKeyboardColor.NEGATIVE)
        if i % 2 == 0 and i != len(donors[:10]): k.add_line()
    k.add_line(); k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_automation_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("❤️ Автолайкер", VkKeyboardColor.PRIMARY)
    k.add_button("🟢 Вечный онлайн", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🤝 Приём друзей", VkKeyboardColor.PRIMARY)
    k.add_button("👥 Приём в группу", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔮 Гороскоп", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_liker_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("▶️ Включить лайкер", VkKeyboardColor.POSITIVE)
    k.add_button("⏸️ Выключить лайкер", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("📋 Лайк группы", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("➕ Лайк группу", VkKeyboardColor.POSITIVE)
    k.add_button("➖ Лайк группу", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("📊 Лайк стата", VkKeyboardColor.SECONDARY)
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_remove_liker_keyboard(groups, vk_user=None):
    k = VkKeyboard(one_time=True)
    for i, g in enumerate(groups[:10], 1):
        try:
            from utils import get_group_name
            name = get_group_name(vk_user, g) if vk_user else str(g)
        except: name = str(g)
        k.add_button(f"❤➖ {name}"[:40], VkKeyboardColor.NEGATIVE)
        if i % 2 == 0 and i != len(groups[:10]): k.add_line()
    k.add_line(); k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_online_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("▶️ Включить онлайн", VkKeyboardColor.POSITIVE)
    k.add_button("⏸️ Выключить онлайн", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_friend_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("▶️ Включить друзей", VkKeyboardColor.POSITIVE)
    k.add_button("⏸️ Выключить друзей", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_group_accept_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("▶️ Включить группу", VkKeyboardColor.POSITIVE)
    k.add_button("⏸️ Выключить группу", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_horoscope_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("Удалить и пересоздать", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("▶️ Включить гороскоп", VkKeyboardColor.POSITIVE)
    k.add_button("⏸️ Выключить гороскоп", VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button("🖼️ Сменить фото", VkKeyboardColor.PRIMARY)
    k.add_button("📋 Промт гороскопа", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_ai_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("✍️ Создать пост", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("📋 Промт", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_variants_keyboard():
    k = VkKeyboard(one_time=True)
    k.add_button("✅ Опубликовать", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("✏️ Свой текст", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔄 Ещё вариант", VkKeyboardColor.SECONDARY)
    k.add_button("❌ Отмена", VkKeyboardColor.NEGATIVE)
    return k

def get_attach_keyboard():
    k = VkKeyboard(one_time=True)
    k.add_button("📷 Да, прикрепить", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("✅ Нет, опубликовать", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("❌ Отмена", VkKeyboardColor.NEGATIVE)
    return k

def get_holidays_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("⬅️ Предыдущий", VkKeyboardColor.PRIMARY)
    k.add_button("➡️ Следующий", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("✍️ Создать поздравление", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("🔄 Обновить список", VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("🔙 Назад в админку", VkKeyboardColor.SECONDARY)
    return k

def get_holiday_confirm_keyboard():
    k = VkKeyboard(one_time=True)
    k.add_button("✅ Опубликовать (праздник)", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("✏️ Написать свой текст", VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("🔄 Сгенерировать ещё", VkKeyboardColor.SECONDARY)
    k.add_button("❌ Отмена", VkKeyboardColor.NEGATIVE)
    return k
