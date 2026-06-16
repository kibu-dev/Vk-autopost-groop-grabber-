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
    k.add_button("📊 Статистика", VkKeyboardColor.SECONDARY)
    k.add_button("🔙 Пользовательское меню", VkKeyboardColor.SECONDARY)
    return k

def get_donor_groups_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("📋 Список групп", VkKeyboardColor.PRIMARY)
    k.add_button("➕ Добавить группу", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("➖ Удалить группу", VkKeyboardColor.NEGATIVE)
    k.add_button("🔙 Назад", VkKeyboardColor.SECONDARY)
    return k

def get_forbidden_words_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button("📋 Список слов", VkKeyboardColor.PRIMARY)
    k.add_button("➕ Добавить слово", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("➖ Удалить слово", VkKeyboardColor.NEGATIVE)
    k.add_button("🔙 Назад", VkKeyboardColor.SECONDARY)
    return k

def get_moderation_keyboard(post_id):
    k = VkKeyboard(one_time=True)
    k.add_button(f"✅ Опубл {post_id}", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button(f"❌ Удалить {post_id}", VkKeyboardColor.NEGATIVE)
    return k

def get_pending_grab_keyboard(index):
    k = VkKeyboard(one_time=True)
    k.add_button(f"✅ Граббер {index}", VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button(f"❌ Граббер {index}", VkKeyboardColor.NEGATIVE)
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
