import sqlite3
from datetime import datetime, timedelta

DB_PATH = "posts.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_posts (
            post_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            published_date TEXT,
            text TEXT,
            is_deleted BOOLEAN DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS grab_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_group_id INTEGER,
            donor_post_id INTEGER,
            text TEXT,
            attachments TEXT,
            grabbed_at TEXT,
            published BOOLEAN DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS grab_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_group_id INTEGER,
            donor_post_id INTEGER,
            grabbed_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS donor_groups (
            group_id INTEGER PRIMARY KEY,
            added_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS forbidden_words (
            word TEXT PRIMARY KEY,
            added_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS moderation_queue (
            post_id INTEGER PRIMARY KEY,
            post_type TEXT,
            user_id INTEGER,
            text TEXT,
            attachments TEXT,
            reason TEXT,
            created_at TEXT
        );
    """)
    conn.commit()
    conn.close()

# ─── Пользовательские посты ───

def add_user_post(user_id, post_id, text):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO user_posts (post_id, user_id, published_date, text) VALUES (?, ?, ?, ?)",
        (post_id, user_id, datetime.now().isoformat(), text[:500])
    )
    conn.commit()
    conn.close()

def get_user_posts(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    posts = conn.execute(
        "SELECT post_id, published_date, text FROM user_posts WHERE user_id = ? AND is_deleted = 0 ORDER BY published_date DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(p) for p in posts]

def delete_user_post(user_id, post_id):
    conn = sqlite3.connect(DB_PATH)
    post = conn.execute("SELECT * FROM user_posts WHERE post_id = ? AND user_id = ?", (post_id, user_id)).fetchone()
    if post:
        conn.execute("UPDATE user_posts SET is_deleted = 1 WHERE post_id = ?", (post_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_post_author(post_id):
    conn = sqlite3.connect(DB_PATH)
    post = conn.execute("SELECT user_id FROM user_posts WHERE post_id = ?", (post_id,)).fetchone()
    conn.close()
    return post[0] if post else None

# ─── Очередь граббера ───

def add_to_grab_queue(donor_group_id, donor_post_id, text, attachments):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO grab_queue (donor_group_id, donor_post_id, text, attachments, grabbed_at) VALUES (?, ?, ?, ?, ?)",
        (donor_group_id, donor_post_id, text, attachments, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_next_grab_post():
    """Берёт первый неопубликованный пост из очереди"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    post = conn.execute(
        "SELECT * FROM grab_queue WHERE published = 0 ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(post) if post else None

def mark_grab_published(queue_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE grab_queue SET published = 1 WHERE id = ?", (queue_id,))
    conn.commit()
    conn.close()

def is_post_grabbed(donor_group_id, donor_post_id):
    conn = sqlite3.connect(DB_PATH)
    exists = conn.execute(
        "SELECT 1 FROM grab_history WHERE donor_group_id = ? AND donor_post_id = ?",
        (donor_group_id, donor_post_id)
    ).fetchone()
    conn.close()
    return exists is not None

def add_to_grab_history(donor_group_id, donor_post_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO grab_history (donor_group_id, donor_post_id, grabbed_at) VALUES (?, ?, ?)",
        (donor_group_id, donor_post_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def count_today_grabs_from_group(donor_group_id):
    """Сколько постов взято с этой группы за сегодня"""
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    count = conn.execute(
        "SELECT COUNT(*) FROM grab_history WHERE donor_group_id = ? AND grabbed_at LIKE ?",
        (donor_group_id, f"{today}%")
    ).fetchone()[0]
    conn.close()
    return count

def get_grab_queue_count():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM grab_queue WHERE published = 0").fetchone()[0]
    conn.close()
    return count

# ─── Группы-доноры ───

def add_donor_group(group_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO donor_groups (group_id, added_at) VALUES (?, ?)",
        (group_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def remove_donor_group(group_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM donor_groups WHERE group_id = ?", (group_id,))
    conn.commit()
    conn.close()

def get_donor_groups():
    conn = sqlite3.connect(DB_PATH)
    groups = conn.execute("SELECT group_id FROM donor_groups").fetchall()
    conn.close()
    return [g[0] for g in groups]

# ─── Запрещённые слова ───

def add_forbidden_word(word):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO forbidden_words (word, added_at) VALUES (?, ?)",
        (word.lower(), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def remove_forbidden_word(word):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM forbidden_words WHERE word = ?", (word.lower(),))
    conn.commit()
    conn.close()

def get_forbidden_words():
    conn = sqlite3.connect(DB_PATH)
    words = conn.execute("SELECT word FROM forbidden_words").fetchall()
    conn.close()
    return [w[0] for w in words]

# ─── Очередь модерации ───

def add_to_moderation(post_id, post_type, user_id, text, attachments, reason):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO moderation_queue (post_id, post_type, user_id, text, attachments, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (post_id, post_type, user_id, text, attachments, reason, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_moderation_posts():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    posts = conn.execute("SELECT * FROM moderation_queue ORDER BY created_at DESC LIMIT 10").fetchall()
    conn.close()
    return [dict(p) for p in posts]

def remove_from_moderation(post_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM moderation_queue WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()

# ─── Статистика ───

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    total_user_posts = conn.execute("SELECT COUNT(*) FROM user_posts WHERE is_deleted = 0").fetchone()[0]
    total_grab_posts = conn.execute("SELECT COUNT(*) FROM grab_queue WHERE published = 1").fetchone()[0]
    pending_grab = conn.execute("SELECT COUNT(*) FROM grab_queue WHERE published = 0").fetchone()[0]
    pending_moderation = conn.execute("SELECT COUNT(*) FROM moderation_queue").fetchone()[0]
    donor_count = conn.execute("SELECT COUNT(*) FROM donor_groups").fetchone()[0]
    conn.close()
    return {
        "total_user_posts": total_user_posts,
        "total_grab_posts": total_grab_posts,
        "pending_grab": pending_grab,
        "pending_moderation": pending_moderation,
        "donor_count": donor_count
    }

# ─── Миграция слов из JSON ───

def migrate_forbidden_words_from_json():
    """Переносит слова из forbidden_words.json в БД (однократно)"""
    import json
    try:
        with open("forbidden_words.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            for word in data.get("words", []):
                add_forbidden_word(word)
        print("✅ Слова перенесены из JSON в БД")
    except:
        pass
