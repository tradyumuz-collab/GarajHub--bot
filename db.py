# db.py - SQLite versiya
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
import calendar
from werkzeug.security import generate_password_hash

DB_PATH = 'garajhub.db'

def get_connection():
    """Database connectionini olish"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Ma'lumotlar bazasini yaratish"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # USERS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            gender TEXT,
            birth_date TEXT,
            specialization TEXT,
            experience TEXT,
            bio TEXT,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # STARTUPS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS startups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            logo TEXT,
            group_link TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            required_skills TEXT,
            category TEXT DEFAULT 'Boshqa',
            max_members INTEGER DEFAULT 10,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            results TEXT,
            channel_post_id INTEGER,
            current_members INTEGER DEFAULT 0,
            FOREIGN KEY (owner_id) REFERENCES users(user_id)
        )
    ''')
    
    # STARTUP_MEMBERS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS startup_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            startup_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (startup_id) REFERENCES startups(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # PRO SETTINGS jadvali (1 ta satr)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pro_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            pro_enabled INTEGER DEFAULT 1,
            pro_price INTEGER DEFAULT 100000,
            card_number TEXT DEFAULT ''
        )
    ''')

    # PRO SUBSCRIPTIONS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pro_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            source TEXT DEFAULT 'payment',
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # PRO PAYMENTS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pro_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            card_number TEXT NOT NULL,
            receipt_file_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # REFERRALS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            invited_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TEXT,
            FOREIGN KEY (inviter_id) REFERENCES users(user_id),
            FOREIGN KEY (invited_id) REFERENCES users(user_id)
        )
    ''')

    # REFERRAL REWARDS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            months INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (inviter_id) REFERENCES users(user_id)
        )
    ''')

    # Default pro settings
    cursor.execute('''
        INSERT OR IGNORE INTO pro_settings (id, pro_enabled, pro_price, card_number)
        VALUES (1, 1, 100000, '')
    ''')

    # ADMINS jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            role TEXT DEFAULT 'admin',
            last_login TEXT
        )
    ''')

    # APP SETTINGS jadvali (1 ta satr)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            site_name TEXT DEFAULT 'GarajHub',
            admin_email TEXT DEFAULT 'admin@garajhub.uz',
            timezone TEXT DEFAULT 'Asia/Tashkent'
        )
    ''')
    cursor.execute('''
        INSERT OR IGNORE INTO app_settings (id, site_name, admin_email, timezone)
        VALUES (1, 'GarajHub', 'admin@garajhub.uz', 'Asia/Tashkent')
    ''')

    # Default adminlar
    cursor.execute('''
        INSERT OR IGNORE INTO admins (username, password_hash, full_name, email, role)
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin', generate_password_hash('admin123'), 'Super Admin', 'admin@garajhub.uz', 'superadmin'))
    cursor.execute('''
        INSERT OR IGNORE INTO admins (username, password_hash, full_name, email, role)
        VALUES (?, ?, ?, ?, ?)
    ''', ('moderator', generate_password_hash('moderator123'), 'Moderator', 'moderator@garajhub.uz', 'moderator'))

    # Existing DB migrate: add missing columns for pro_payments
    try:
        cursor.execute("PRAGMA table_info(pro_payments)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'card_number' not in cols:
            cursor.execute("ALTER TABLE pro_payments ADD COLUMN card_number TEXT DEFAULT ''")
        if 'receipt_file_id' not in cols:
            cursor.execute("ALTER TABLE pro_payments ADD COLUMN receipt_file_id TEXT DEFAULT ''")
    except Exception:
        pass
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# ======================== PRO SETTINGS FUNCTIONS ========================

def get_pro_settings() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT pro_enabled, pro_price, card_number FROM pro_settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'pro_enabled': int(row['pro_enabled']),
            'pro_price': int(row['pro_price']),
            'card_number': row['card_number'] or ''
        }
    return {'pro_enabled': 0, 'pro_price': 0, 'card_number': ''}

def set_pro_enabled(enabled: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE pro_settings SET pro_enabled = ? WHERE id = 1', (1 if enabled else 0,))
    conn.commit()
    conn.close()

def set_pro_price(price: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE pro_settings SET pro_price = ? WHERE id = 1', (int(price),))
    conn.commit()
    conn.close()

def set_pro_card(card_number: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE pro_settings SET card_number = ? WHERE id = 1', (card_number,))
    conn.commit()
    conn.close()

def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)

def _expire_old_subscriptions():
    now_iso = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pro_subscriptions
        SET status = 'expired'
        WHERE status = 'active' AND end_at <= ?
    ''', (now_iso,))
    conn.commit()
    conn.close()

def get_active_pro_subscription(user_id: int) -> Optional[Dict]:
    _expire_old_subscriptions()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM pro_subscriptions
        WHERE user_id = ? AND status = 'active'
        ORDER BY end_at DESC LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def is_user_pro(user_id: int) -> bool:
    return get_active_pro_subscription(user_id) is not None

def add_pro_subscription(user_id: int, months: int = 1, source: str = 'payment', note: str = '') -> Dict:
    _expire_old_subscriptions()
    now = datetime.now()
    active = get_active_pro_subscription(user_id)
    if active and active.get('end_at'):
        try:
            start_base = datetime.fromisoformat(active['end_at'])
        except Exception:
            start_base = now
    else:
        start_base = now

    start_at = start_base if start_base > now else now
    end_at = _add_months(start_at, months)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pro_subscriptions (user_id, start_at, end_at, status, source, note)
        VALUES (?, ?, ?, 'active', ?, ?)
    ''', (user_id, start_at.isoformat(), end_at.isoformat(), source, note))
    conn.commit()
    sub_id = cursor.lastrowid
    conn.close()

    return {
        'id': sub_id,
        'user_id': user_id,
        'start_at': start_at.isoformat(),
        'end_at': end_at.isoformat(),
        'status': 'active',
        'source': source,
        'note': note
    }

# ======================== PRO PAYMENTS FUNCTIONS ========================

def create_pro_payment(user_id: int, amount: int, card_number: str, receipt_file_id: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pro_payments (user_id, amount, card_number, receipt_file_id, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (user_id, int(amount), card_number, receipt_file_id))
    conn.commit()
    payment_id = cursor.lastrowid
    conn.close()
    return int(payment_id)

def get_payment(payment_id: int) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pro_payments WHERE id = ?', (int(payment_id),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_pending_payments(limit: int = 20) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM pro_payments
        WHERE status = 'pending'
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_payment_status(payment_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE pro_payments SET status = ? WHERE id = ?', (status, int(payment_id)))
    conn.commit()
    conn.close()

# ======================== REFERRAL FUNCTIONS ========================

def register_referral(inviter_id: int, invited_id: int) -> bool:
    if inviter_id == invited_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM referrals WHERE invited_id = ?', (invited_id,))
    exists = cursor.fetchone()
    if exists:
        conn.close()
        return False
    cursor.execute('''
        INSERT INTO referrals (inviter_id, invited_id, status)
        VALUES (?, ?, 'pending')
    ''', (inviter_id, invited_id))
    conn.commit()
    conn.close()
    return True

def confirm_referral(invited_id: int) -> Optional[int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT inviter_id, status FROM referrals WHERE invited_id = ?
    ''', (invited_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    if row['status'] != 'confirmed':
        cursor.execute('''
            UPDATE referrals
            SET status = 'confirmed', confirmed_at = ?
            WHERE invited_id = ?
        ''', (datetime.now().isoformat(), invited_id))
        conn.commit()
    inviter_id = row['inviter_id']
    conn.close()
    return inviter_id

def get_confirmed_referral_count(inviter_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) as count FROM referrals
        WHERE inviter_id = ? AND status = 'confirmed'
    ''', (inviter_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row['count']) if row else 0

def get_referral_reward_count(inviter_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) as count FROM referral_rewards WHERE inviter_id = ?
    ''', (inviter_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row['count']) if row else 0

def add_referral_reward(inviter_id: int, months: int = 1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO referral_rewards (inviter_id, months)
        VALUES (?, ?)
    ''', (inviter_id, int(months)))
    conn.commit()
    conn.close()

def get_user_startup_count(owner_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM startups WHERE owner_id = ?', (owner_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row['count']) if row else 0

# ======================== USER FUNCTIONS ========================

def get_user(user_id: int) -> Optional[Dict]:
    """Foydalanuvchini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def save_user(user_id: int, username: str, first_name: str):
    """Yangi foydalanuvchini saqlash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    
    conn.commit()
    conn.close()

def update_user_field(user_id: int, field: str, value):
    """Foydalanuvchi maydonini yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = f'UPDATE users SET {field} = ? WHERE user_id = ?'
    cursor.execute(query, (value, user_id))
    
    conn.commit()
    conn.close()

def update_user_specialization(user_id: int, specialization: str):
    """Mutaxassislikni yangilash"""
    update_user_field(user_id, 'specialization', specialization)

def update_user_experience(user_id: int, experience: str):
    """Tajribani yangilash"""
    update_user_field(user_id, 'experience', experience)

def get_all_users() -> List[int]:
    """Barcha foydalanuvchilar ID larini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    rows = cursor.fetchall()
    conn.close()
    
    return [row['user_id'] for row in rows]

def get_recent_users(limit: int = 10) -> List[Dict]:
    """So'nggi foydalanuvchilarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY joined_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# ======================== STARTUP FUNCTIONS ========================

def create_startup(name: str, description: str, logo: Optional[str], 
                   group_link: str, owner_id: int, required_skills: str = "",
                   category: str = "Boshqa", max_members: int = 10) -> Optional[str]:
    """Yangi startup yaratish"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO startups (name, description, logo, group_link, owner_id, 
                            required_skills, category, max_members)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, description, logo, group_link, owner_id, required_skills, category, max_members))
    
    startup_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return str(startup_id)

def get_startup(startup_id: str) -> Optional[Dict]:
    """Startupni ID bo'yicha olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM startups WHERE id = ?', (int(startup_id),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        result = dict(row)
        result['_id'] = str(result['id'])
        return result
    return None

def get_startups_by_owner(owner_id: int) -> List[Dict]:
    """Egaga tegishli startaplarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM startups WHERE owner_id = ? ORDER BY created_at DESC', (owner_id,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    return result

def get_pending_startups(page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    """Kutilayotgan startaplarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    
    offset = (page - 1) * per_page
    
    cursor.execute('SELECT COUNT(*) as count FROM startups WHERE status = ?', ('pending',))
    total = cursor.fetchone()['count']
    
    cursor.execute('''
        SELECT * FROM startups WHERE status = ? 
        ORDER BY created_at DESC LIMIT ? OFFSET ?
    ''', ('pending', per_page, offset))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    
    return result, total

def get_active_startups(page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    """Faol startaplarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    
    offset = (page - 1) * per_page
    
    cursor.execute('SELECT COUNT(*) as count FROM startups WHERE status = ?', ('active',))
    total = cursor.fetchone()['count']
    
    cursor.execute('''
        SELECT * FROM startups WHERE status = ? 
        ORDER BY created_at DESC LIMIT ? OFFSET ?
    ''', ('active', per_page, offset))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    
    return result, total

def get_completed_startups() -> List[Dict]:
    """Yakunlangan startaplarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM startups WHERE status = ? ORDER BY created_at DESC', ('completed',))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    return result

def get_rejected_startups() -> List[Dict]:
    """Rad etilgan startaplarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM startups WHERE status = ? ORDER BY created_at DESC', ('rejected',))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    return result

def get_recent_startups(limit: int = 10) -> List[Dict]:
    """So'nggi startaplarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM startups ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    return result

def update_startup_status(startup_id: str, status: str):
    """Startup holatini yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    started_at = datetime.now().isoformat() if status == 'active' else None
    
    if started_at:
        cursor.execute('''
            UPDATE startups SET status = ?, started_at = ? WHERE id = ?
        ''', (status, started_at, int(startup_id)))
    else:
        cursor.execute('''
            UPDATE startups SET status = ? WHERE id = ?
        ''', (status, int(startup_id)))
    
    conn.commit()
    conn.close()

def update_startup_results(startup_id: str, results: str, completed_at: datetime):
    """Startup natijalarini yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE startups SET results = ? WHERE id = ?
    ''', (results, int(startup_id)))
    
    conn.commit()
    conn.close()

def update_startup_post_id(startup_id: str, post_id: int):
    """Kanal post ID sini saqlash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE startups SET channel_post_id = ? WHERE id = ?
    ''', (post_id, int(startup_id)))
    
    conn.commit()
    conn.close()

def get_startup_by_post_id(post_id: int) -> Optional[Dict]:
    """Post ID bo'yicha startupni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM startups WHERE channel_post_id = ?', (post_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        result = dict(row)
        result['_id'] = str(result['id'])
        return result
    return None

def update_startup_current_members(startup_id: str, count: int):
    """A'zolar sonini yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE startups SET current_members = ? WHERE id = ?
    ''', (count, int(startup_id)))
    
    conn.commit()
    conn.close()

def get_startups_by_category(category: str) -> List[Dict]:
    """Kategoriya bo'yicha startaplarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM startups WHERE category = ? AND status = 'active'
        ORDER BY created_at DESC
    ''', (category,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    return result

def get_all_categories() -> List[str]:
    """Barcha kategoriyalarni olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT category FROM startups WHERE status = "active"')
    rows = cursor.fetchall()
    conn.close()
    
    return [row['category'] for row in rows]

def get_startups_by_ids(startup_ids: List[int]) -> List[Dict]:
    """ID lar bo'yicha startaplarni olish"""
    if not startup_ids:
        return []
    
    conn = get_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(startup_ids))
    cursor.execute(f'SELECT * FROM startups WHERE id IN ({placeholders})', startup_ids)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        startup = dict(row)
        startup['_id'] = str(startup['id'])
        result.append(startup)
    return result

# ======================== STARTUP MEMBERS FUNCTIONS ========================

def add_startup_member(startup_id: str, user_id: int):
    """Startupga a'zo qo'shish so'rovi"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO startup_members (startup_id, user_id, status)
        VALUES (?, ?, 'pending')
    ''', (int(startup_id), user_id))
    
    conn.commit()
    conn.close()

def get_join_request_id(startup_id: str, user_id: int) -> Optional[str]:
    """Qo'shilish so'rovi ID sini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM startup_members 
        WHERE startup_id = ? AND user_id = ?
        ORDER BY joined_at DESC LIMIT 1
    ''', (int(startup_id), user_id))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return str(row['id'])
    return None

def get_join_request(request_id: str) -> Optional[Dict]:
    """So'rov ma'lumotlarini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM startup_members WHERE id = ?', (int(request_id),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def update_join_request(request_id: str, status: str):
    """Qo'shilish so'rovini yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE startup_members SET status = ? WHERE id = ?
    ''', (status, int(request_id)))
    
    conn.commit()
    conn.close()

def get_startup_members(startup_id: str, page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    """Startup a'zolarini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    
    offset = (page - 1) * per_page
    
    cursor.execute('''
        SELECT COUNT(*) as count FROM startup_members 
        WHERE startup_id = ? AND status = 'accepted'
    ''', (int(startup_id),))
    total = cursor.fetchone()['count']
    
    cursor.execute('''
        SELECT u.* FROM users u
        JOIN startup_members sm ON u.user_id = sm.user_id
        WHERE sm.startup_id = ? AND sm.status = 'accepted'
        ORDER BY sm.joined_at DESC
        LIMIT ? OFFSET ?
    ''', (int(startup_id), per_page, offset))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows], total

def get_all_startup_members(startup_id: str) -> List[int]:
    """Barcha startup a'zolarining ID larini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id FROM startup_members 
        WHERE startup_id = ? AND status = 'accepted'
    ''', (int(startup_id),))
    rows = cursor.fetchall()
    conn.close()
    
    return [row['user_id'] for row in rows]

def get_startup_member_count(startup_id: str) -> int:
    """Startup a'zolari sonini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) as count FROM startup_members 
        WHERE startup_id = ? AND status = 'accepted'
    ''', (int(startup_id),))
    row = cursor.fetchone()
    conn.close()
    
    return row['count']

def update_startup_member_count(startup_id: str):
    """A'zolar sonini hisoblash va yangilash"""
    count = get_startup_member_count(startup_id)
    update_startup_current_members(startup_id, count)

def get_user_joined_startups(user_id: int) -> List[int]:
    """Foydalanuvchi qo'shilgan startaplar ID larini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT startup_id FROM startup_members 
        WHERE user_id = ? AND status = 'accepted'
        ORDER BY joined_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [row['startup_id'] for row in rows]

# ======================== STATISTICS FUNCTIONS ========================

def get_statistics() -> Dict:
    """Statistikani olish"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as count FROM users')
    total_users = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM startups')
    total_startups = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM startups WHERE status = ?', ('pending',))
    pending_startups = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM startups WHERE status = ?', ('active',))
    active_startups = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM startups WHERE status = ?', ('completed',))
    completed_startups = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM startups WHERE status = ?', ('rejected',))
    rejected_startups = cursor.fetchone()['count']
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_startups': total_startups,
        'pending_startups': pending_startups,
        'active_startups': active_startups,
        'completed_startups': completed_startups,
        'rejected_startups': rejected_startups
    }

# ======================== SETTINGS FUNCTIONS ========================

def get_app_settings() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT site_name, admin_email, timezone FROM app_settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'site_name': row['site_name'],
            'admin_email': row['admin_email'],
            'timezone': row['timezone']
        }
    return {
        'site_name': 'GarajHub',
        'admin_email': 'admin@garajhub.uz',
        'timezone': 'Asia/Tashkent'
    }

def update_app_settings(site_name: str, admin_email: str, timezone: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE app_settings
        SET site_name = ?, admin_email = ?, timezone = ?
        WHERE id = 1
    ''', (site_name, admin_email, timezone))
    conn.commit()
    conn.close()

# ======================== ADMIN FUNCTIONS ========================

def get_admin_by_username(username: str) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admins WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_admin_by_id(admin_id: int) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admins WHERE id = ?', (admin_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_admins() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admins ORDER BY id ASC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_admin(username: str, password_hash: str, full_name: str, email: str, role: str) -> Optional[int]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO admins (username, password_hash, full_name, email, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, password_hash, full_name, email, role))
        admin_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return admin_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def delete_admin(admin_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM admins WHERE id = ?', (admin_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def update_admin_last_login(admin_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE admins SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), admin_id))
    conn.commit()
    conn.close()


# Bu qo'shimcha constantalar - MongoDB versiyasida bo'lgan
USERS_COLLECTION = 'users'
STARTUPS_COLLECTION = 'startups'
STARTUP_MEMBERS_COLLECTION = 'startup_members'

# MongoDB versiyasidan qolgan funksiyalar uchun
class FakeDB:
    """MongoDB db obyektini SQLite uchun fake qilish"""
    pass

db = FakeDB()
