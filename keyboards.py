from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# ─── Пользовательские ───

def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🗑 Удалить мой пост", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("🆘 Написать в поддержку", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_posts_keyboard(posts):
    keyboard = VkKeyboard(one_time=True)
    for i, post in enumerate(posts[:10], 1):
        preview = post["text"][:20] + "..." if len(post["text"]) > 20 else post["text"]
        keyboard.add_button(f"🗑 {i}. Пост #{post['post_id']}: {preview}", color=VkKeyboardColor.SECONDARY)
        if i % 2 == 0 and i != len(posts[:10]):
            keyboard.add_line()
    keyboard.add_line()
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.PRIMARY)
    return keyboard

def get_confirm_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("✅ Да, удалить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("❌ Нет", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_cancel_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🔙 Отмена", color=VkKeyboardColor.SECONDARY)
    return keyboard

# ─── Админские ───

def get_admin_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📢 Модерация", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("👥 Группы-доноры", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🚫 Запрет-слова", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("📊 Статистика", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🔙 Пользовательское меню", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_donor_groups_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📋 Список групп", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("➕ Добавить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("➖ Удалить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_forbidden_words_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📋 Список слов", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("➕ Добавить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("➖ Удалить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_moderation_keyboard(post_id):
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button(f"✅ Опубл {post_id}", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button(f"❌ Удалить {post_id}", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button(f"⏭ Пропустить {post_id}", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_back_admin_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🔙 Назад в админку", color=VkKeyboardColor.PRIMARY)
    return keyboard
