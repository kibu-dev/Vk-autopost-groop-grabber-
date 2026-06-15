elif t == "📊 статистика":
    s = get_stats()
    msg = (
        f"📊 Статистика:\n"
        f"• Опубликовано: {s['total_published']}\n"
        f"• В предложке: {s['pending_suggests']}\n"
        f"• Взято граббером: {s['total_grabbed']}\n"
        f"• На модерации: {s['pending_moderation']}\n"
        f"• Доноров: {s['donor_count']}\n"
        f"• До публ: {s['next_publish']}\n"
        f"• До граббера: {s['next_grab']}"
    )
    send_message(vk, user_id, msg, get_admin_main_keyboard())
