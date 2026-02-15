# db.py - MongoDB version
import calendar
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()


def _ensure_utf8_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


_ensure_utf8_stdio()

def _env_str(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        cleaned = str(value).strip().strip("'").strip('"')
        if cleaned:
            return cleaned
    return default


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name, default=str(default))
    try:
        return int(raw)
    except Exception:
        return default


MONGODB_URI = _env_str("MONGODB_URI", "MONGO_URL", "DATABASE_URL", default="mongodb://127.0.0.1:27017")
MONGODB_DB_NAME = _env_str("MONGODB_DB_NAME", default="garajhub")
MONGODB_TIMEOUT_MS = _env_int("MONGODB_TIMEOUT_MS", 5000)
MONGO_AUTO_MIGRATE = _env_str("MONGO_AUTO_MIGRATE", default="1") == "1"
SQLITE_MIGRATION_PATH = _env_str("SQLITE_MIGRATION_PATH", default="garajhub.db")

USERS_COLLECTION = "users"
STARTUPS_COLLECTION = "startups"
STARTUP_MEMBERS_COLLECTION = "startup_members"

_mongo_client: Optional[MongoClient] = None
_db: Optional[Database] = None

_COUNTER_CONFIG: Dict[str, Tuple[str, str]] = {
    "startups": (STARTUPS_COLLECTION, "id"),
    "startup_members": (STARTUP_MEMBERS_COLLECTION, "id"),
    "pro_subscriptions": ("pro_subscriptions", "id"),
    "pro_payments": ("pro_payments", "id"),
    "referrals": ("referrals", "id"),
    "referral_rewards": ("referral_rewards", "id"),
    "admins": ("admins", "id"),
}

_ALLOWED_USER_FIELDS = {
    "username",
    "first_name",
    "last_name",
    "phone",
    "gender",
    "birth_date",
    "specialization",
    "experience",
    "bio",
    "joined_at",
}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _to_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def _without_mongo_id(doc: Optional[Dict]) -> Optional[Dict]:
    if not doc:
        return None
    result = dict(doc)
    result.pop("_id", None)
    return result


def _normalize_startup(doc: Optional[Dict]) -> Optional[Dict]:
    data = _without_mongo_id(doc)
    if not data:
        return None
    startup_id = _to_int(data.get("id"), None)
    if startup_id is None and doc is not None:
        startup_id = _to_int(doc.get("_id"), 0)
    if startup_id is None:
        startup_id = 0
    data["id"] = startup_id
    data["_id"] = str(startup_id)
    return data


def _get_client() -> MongoClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=MONGODB_TIMEOUT_MS,
        )
        _mongo_client.admin.command("ping")
    return _mongo_client


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = _get_client()[MONGODB_DB_NAME]
    return _db


def get_connection():
    """MongoDB db objectini qaytaradi."""
    return _get_db()


def _next_sequence(counter_name: str) -> int:
    db = _get_db()
    row = db.counters.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(row.get("seq", 1))


def _max_numeric_field(collection: Collection, field_name: str) -> int:
    row = collection.find_one(
        {field_name: {"$type": "number"}},
        sort=[(field_name, DESCENDING)],
        projection={field_name: 1},
    )
    if not row:
        return 0
    return _to_int(row.get(field_name), 0) or 0


def _ensure_counter_seed(counter_name: str, value: int):
    db = _get_db()
    db.counters.update_one({"_id": counter_name}, {"$setOnInsert": {"seq": 0}}, upsert=True)
    db.counters.update_one({"_id": counter_name}, {"$max": {"seq": int(value)}})


def _sync_counters():
    db = _get_db()
    for counter_name, (collection_name, field_name) in _COUNTER_CONFIG.items():
        max_value = _max_numeric_field(db[collection_name], field_name)
        _ensure_counter_seed(counter_name, max_value)


def _ensure_indexes():
    db = _get_db()

    db[USERS_COLLECTION].create_index([("user_id", ASCENDING)], unique=True)
    db[USERS_COLLECTION].create_index([("joined_at", DESCENDING)])

    db[STARTUPS_COLLECTION].create_index([("id", ASCENDING)], unique=True)
    db[STARTUPS_COLLECTION].create_index([("owner_id", ASCENDING)])
    db[STARTUPS_COLLECTION].create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db[STARTUPS_COLLECTION].create_index([("category", ASCENDING), ("status", ASCENDING)])
    db[STARTUPS_COLLECTION].create_index(
        [("channel_post_id", ASCENDING)],
        unique=True,
        sparse=True,
    )

    db[STARTUP_MEMBERS_COLLECTION].create_index([("id", ASCENDING)], unique=True)
    db[STARTUP_MEMBERS_COLLECTION].create_index(
        [("startup_id", ASCENDING), ("status", ASCENDING), ("joined_at", DESCENDING)]
    )
    db[STARTUP_MEMBERS_COLLECTION].create_index([("user_id", ASCENDING), ("status", ASCENDING)])

    db["pro_subscriptions"].create_index([("id", ASCENDING)], unique=True)
    db["pro_subscriptions"].create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    db["pro_subscriptions"].create_index([("end_at", ASCENDING)])

    db["pro_payments"].create_index([("id", ASCENDING)], unique=True)
    db["pro_payments"].create_index([("status", ASCENDING), ("created_at", DESCENDING)])

    db["referrals"].create_index([("id", ASCENDING)], unique=True)
    db["referrals"].create_index([("invited_id", ASCENDING)], unique=True)
    db["referrals"].create_index([("inviter_id", ASCENDING), ("status", ASCENDING)])

    db["referral_rewards"].create_index([("id", ASCENDING)], unique=True)
    db["referral_rewards"].create_index([("inviter_id", ASCENDING), ("created_at", DESCENDING)])

    db["admins"].create_index([("id", ASCENDING)], unique=True)
    db["admins"].create_index([("username", ASCENDING)], unique=True)


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _collection_has_data() -> bool:
    db = _get_db()
    for col in (USERS_COLLECTION, STARTUPS_COLLECTION, STARTUP_MEMBERS_COLLECTION, "admins"):
        if db[col].estimated_document_count() > 0:
            return True
    return False

def _migrate_sqlite_to_mongodb():
    if not MONGO_AUTO_MIGRATE:
        return
    if _collection_has_data():
        return
    if not os.path.exists(SQLITE_MIGRATION_PATH):
        return

    try:
        conn = sqlite3.connect(SQLITE_MIGRATION_PATH)
        conn.row_factory = sqlite3.Row
    except Exception:
        return

    db = _get_db()
    migrated = defaultdict(int)

    try:
        cursor = conn.cursor()

        if _table_exists(cursor, "users"):
            cursor.execute("SELECT * FROM users")
            for row in cursor.fetchall():
                data = dict(row)
                user_id = _to_int(data.get("user_id"), None)
                if user_id is None:
                    continue
                doc = {
                    "_id": user_id,
                    "user_id": user_id,
                    "username": data.get("username") or "",
                    "first_name": data.get("first_name") or "",
                    "last_name": data.get("last_name") or "",
                    "phone": data.get("phone") or "",
                    "gender": data.get("gender") or "",
                    "birth_date": data.get("birth_date") or "",
                    "specialization": data.get("specialization") or "",
                    "experience": data.get("experience") or "",
                    "bio": data.get("bio") or "",
                    "joined_at": data.get("joined_at") or _now_iso(),
                }
                db[USERS_COLLECTION].replace_one({"_id": user_id}, doc, upsert=True)
                migrated["users"] += 1

        if _table_exists(cursor, "startups"):
            cursor.execute("SELECT * FROM startups")
            for row in cursor.fetchall():
                data = dict(row)
                startup_id = _to_int(data.get("id"), None)
                if startup_id is None:
                    continue
                doc = {
                    "_id": startup_id,
                    "id": startup_id,
                    "name": data.get("name") or "",
                    "description": data.get("description") or "",
                    "logo": data.get("logo"),
                    "group_link": data.get("group_link") or "",
                    "owner_id": _to_int(data.get("owner_id"), 0) or 0,
                    "required_skills": data.get("required_skills") or "",
                    "category": data.get("category") or "Boshqa",
                    "max_members": _to_int(data.get("max_members"), 10) or 10,
                    "status": data.get("status") or "pending",
                    "created_at": data.get("created_at") or _now_iso(),
                    "started_at": data.get("started_at"),
                    "results": data.get("results"),
                    "channel_post_id": _to_int(data.get("channel_post_id"), None),
                    "current_members": _to_int(data.get("current_members"), 0) or 0,
                }
                db[STARTUPS_COLLECTION].replace_one({"_id": startup_id}, doc, upsert=True)
                migrated["startups"] += 1

        if _table_exists(cursor, "startup_members"):
            cursor.execute("SELECT * FROM startup_members")
            for row in cursor.fetchall():
                data = dict(row)
                member_id = _to_int(data.get("id"), None)
                if member_id is None:
                    continue
                doc = {
                    "_id": member_id,
                    "id": member_id,
                    "startup_id": _to_int(data.get("startup_id"), 0) or 0,
                    "user_id": _to_int(data.get("user_id"), 0) or 0,
                    "status": data.get("status") or "pending",
                    "joined_at": data.get("joined_at") or _now_iso(),
                }
                db[STARTUP_MEMBERS_COLLECTION].replace_one({"_id": member_id}, doc, upsert=True)
                migrated["startup_members"] += 1

        if _table_exists(cursor, "pro_settings"):
            cursor.execute("SELECT * FROM pro_settings WHERE id = 1")
            row = cursor.fetchone()
            if row:
                data = dict(row)
                doc = {
                    "_id": 1,
                    "id": 1,
                    "pro_enabled": _to_int(data.get("pro_enabled"), 1) or 1,
                    "pro_price": _to_int(data.get("pro_price"), 100000) or 100000,
                    "card_number": data.get("card_number") or "",
                }
                db["pro_settings"].replace_one({"_id": 1}, doc, upsert=True)
                migrated["pro_settings"] += 1

        if _table_exists(cursor, "pro_subscriptions"):
            cursor.execute("SELECT * FROM pro_subscriptions")
            for row in cursor.fetchall():
                data = dict(row)
                sub_id = _to_int(data.get("id"), None)
                if sub_id is None:
                    continue
                doc = {
                    "_id": sub_id,
                    "id": sub_id,
                    "user_id": _to_int(data.get("user_id"), 0) or 0,
                    "start_at": data.get("start_at") or _now_iso(),
                    "end_at": data.get("end_at") or _now_iso(),
                    "status": data.get("status") or "active",
                    "source": data.get("source") or "payment",
                    "note": data.get("note") or "",
                    "created_at": data.get("created_at") or _now_iso(),
                }
                db["pro_subscriptions"].replace_one({"_id": sub_id}, doc, upsert=True)
                migrated["pro_subscriptions"] += 1

        if _table_exists(cursor, "pro_payments"):
            cursor.execute("SELECT * FROM pro_payments")
            for row in cursor.fetchall():
                data = dict(row)
                payment_id = _to_int(data.get("id"), None)
                if payment_id is None:
                    continue
                doc = {
                    "_id": payment_id,
                    "id": payment_id,
                    "user_id": _to_int(data.get("user_id"), 0) or 0,
                    "amount": _to_int(data.get("amount"), 0) or 0,
                    "card_number": data.get("card_number") or "",
                    "receipt_file_id": data.get("receipt_file_id") or "",
                    "status": data.get("status") or "pending",
                    "created_at": data.get("created_at") or _now_iso(),
                }
                db["pro_payments"].replace_one({"_id": payment_id}, doc, upsert=True)
                migrated["pro_payments"] += 1

        if _table_exists(cursor, "referrals"):
            cursor.execute("SELECT * FROM referrals")
            for row in cursor.fetchall():
                data = dict(row)
                referral_id = _to_int(data.get("id"), None)
                if referral_id is None:
                    continue
                doc = {
                    "_id": referral_id,
                    "id": referral_id,
                    "inviter_id": _to_int(data.get("inviter_id"), 0) or 0,
                    "invited_id": _to_int(data.get("invited_id"), 0) or 0,
                    "status": data.get("status") or "pending",
                    "created_at": data.get("created_at") or _now_iso(),
                    "confirmed_at": data.get("confirmed_at"),
                }
                db["referrals"].replace_one({"_id": referral_id}, doc, upsert=True)
                migrated["referrals"] += 1

        if _table_exists(cursor, "referral_rewards"):
            cursor.execute("SELECT * FROM referral_rewards")
            for row in cursor.fetchall():
                data = dict(row)
                reward_id = _to_int(data.get("id"), None)
                if reward_id is None:
                    continue
                doc = {
                    "_id": reward_id,
                    "id": reward_id,
                    "inviter_id": _to_int(data.get("inviter_id"), 0) or 0,
                    "months": _to_int(data.get("months"), 1) or 1,
                    "created_at": data.get("created_at") or _now_iso(),
                }
                db["referral_rewards"].replace_one({"_id": reward_id}, doc, upsert=True)
                migrated["referral_rewards"] += 1

        if _table_exists(cursor, "admins"):
            cursor.execute("SELECT * FROM admins")
            for row in cursor.fetchall():
                data = dict(row)
                admin_id = _to_int(data.get("id"), None)
                if admin_id is None:
                    continue
                doc = {
                    "_id": admin_id,
                    "id": admin_id,
                    "username": data.get("username") or "",
                    "password_hash": data.get("password_hash") or "",
                    "full_name": data.get("full_name") or "",
                    "email": data.get("email") or "",
                    "role": data.get("role") or "admin",
                    "last_login": data.get("last_login"),
                }
                db["admins"].replace_one({"_id": admin_id}, doc, upsert=True)
                migrated["admins"] += 1

        if _table_exists(cursor, "app_settings"):
            cursor.execute("SELECT * FROM app_settings WHERE id = 1")
            row = cursor.fetchone()
            if row:
                data = dict(row)
                doc = {
                    "_id": 1,
                    "id": 1,
                    "site_name": data.get("site_name") or "GarajHub",
                    "admin_email": data.get("admin_email") or "admin@garajhub.uz",
                    "timezone": data.get("timezone") or "Asia/Tashkent",
                }
                db["app_settings"].replace_one({"_id": 1}, doc, upsert=True)
                migrated["app_settings"] += 1
    finally:
        conn.close()

    if migrated:
        print(f"SQLite -> MongoDB migration completed: {dict(migrated)}")


def _ensure_defaults():
    db = _get_db()

    db["pro_settings"].update_one(
        {"_id": 1},
        {
            "$setOnInsert": {
                "_id": 1,
                "id": 1,
                "pro_enabled": 1,
                "pro_price": 100000,
                "card_number": "",
            }
        },
        upsert=True,
    )

    db["app_settings"].update_one(
        {"_id": 1},
        {
            "$setOnInsert": {
                "_id": 1,
                "id": 1,
                "site_name": "GarajHub",
                "admin_email": "admin@garajhub.uz",
                "timezone": "Asia/Tashkent",
            }
        },
        upsert=True,
    )

    if not db["admins"].find_one({"username": "admin"}):
        admin_id = _next_sequence("admins")
        try:
            db["admins"].insert_one(
                {
                    "_id": admin_id,
                    "id": admin_id,
                    "username": "admin",
                    "password_hash": generate_password_hash("admin123"),
                    "full_name": "Super Admin",
                    "email": "admin@garajhub.uz",
                    "role": "superadmin",
                    "last_login": None,
                }
            )
        except DuplicateKeyError:
            pass

    if not db["admins"].find_one({"username": "admin2"}):
        admin2_id = _next_sequence("admins")
        try:
            db["admins"].insert_one(
                {
                    "_id": admin2_id,
                    "id": admin2_id,
                    "username": "admin2",
                    "password_hash": generate_password_hash("admin2123"),
                    "full_name": "Second Admin",
                    "email": "admin2@garajhub.uz",
                    "role": "admin",
                    "last_login": None,
                }
            )
        except DuplicateKeyError:
            pass

    if not db["admins"].find_one({"username": "moderator"}):
        moderator_id = _next_sequence("admins")
        try:
            db["admins"].insert_one(
                {
                    "_id": moderator_id,
                    "id": moderator_id,
                    "username": "moderator",
                    "password_hash": generate_password_hash("moderator123"),
                    "full_name": "Moderator",
                    "email": "moderator@garajhub.uz",
                    "role": "moderator",
                    "last_login": None,
                }
            )
        except DuplicateKeyError:
            pass


def init_db():
    """MongoDB ni tayyorlash va kerak bo'lsa SQLite dan migratsiya qilish."""
    _ensure_indexes()
    _migrate_sqlite_to_mongodb()
    _ensure_defaults()
    _sync_counters()
    print("Database initialized successfully (MongoDB).")


# ======================== PRO SETTINGS FUNCTIONS ========================


def get_pro_settings() -> Dict:
    db = _get_db()
    row = db["pro_settings"].find_one({"_id": 1}) or {}
    return {
        "pro_enabled": int(row.get("pro_enabled", 0)),
        "pro_price": int(row.get("pro_price", 0)),
        "card_number": row.get("card_number", "") or "",
    }


def set_pro_enabled(enabled: bool):
    db = _get_db()
    db["pro_settings"].update_one({"_id": 1}, {"$set": {"pro_enabled": 1 if enabled else 0}}, upsert=True)


def set_pro_price(price: int):
    db = _get_db()
    db["pro_settings"].update_one({"_id": 1}, {"$set": {"pro_price": int(price)}}, upsert=True)


def set_pro_card(card_number: str):
    db = _get_db()
    db["pro_settings"].update_one({"_id": 1}, {"$set": {"card_number": card_number}}, upsert=True)


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _expire_old_subscriptions():
    db = _get_db()
    now = datetime.now()
    rows = db["pro_subscriptions"].find({"status": "active"}, {"id": 1, "end_at": 1})
    for row in rows:
        end_dt = _parse_datetime(row.get("end_at"))
        if end_dt and end_dt <= now:
            db["pro_subscriptions"].update_one(
                {"id": row.get("id")},
                {"$set": {"status": "expired"}},
            )


def get_active_pro_subscription(user_id: int) -> Optional[Dict]:
    _expire_old_subscriptions()
    db = _get_db()
    rows = list(db["pro_subscriptions"].find({"user_id": int(user_id), "status": "active"}))
    if not rows:
        return None
    rows.sort(key=lambda r: _parse_datetime(r.get("end_at")) or datetime.min, reverse=True)
    return _without_mongo_id(rows[0])


def is_user_pro(user_id: int) -> bool:
    return get_active_pro_subscription(user_id) is not None


def add_pro_subscription(user_id: int, months: int = 1, source: str = "payment", note: str = "") -> Dict:
    _expire_old_subscriptions()

    now = datetime.now()
    active = get_active_pro_subscription(user_id)
    if active and active.get("end_at"):
        start_base = _parse_datetime(active.get("end_at")) or now
    else:
        start_base = now

    start_at = start_base if start_base > now else now
    end_at = _add_months(start_at, months)

    sub_id = _next_sequence("pro_subscriptions")
    doc = {
        "_id": sub_id,
        "id": sub_id,
        "user_id": int(user_id),
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "status": "active",
        "source": source,
        "note": note,
        "created_at": _now_iso(),
    }
    _get_db()["pro_subscriptions"].insert_one(doc)
    return _without_mongo_id(doc) or {}

# ======================== PRO PAYMENTS FUNCTIONS ========================


def create_pro_payment(user_id: int, amount: int, card_number: str, receipt_file_id: str) -> int:
    payment_id = _next_sequence("pro_payments")
    _get_db()["pro_payments"].insert_one(
        {
            "_id": payment_id,
            "id": payment_id,
            "user_id": int(user_id),
            "amount": int(amount),
            "card_number": card_number,
            "receipt_file_id": receipt_file_id,
            "status": "pending",
            "created_at": _now_iso(),
        }
    )
    return int(payment_id)


def get_payment(payment_id: int) -> Optional[Dict]:
    row = _get_db()["pro_payments"].find_one({"id": int(payment_id)})
    return _without_mongo_id(row)


def get_pending_payments(limit: int = 20) -> List[Dict]:
    rows = _get_db()["pro_payments"].find({"status": "pending"}).sort("created_at", DESCENDING).limit(int(limit))
    return [_without_mongo_id(row) for row in rows if row]


def update_payment_status(payment_id: int, status: str):
    _get_db()["pro_payments"].update_one({"id": int(payment_id)}, {"$set": {"status": status}})


# ======================== REFERRAL FUNCTIONS ========================


def register_referral(inviter_id: int, invited_id: int) -> bool:
    if inviter_id == invited_id:
        return False

    db = _get_db()
    if db["referrals"].find_one({"invited_id": int(invited_id)}):
        return False

    referral_id = _next_sequence("referrals")
    try:
        db["referrals"].insert_one(
            {
                "_id": referral_id,
                "id": referral_id,
                "inviter_id": int(inviter_id),
                "invited_id": int(invited_id),
                "status": "pending",
                "created_at": _now_iso(),
                "confirmed_at": None,
            }
        )
        return True
    except DuplicateKeyError:
        return False


def confirm_referral(invited_id: int) -> Optional[int]:
    db = _get_db()
    row = db["referrals"].find_one({"invited_id": int(invited_id)})
    if not row:
        return None

    if row.get("status") != "confirmed":
        db["referrals"].update_one(
            {"id": row.get("id")},
            {"$set": {"status": "confirmed", "confirmed_at": _now_iso()}},
        )
    return _to_int(row.get("inviter_id"), None)


def get_confirmed_referral_count(inviter_id: int) -> int:
    return _get_db()["referrals"].count_documents(
        {"inviter_id": int(inviter_id), "status": "confirmed"}
    )


def get_referral_reward_count(inviter_id: int) -> int:
    return _get_db()["referral_rewards"].count_documents({"inviter_id": int(inviter_id)})


def add_referral_reward(inviter_id: int, months: int = 1):
    reward_id = _next_sequence("referral_rewards")
    _get_db()["referral_rewards"].insert_one(
        {
            "_id": reward_id,
            "id": reward_id,
            "inviter_id": int(inviter_id),
            "months": int(months),
            "created_at": _now_iso(),
        }
    )


def get_user_startup_count(owner_id: int) -> int:
    return _get_db()[STARTUPS_COLLECTION].count_documents({"owner_id": int(owner_id)})


# ======================== USER FUNCTIONS ========================


def get_user(user_id: int) -> Optional[Dict]:
    row = _get_db()[USERS_COLLECTION].find_one({"user_id": int(user_id)})
    return _without_mongo_id(row)


def save_user(user_id: int, username: str, first_name: str):
    _get_db()[USERS_COLLECTION].update_one(
        {"user_id": int(user_id)},
        {
            "$setOnInsert": {
                "_id": int(user_id),
                "user_id": int(user_id),
                "username": username or "",
                "first_name": first_name or "",
                "last_name": "",
                "phone": "",
                "gender": "",
                "birth_date": "",
                "specialization": "",
                "experience": "",
                "bio": "",
                "joined_at": _now_iso(),
            }
        },
        upsert=True,
    )


def update_user_field(user_id: int, field: str, value):
    if field not in _ALLOWED_USER_FIELDS:
        return
    _get_db()[USERS_COLLECTION].update_one(
        {"user_id": int(user_id)},
        {"$set": {field: value}},
    )


def update_user_specialization(user_id: int, specialization: str):
    update_user_field(user_id, "specialization", specialization)


def update_user_experience(user_id: int, experience: str):
    update_user_field(user_id, "experience", experience)


def get_all_users() -> List[int]:
    rows = _get_db()[USERS_COLLECTION].find({}, {"user_id": 1, "_id": 0})
    return [_to_int(row.get("user_id"), 0) or 0 for row in rows]


def get_recent_users(limit: int = 10) -> List[Dict]:
    rows = _get_db()[USERS_COLLECTION].find({}).sort("joined_at", DESCENDING).limit(int(limit))
    return [_without_mongo_id(row) for row in rows if row]


# ======================== STARTUP FUNCTIONS ========================


def create_startup(
    name: str,
    description: str,
    logo: Optional[str],
    group_link: str,
    owner_id: int,
    required_skills: str = "",
    category: str = "Boshqa",
    max_members: int = 10,
) -> Optional[str]:
    startup_id = _next_sequence("startups")
    _get_db()[STARTUPS_COLLECTION].insert_one(
        {
            "_id": startup_id,
            "id": startup_id,
            "name": name,
            "description": description,
            "logo": logo,
            "group_link": group_link,
            "owner_id": int(owner_id),
            "required_skills": required_skills or "",
            "category": category or "Boshqa",
            "max_members": int(max_members),
            "status": "pending",
            "created_at": _now_iso(),
            "started_at": None,
            "results": None,
            "channel_post_id": None,
            "current_members": 0,
        }
    )
    return str(startup_id)


def get_startup(startup_id: str) -> Optional[Dict]:
    sid = _to_int(startup_id, None)
    if sid is None:
        return None
    row = _get_db()[STARTUPS_COLLECTION].find_one({"id": sid})
    return _normalize_startup(row)


def get_startups_by_owner(owner_id: int) -> List[Dict]:
    rows = _get_db()[STARTUPS_COLLECTION].find({"owner_id": int(owner_id)}).sort("created_at", DESCENDING)
    return [_normalize_startup(row) for row in rows if row]


def get_pending_startups(page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    db = _get_db()[STARTUPS_COLLECTION]
    offset = (int(page) - 1) * int(per_page)
    query = {"status": "pending"}
    total = db.count_documents(query)
    rows = db.find(query).sort("created_at", DESCENDING).skip(offset).limit(int(per_page))
    return [_normalize_startup(row) for row in rows if row], total


def get_active_startups(page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    db = _get_db()[STARTUPS_COLLECTION]
    offset = (int(page) - 1) * int(per_page)
    query = {"status": "active"}
    total = db.count_documents(query)
    rows = db.find(query).sort("created_at", DESCENDING).skip(offset).limit(int(per_page))
    return [_normalize_startup(row) for row in rows if row], total


def get_completed_startups() -> List[Dict]:
    rows = _get_db()[STARTUPS_COLLECTION].find({"status": "completed"}).sort("created_at", DESCENDING)
    return [_normalize_startup(row) for row in rows if row]


def get_rejected_startups() -> List[Dict]:
    rows = _get_db()[STARTUPS_COLLECTION].find({"status": "rejected"}).sort("created_at", DESCENDING)
    return [_normalize_startup(row) for row in rows if row]


def get_recent_startups(limit: int = 10) -> List[Dict]:
    rows = _get_db()[STARTUPS_COLLECTION].find({}).sort("created_at", DESCENDING).limit(int(limit))
    return [_normalize_startup(row) for row in rows if row]


def update_startup_status(startup_id: str, status: str):
    sid = _to_int(startup_id, None)
    if sid is None:
        return
    updates: Dict[str, Any] = {"status": status}
    if status == "active":
        updates["started_at"] = _now_iso()
    _get_db()[STARTUPS_COLLECTION].update_one({"id": sid}, {"$set": updates})


def update_startup_results(startup_id: str, results: str, completed_at: datetime):
    sid = _to_int(startup_id, None)
    if sid is None:
        return
    updates: Dict[str, Any] = {"results": results}
    if completed_at:
        updates["completed_at"] = completed_at.isoformat()
    _get_db()[STARTUPS_COLLECTION].update_one({"id": sid}, {"$set": updates})


def update_startup_post_id(startup_id: str, post_id: int):
    sid = _to_int(startup_id, None)
    if sid is None:
        return
    _get_db()[STARTUPS_COLLECTION].update_one({"id": sid}, {"$set": {"channel_post_id": int(post_id)}})


def get_startup_by_post_id(post_id: int) -> Optional[Dict]:
    row = _get_db()[STARTUPS_COLLECTION].find_one({"channel_post_id": int(post_id)})
    return _normalize_startup(row)


def update_startup_current_members(startup_id: str, count: int):
    sid = _to_int(startup_id, None)
    if sid is None:
        return
    _get_db()[STARTUPS_COLLECTION].update_one({"id": sid}, {"$set": {"current_members": int(count)}})


def get_startups_by_category(category: str) -> List[Dict]:
    rows = _get_db()[STARTUPS_COLLECTION].find(
        {"category": category, "status": "active"}
    ).sort("created_at", DESCENDING)
    return [_normalize_startup(row) for row in rows if row]


def get_all_categories() -> List[str]:
    categories = _get_db()[STARTUPS_COLLECTION].distinct("category", {"status": "active"})
    return [category for category in categories if category]


def get_startups_by_ids(startup_ids: List[int]) -> List[Dict]:
    if not startup_ids:
        return []

    ids = []
    for startup_id in startup_ids:
        sid = _to_int(startup_id, None)
        if sid is not None:
            ids.append(sid)
    if not ids:
        return []

    rows = list(_get_db()[STARTUPS_COLLECTION].find({"id": {"$in": ids}}))
    by_id = {}
    for row in rows:
        norm = _normalize_startup(row)
        if norm:
            by_id[norm["id"]] = norm

    ordered: List[Dict] = []
    for sid in ids:
        if sid in by_id:
            ordered.append(by_id[sid])
    return ordered

# ======================== STARTUP MEMBERS FUNCTIONS ========================


def add_startup_member(startup_id: str, user_id: int):
    sid = _to_int(startup_id, None)
    if sid is None:
        return
    member_id = _next_sequence("startup_members")
    _get_db()[STARTUP_MEMBERS_COLLECTION].insert_one(
        {
            "_id": member_id,
            "id": member_id,
            "startup_id": sid,
            "user_id": int(user_id),
            "status": "pending",
            "joined_at": _now_iso(),
        }
    )


def get_join_request_id(startup_id: str, user_id: int) -> Optional[str]:
    sid = _to_int(startup_id, None)
    if sid is None:
        return None
    row = (
        _get_db()[STARTUP_MEMBERS_COLLECTION]
        .find({"startup_id": sid, "user_id": int(user_id)})
        .sort([("joined_at", DESCENDING), ("id", DESCENDING)])
        .limit(1)
    )
    rows = list(row)
    if not rows:
        return None
    return str(rows[0].get("id"))


def get_join_request(request_id: str) -> Optional[Dict]:
    rid = _to_int(request_id, None)
    if rid is None:
        return None
    row = _get_db()[STARTUP_MEMBERS_COLLECTION].find_one({"id": rid})
    return _without_mongo_id(row)


def update_join_request(request_id: str, status: str):
    rid = _to_int(request_id, None)
    if rid is None:
        return
    _get_db()[STARTUP_MEMBERS_COLLECTION].update_one({"id": rid}, {"$set": {"status": status}})


def get_startup_members(startup_id: str, page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    sid = _to_int(startup_id, None)
    if sid is None:
        return [], 0

    members_col = _get_db()[STARTUP_MEMBERS_COLLECTION]
    users_col = _get_db()[USERS_COLLECTION]

    offset = (int(page) - 1) * int(per_page)
    query = {"startup_id": sid, "status": "accepted"}

    total = members_col.count_documents(query)
    member_rows = list(
        members_col.find(query)
        .sort("joined_at", DESCENDING)
        .skip(offset)
        .limit(int(per_page))
    )

    user_ids = [row.get("user_id") for row in member_rows if row.get("user_id") is not None]
    if not user_ids:
        return [], total

    users = users_col.find({"user_id": {"$in": user_ids}})
    user_map = {}
    for user in users:
        clean = _without_mongo_id(user)
        if clean:
            user_map[clean.get("user_id")] = clean

    ordered_users: List[Dict] = []
    for member in member_rows:
        user = user_map.get(member.get("user_id"))
        if user:
            ordered_users.append(user)
    return ordered_users, total


def get_all_startup_members(startup_id: str) -> List[int]:
    sid = _to_int(startup_id, None)
    if sid is None:
        return []
    rows = _get_db()[STARTUP_MEMBERS_COLLECTION].find(
        {"startup_id": sid, "status": "accepted"},
        {"user_id": 1, "_id": 0},
    )
    return [_to_int(row.get("user_id"), 0) or 0 for row in rows]


def get_startup_member_count(startup_id: str) -> int:
    sid = _to_int(startup_id, None)
    if sid is None:
        return 0
    return _get_db()[STARTUP_MEMBERS_COLLECTION].count_documents({"startup_id": sid, "status": "accepted"})


def update_startup_member_count(startup_id: str):
    count = get_startup_member_count(startup_id)
    update_startup_current_members(startup_id, count)


def get_user_joined_startups(user_id: int) -> List[int]:
    rows = (
        _get_db()[STARTUP_MEMBERS_COLLECTION]
        .find({"user_id": int(user_id), "status": "accepted"}, {"startup_id": 1, "_id": 0})
        .sort("joined_at", DESCENDING)
    )
    result: List[int] = []
    for row in rows:
        sid = _to_int(row.get("startup_id"), None)
        if sid is not None:
            result.append(sid)
    return result


# ======================== STATISTICS FUNCTIONS ========================


def get_statistics() -> Dict:
    startups_col = _get_db()[STARTUPS_COLLECTION]
    return {
        "total_users": _get_db()[USERS_COLLECTION].count_documents({}),
        "total_startups": startups_col.count_documents({}),
        "pending_startups": startups_col.count_documents({"status": "pending"}),
        "active_startups": startups_col.count_documents({"status": "active"}),
        "completed_startups": startups_col.count_documents({"status": "completed"}),
        "rejected_startups": startups_col.count_documents({"status": "rejected"}),
    }


# ======================== SETTINGS FUNCTIONS ========================


def get_app_settings() -> Dict:
    row = _get_db()["app_settings"].find_one({"_id": 1}) or {}
    return {
        "site_name": row.get("site_name", "GarajHub"),
        "admin_email": row.get("admin_email", "admin@garajhub.uz"),
        "timezone": row.get("timezone", "Asia/Tashkent"),
    }


def update_app_settings(site_name: str, admin_email: str, timezone: str):
    _get_db()["app_settings"].update_one(
        {"_id": 1},
        {"$set": {"site_name": site_name, "admin_email": admin_email, "timezone": timezone}},
        upsert=True,
    )


# ======================== ADMIN FUNCTIONS ========================


def get_admin_by_username(username: str) -> Optional[Dict]:
    row = _get_db()["admins"].find_one({"username": username})
    return _without_mongo_id(row)


def get_admin_by_id(admin_id: int) -> Optional[Dict]:
    row = _get_db()["admins"].find_one({"id": int(admin_id)})
    return _without_mongo_id(row)


def get_all_admins() -> List[Dict]:
    rows = _get_db()["admins"].find({}).sort("id", ASCENDING)
    return [_without_mongo_id(row) for row in rows if row]


def add_admin(username: str, password_hash: str, full_name: str, email: str, role: str) -> Optional[int]:
    admin_id = _next_sequence("admins")
    doc = {
        "_id": admin_id,
        "id": admin_id,
        "username": username,
        "password_hash": password_hash,
        "full_name": full_name,
        "email": email,
        "role": role,
        "last_login": None,
    }
    try:
        _get_db()["admins"].insert_one(doc)
        return admin_id
    except DuplicateKeyError:
        return None


def delete_admin(admin_id: int) -> bool:
    result = _get_db()["admins"].delete_one({"id": int(admin_id)})
    return result.deleted_count > 0


def update_admin_last_login(admin_id: int):
    _get_db()["admins"].update_one({"id": int(admin_id)}, {"$set": {"last_login": _now_iso()}})
