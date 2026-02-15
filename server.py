import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, send_from_directory
from flask_cors import CORS
from functools import wraps
import threading
import time
import traceback
import sys
from werkzeug.security import generate_password_hash, check_password_hash

def _ensure_utf8_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

_ensure_utf8_stdio()

# Bot va Database importlarini aniq qilamiz
sys.path.append('.')  # Joriy papkaga qo'shamiz

# Database import
try:
    from db import (
        init_db, get_connection,
        get_user, save_user, update_user_field,
        create_startup, get_startup, get_startups_by_owner,
        get_pending_startups, get_active_startups, update_startup_status,
        get_statistics, get_all_users, get_recent_users, get_recent_startups,
        get_completed_startups, get_rejected_startups,
        get_startups_by_category, get_all_categories,
        get_startup_members, get_all_startup_members,
        update_startup_results, update_join_request, get_join_request,
        get_user_joined_startups,
        update_startup_post_id,
        get_startup_member_count,
        get_admin_by_username, get_admin_by_id, get_all_admins,
        add_admin, delete_admin, update_admin_last_login,
        get_app_settings, update_app_settings
    )
    DB_AVAILABLE = True
    print("✅ Database moduli muvaffaqiyatli yuklandi")
except ImportError as e:
    print(f"❌ Database import xatosi: {e}")
    DB_AVAILABLE = False
    # Fake functions for testing
    def init_db(): pass
    def get_connection(): return None
    def get_user(*args): return None
    def save_user(*args): return None
    def get_startup(*args): return None
    def update_startup_status(*args): return True
    def get_statistics(): return {
        'total_users': 0,
        'total_startups': 0,
        'active_startups': 0,
        'pending_startups': 0,
        'completed_startups': 0,
        'rejected_startups': 0
    }
    def get_all_users(): return []
    def get_recent_users(*args): return []
    def get_pending_startups(*args): return ([], 0)
    def get_admin_by_username(*args): return None
    def get_admin_by_id(*args): return None
    def get_all_admins(): return []
    def add_admin(*args): return None
    def delete_admin(*args): return False
    def update_admin_last_login(*args): return None
    def get_app_settings(): return {'site_name': 'GarajHub', 'admin_email': 'admin@garajhub.uz', 'timezone': 'Asia/Tashkent'}
    def update_app_settings(*args): return None

# Bot import va ishga tushirish
try:
    from main import bot, BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    import telebot.apihelper as apihelper
    BOT_AVAILABLE = True
    print("✅ Bot moduli muvaffaqiyatli yuklandi")
    
    # Bot threadini global o'zgaruvchi sifatida saqlash
    bot_thread = None
    
    def start_bot():
        """Botni alohida threadda ishga tushirish"""
        global bot_thread
        
        def run_bot():
            print("🤖 Bot ishga tushmoqda...")
            while True:
                try:
                    try:
                        bot.remove_webhook()
                    except:
                        pass
                    bot.infinity_polling(timeout=60, long_polling_timeout=60)
                except apihelper.ApiTelegramException as e:
                    if '409' in str(e):
                        logging.error(f"Telegram 409 conflict: {e}. Retrying...")
                        try:
                            bot.remove_webhook()
                        except:
                            pass
                        time.sleep(5)
                        continue
                    else:
                        logging.error(f"TeleBot ApiTelegramException: {e}")
                        time.sleep(5)
                        continue
                except Exception as e:
                    logging.error(f"Botda xatolik: {e}")
                    time.sleep(5)
        
        # Botni alohida threadda ishga tushirish
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        print("✅ Bot alohida threadda ishga tushirildi")
    
except ImportError as e:
    print(f"❌ Bot import xatosi: {e}")
    BOT_AVAILABLE = False
    BOT_TOKEN = "N/A"
    ADMIN_ID = 0
    CHANNEL_USERNAME = "N/A"
    
    def start_bot():
        print("⚠️ Bot mavjud emas, ishga tushirib bo'lmadi")

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'garajhub-admin-secret-key-2024')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

CORS(app)

# Logger sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('admin_panel.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Adminlar ro'yxati
ADMINS = {
    'admin': {
        'password': 'admin123',
        'full_name': 'Super Admin',
        'email': 'admin@garajhub.uz',
        'role': 'superadmin'
    },
    'moderator': {
        'password': 'moderator123',
        'full_name': 'Moderator',
        'email': 'moderator@garajhub.uz',
        'role': 'moderator'
    }
}

# Login talab qiluvchi decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return jsonify({'success': False, 'error': 'Kirish talab qilinadi'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Role based access control
def role_required(roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if session.get('admin_role') not in roles:
                return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== UTILITY FUNCTIONS ====================

def format_datetime(dt_str):
    """Datetime ni formatlash"""
    if not dt_str:
        return ""
    
    try:
        if isinstance(dt_str, datetime):
            return dt_str.strftime('%Y-%m-%d %H:%M')
        
        # String formatni parse qilish
        dt_str = str(dt_str)
        
        # Faqat sanani olish (birinchi 19 ta belgi)
        if len(dt_str) >= 19:
            dt_str = dt_str[:19]
        
        # Parse qilish
        try:
            dt = datetime.fromisoformat(dt_str.replace(' ', 'T'))
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return dt_str[:16] if len(dt_str) >= 16 else dt_str
        
    except Exception as e:
        logger.error(f"Date format error: {e}")
        return str(dt_str)[:16] if dt_str else ""

def format_date_for_display(date_str):
    """Ko'rish uchun formatlash"""
    try:
        if not date_str:
            return ""
        
        # String ga o'tkazish
        date_str = str(date_str)
        
        # Parse qilish
        try:
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(date_str[:19])
        except:
            return date_str[:16] if len(date_str) >= 16 else date_str
        
        now = datetime.now()
        diff = now - dt
        
        if diff.days == 0:
            if diff.seconds < 60:
                return "Hozirgina"
            elif diff.seconds < 3600:
                return f"{diff.seconds // 60} daqiqa oldin"
            else:
                return f"{diff.seconds // 3600} soat oldin"
        elif diff.days == 1:
            return "Kecha"
        elif diff.days < 7:
            return f"{diff.days} kun oldin"
        else:
            return dt.strftime('%d.%m.%Y')
    except Exception as e:
        logger.error(f"Display date format error: {e}")
        return str(date_str)[:16] if date_str else ""

# ==================== ANALYTICS HELPERS ====================

def _query_user_counts_by_day(start_date):
    conn = get_connection()
    if not conn:
        return {}
    try:
        start_dt = datetime.fromisoformat(str(start_date))
    except Exception:
        return {}

    result = {}
    rows = conn["users"].find({}, {"joined_at": 1})
    for row in rows:
        joined_at = row.get("joined_at")
        dt = parse_datetime_flexible(joined_at)
        if not dt:
            continue
        if dt.date() < start_dt.date():
            continue
        key = dt.date().isoformat()
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items(), key=lambda item: item[0]))

def _query_user_counts_by_month(start_month_date):
    conn = get_connection()
    if not conn:
        return {}
    try:
        start_dt = datetime.fromisoformat(str(start_month_date))
    except Exception:
        return {}

    result = {}
    rows = conn["users"].find({}, {"joined_at": 1})
    for row in rows:
        joined_at = row.get("joined_at")
        dt = parse_datetime_flexible(joined_at)
        if not dt:
            continue
        if dt.date() < start_dt.date():
            continue
        key = dt.strftime("%Y-%m")
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items(), key=lambda item: item[0]))

def _build_user_growth_chart(period: str):
    now = datetime.now()
    period = (period or 'month').lower()
    day_periods = {'week': 7, 'month': 30, 'quarter': 90}
    if period not in day_periods and period != 'year':
        period = 'month'
    
    if period in day_periods:
        days = day_periods[period]
        start_date = (now - timedelta(days=days - 1)).date()
        counts = _query_user_counts_by_day(start_date.isoformat())
        
        labels = []
        data = []
        for i in range(days):
            current = start_date + timedelta(days=i)
            key = current.isoformat()
            labels.append(current.strftime('%d.%m'))
            data.append(counts.get(key, 0))
    else:
        # Yearly: last 12 months
        month_names = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyun', 'Iyul', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']
        months = []
        year = now.year
        month = now.month
        for i in range(11, -1, -1):
            m = month - i
            y = year
            while m <= 0:
                m += 12
                y -= 1
            months.append((y, m))
        
        first_year, first_month = months[0]
        start_month_date = datetime(first_year, first_month, 1).date().isoformat()
        counts = _query_user_counts_by_month(start_month_date)
        
        labels = []
        data = []
        for y, m in months:
            key = f"{y:04d}-{m:02d}"
            labels.append(f"{month_names[m-1]} {y}")
            data.append(counts.get(key, 0))
    
    return {
        'labels': labels,
        'datasets': [{
            'label': "Yangi foydalanuvchilar",
            'data': data,
            'borderColor': '#2563eb',
            'backgroundColor': 'rgba(37, 99, 235, 0.15)',
            'fill': True,
            'tension': 0.4,
            'pointRadius': 3
        }]
    }

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Asosiy sahifa"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Admin login API"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username va password kiriting'}), 400
        
        # Adminni tekshirish
        admin = None
        if DB_AVAILABLE:
            admin = get_admin_by_username(username)
            if admin:
                if not check_password_hash(admin.get('password_hash', ''), password):
                    admin = None
        else:
            admin = ADMINS.get(username)
            if admin and admin.get('password') != password:
                admin = None
        
        if admin:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_role'] = admin.get('role', 'admin')
            session['admin_name'] = admin.get('full_name', username)
            session['admin_email'] = admin.get('email', f"{username}@garajhub.uz")
            if admin.get('id'):
                session['admin_id'] = admin.get('id')
                update_admin_last_login(admin.get('id'))
            
            logger.info(f"Admin kirildi: {username}")
            return jsonify({
                'success': True,
                'user': {
                    'username': username,
                    'full_name': admin.get('full_name', username),
                    'email': admin.get('email', f"{username}@garajhub.uz"),
                    'role': admin.get('role', 'admin')
                }
            })
        return jsonify({'success': False, 'error': 'Noto\'g\'ri login yoki parol'}), 401
    except Exception as e:
        logger.error(f"Login error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'Server xatosi'}), 500

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Logout API"""
    try:
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Logout error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check_auth')
def check_auth():
    """Auth tekshirish"""
    try:
        if 'admin_logged_in' in session:
            return jsonify({
                'authenticated': True,
                'success': True,
                'user': {
                    'username': session.get('admin_username'),
                    'full_name': session.get('admin_name'),
                    'email': session.get('admin_email'),
                    'role': session.get('admin_role')
                }
            })
        return jsonify({'authenticated': False, 'success': True})
    except Exception as e:
        logger.error(f"Check auth error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/statistics')
@login_required
def get_statistics_data():
    """Statistika ma'lumotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        stats = get_statistics()
        
        # Bugungi yangi foydalanuvchilar
        today = datetime.now().strftime('%Y-%m-%d')
        recent_users = get_recent_users(1000)
        new_today = 0
        for user in recent_users:
            joined_at = str(user.get('joined_at', ''))
            if joined_at.startswith(today):
                new_today += 1
        
        # Faol foydalanuvchilar (so'nggi 7 kun)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        active_users = 0
        for user in recent_users:
            joined_at = str(user.get('joined_at', ''))
            if joined_at >= week_ago:
                active_users += 1

        # Kategoriyalar statistikasi
        categories_data = {}
        try:
            for category in get_all_categories():
                categories_data[category] = len(get_startups_by_category(category))
        except Exception:
            categories_data = {}
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': stats.get('total_users', 0),
                'total_startups': stats.get('total_startups', 0),
                'active_startups': stats.get('active_startups', 0),
                'pending_startups': stats.get('pending_startups', 0),
                'completed_startups': stats.get('completed_startups', 0),
                'rejected_startups': stats.get('rejected_startups', 0),
                'new_today': new_today,
                'active_users': active_users,
                'categories': categories_data,
                'trends': {
                    'users': "+0%",
                    'startups': "+0%"
                }
            }
        })
    except Exception as e:
        logger.error(f"Statistics error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/analytics/user-growth')
@login_required
def analytics_user_growth():
    """Foydalanuvchi o'sishi statistikasi"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database mavjud emas'}), 500
        
        period = request.args.get('period', 'month')
        chart_data = _build_user_growth_chart(period)
        
        return jsonify({
            'success': True,
            'data': chart_data
        })
    except Exception as e:
        logger.error(f"User growth analytics error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/startup-distribution')
@login_required
def analytics_startup_distribution():
    """Startaplar taqsimoti"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database mavjud emas'}), 500
        
        categories = get_all_categories()
        labels = []
        data = []
        total = 0
        
        for category in categories:
            count = len(get_startups_by_category(category))
            labels.append(category)
            data.append(count)
            total += count
        
        palette = [
            '#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
            '#14b8a6', '#f97316', '#84cc16', '#06b6d4', '#e11d48'
        ]
        colors = [palette[i % len(palette)] for i in range(len(labels))]
        
        chart_data = {
            'labels': labels,
            'datasets': [{
                'data': data,
                'backgroundColor': colors,
                'borderWidth': 0
            }]
        }
        
        return jsonify({
            'success': True,
            'data': chart_data,
            'total': total
        })
    except Exception as e:
        logger.error(f"Startup distribution analytics error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users')
@login_required
def get_users():
    """Foydalanuvchilar ro'yxati"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        
        # DB dan foydalanuvchilarni olish
        all_users_ids = get_all_users()
        users = []
        
        for user_id in all_users_ids:
            user = get_user(user_id)
            if user:
                users.append(user)
        
        # Filtrlash
        if search:
            filtered_users = []
            for user in users:
                user_text = (
                    f"{user.get('first_name', '')} "
                    f"{user.get('last_name', '')} "
                    f"{user.get('username', '')} "
                    f"{user.get('phone', '')}"
                ).lower()
                if search.lower() in user_text:
                    filtered_users.append(user)
            users = filtered_users
        
        # Sort by joined_at desc
        users.sort(key=lambda x: x.get('joined_at', ''), reverse=True)
        
        # Pagination
        total = len(users)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_users = users[start_idx:end_idx]
        
        # Formatlash
        formatted_users = []
        for user in paginated_users:
            # Qo'shilgan startaplar soni
            user_id = user.get('user_id')
            joined_startups_count = 0
            if user_id:
                try:
                    joined_startups_count = len(get_startups_by_owner(user_id))
                except:
                    pass
            
            formatted_users.append({
                'id': str(user_id) if user_id else '',
                'user_id': user_id,
                'first_name': user.get('first_name', 'Noma\'lum'),
                'last_name': user.get('last_name', ''),
                'username': f"@{user.get('username', '')}" if user.get('username') else '—',
                'phone': user.get('phone', '—'),
                'joined_at': format_date_for_display(user.get('joined_at', '')),
                'status': 'active',
                'startup_count': joined_startups_count,
                'specialization': user.get('specialization', '—'),
                'experience': user.get('experience', '—')
            })
        
        return jsonify({
            'success': True,
            'data': formatted_users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page if per_page > 0 else 1
            }
        })
    except Exception as e:
        logger.error(f"Users error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/users/<user_id>')
@login_required
def get_user_detail(user_id):
    """Foydalanuvchi tafsilotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        # User_id ni int ga o'tkazish
        try:
            user_id_int = int(user_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Noto\'g\'ri user ID'}), 400
        
        user = get_user(user_id_int)
        if not user:
            return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'}), 404
        
        # User startaplari
        user_startups = get_startups_by_owner(user_id_int)
        startups_data = []
        for startup in user_startups[:10]:
            startups_data.append({
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', 'Noma\'lum'),
                'status': startup.get('status', 'unknown'),
                'created_at': format_datetime(startup.get('created_at', ''))
            })
        
        # Qo'shilgan startaplar
        joined_startups = get_user_joined_startups(user_id_int)
        
        return jsonify({
            'success': True,
            'data': {
                'id': user.get('user_id'),
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', ''),
                'username': user.get('username', ''),
                'phone': user.get('phone', ''),
                'gender': user.get('gender', ''),
                'birth_date': user.get('birth_date', ''),
                'specialization': user.get('specialization', ''),
                'experience': user.get('experience', ''),
                'bio': user.get('bio', ''),
                'joined_at': format_date_for_display(user.get('joined_at', '')),
                'startup_count': len(user_startups),
                'joined_startup_count': len(joined_startups),
                'startups': startups_data,
                'stats': {
                    'created': len(user_startups),
                    'joined': len(joined_startups),
                    'active': sum(1 for s in user_startups if s.get('status') == 'active'),
                    'completed': sum(1 for s in user_startups if s.get('status') == 'completed')
                }
            }
        })
    except Exception as e:
        logger.error(f"User detail error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startups')
@login_required
def get_startups_list():
    """Startaplar ro'yxati"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        status = request.args.get('status', 'all')
        category = request.args.get('category', 'all')
        
        # Barcha startaplarni yig'ish
        all_startups = []
        
        if status == 'all' or status == 'active':
            active_startups, _ = get_active_startups(1, 1000)
            all_startups.extend(active_startups)
        
        if status == 'all' or status == 'pending':
            pending_startups, _ = get_pending_startups(1, 1000)
            all_startups.extend(pending_startups)
        
        if status == 'all' or status == 'completed':
            completed_startups = get_completed_startups()
            all_startups.extend(completed_startups)
        
        if status == 'all' or status == 'rejected':
            rejected_startups = get_rejected_startups()
            all_startups.extend(rejected_startups)
        
        # Kategoriya bo'yicha filtrlash
        if category != 'all':
            all_startups = [s for s in all_startups if s.get('category') == category]
        
        # Qidiruv bo'lsa
        if search:
            filtered = []
            for startup in all_startups:
                startup_name = startup.get('name', '').lower()
                startup_desc = startup.get('description', '').lower()
                search_term = search.lower()
                
                if (search_term in startup_name or 
                    search_term in startup_desc):
                    filtered.append(startup)
            all_startups = filtered
        
        # Sort by created_at desc
        all_startups.sort(key=lambda x: str(x.get('created_at', '')), reverse=True)
        
        total = len(all_startups)
        
        # Pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_startups = all_startups[start_idx:end_idx] if total > 0 else []
        
        # Formatlash
        formatted_startups = []
        for startup in paginated_startups:
            # Muallif ma'lumotlari
            owner_id = startup.get('owner_id')
            owner_name = "Noma'lum"
            if owner_id:
                owner = get_user(owner_id)
                if owner:
                    owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
                    if not owner_name:
                        owner_name = f"User {owner_id}"
            
            # A'zolar soni
            startup_id = str(startup.get('_id', ''))
            members_count = 0
            try:
                members_count = get_startup_member_count(startup_id) or 0
            except:
                pass
            
            # Status matni
            status_texts = {
                'pending': '⏳ Kutilmoqda',
                'active': '▶️ Faol',
                'completed': '✅ Yakunlangan',
                'rejected': '❌ Rad etilgan'
            }
            
            description = startup.get('description', '')
            if len(description) > 100:
                description = description[:100] + '...'
            
            formatted_startups.append({
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', 'Noma\'lum'),
                'description': description,
                'owner_name': owner_name,
                'owner_id': owner_id,
                'status': startup.get('status', 'pending'),
                'status_text': status_texts.get(startup.get('status', 'pending'), startup.get('status', 'pending')),
                'category': startup.get('category', 'Boshqa'),
                'created_at': format_date_for_display(startup.get('created_at', '')),
                'started_at': format_date_for_display(startup.get('started_at', '')),
                'ended_at': format_date_for_display(startup.get('ended_at', '')),
                'member_count': members_count,
                'max_members': startup.get('max_members', 0),
                'logo': startup.get('logo', ''),
                'group_link': startup.get('group_link', '')
            })
        
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1
        
        return jsonify({
            'success': True,
            'data': formatted_startups,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages
            }
        })
    except Exception as e:
        logger.error(f"Startups error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/startup/<startup_id>', methods=['GET'])
@login_required
def get_startup_details(startup_id):
    """Startap tafsilotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        startup = get_startup(startup_id)
        if not startup:
            return jsonify({'success': False, 'error': 'Startap topilmadi'}), 404
        
        # Muallif ma'lumotlari
        owner_id = startup.get('owner_id')
        owner_info = None
        if owner_id:
            owner = get_user(owner_id)
            if owner:
                owner_info = {
                    'id': owner.get('user_id'),
                    'first_name': owner.get('first_name', ''),
                    'last_name': owner.get('last_name', ''),
                    'phone': owner.get('phone', ''),
                    'username': owner.get('username', ''),
                    'bio': owner.get('bio', '')
                }
        
        # A'zolar
        members = []
        try:
            members_data, _ = get_startup_members(startup_id, 1, 50)
            members = members_data
        except Exception as e:
            logger.error(f"Members olishda xato: {e}")
        
        # Status matni
        status_texts = {
            'pending': '⏳ Kutilmoqda',
            'active': '▶️ Faol',
            'completed': '✅ Yakunlangan',
            'rejected': '❌ Rad etilgan'
        }
        
        return jsonify({
            'success': True,
            'data': {
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', ''),
                'description': startup.get('description', ''),
                'status': startup.get('status', ''),
                'status_text': status_texts.get(startup.get('status'), startup.get('status')),
                'created_at': format_date_for_display(startup.get('created_at', '')),
                'started_at': format_date_for_display(startup.get('started_at', '')),
                'results': startup.get('results', ''),
                'group_link': startup.get('group_link', ''),
                'logo': startup.get('logo', ''),
                'owner': owner_info,
                'members': members,
                'member_count': len(members),
                'max_members': startup.get('max_members', 0),
                'required_skills': startup.get('required_skills', ''),
                'category': startup.get('category', 'Boshqa')
            }
        })
    except Exception as e:
        logger.error(f"Startup details error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startup/<startup_id>/approve', methods=['POST'])
@login_required
@role_required(['superadmin', 'moderator'])
def approve_startup(startup_id):
    """Startapni tasdiqlash"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        # Startup holatini yangilash
        update_startup_status(startup_id, 'active')
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if not startup:
                    return jsonify({'success': False, 'error': 'Startap topilmadi'}), 404
                
                # Egaga xabar
                if startup.get('owner_id'):
                    try:
                        bot.send_message(
                            startup['owner_id'],
                            f"🎉 <b>Tabriklaymiz!</b>\n\n"
                            f"✅ '<b>{startup['name']}</b>' startupingiz tasdiqlandi va kanalga joylandi!",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Egaga xabar yuborishda xato: {e}")
                
                # Kanalga post yuborish
                try:
                    user = get_user(startup['owner_id'])
                    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
                    
                    # Post matni
                    channel_text = (
                        f"🚀 <b>{startup['name']}</b>\n\n"
                        f"📝 {startup['description']}\n\n"
                        f"👤 <b>Muallif:</b> {owner_name}\n"
                        f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
                        f"🔧 <b>Kerakli mutaxassislar:</b>\n{startup.get('required_skills', '—')}\n\n"
                        f"👥 <b>A'zolar:</b> 0 / {startup.get('max_members', '—')}\n\n"
                        f"➕ <b>O'z startupingizni yaratish uchun:</b> @{bot.get_me().username}"
                    )
                    
                    # Tugma yaratish
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton('🤝 Startupga qo\'shilish', callback_data=f'join_startup_{startup_id}'))
                    
                    # Postni kanalga yuborish
                    if startup.get('logo'):
                        sent_message = bot.send_photo(
                            CHANNEL_USERNAME, 
                            startup['logo'], 
                            caption=channel_text, 
                            reply_markup=markup, 
                            parse_mode='HTML'
                        )
                    else:
                        sent_message = bot.send_message(
                            CHANNEL_USERNAME, 
                            channel_text, 
                            reply_markup=markup, 
                            parse_mode='HTML'
                        )
                    
                    # Post ID sini saqlash
                    update_startup_post_id(startup_id, sent_message.message_id)
                    
                    logger.info(f"Kanalga post joylandi: {startup_id} -> message_id: {sent_message.message_id}")
                    
                except Exception as e:
                    logger.error(f"Kanalga post yuborishda xato: {e}")
                    return jsonify({
                        'success': False, 
                        'error': f'Kanalga post yuborishda xato: {str(e)}'
                    }), 500
                    
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
                return jsonify({
                    'success': False, 
                    'error': f'Bot xatosi: {str(e)}'
                }), 500
        
        logger.info(f"Startup approved: {startup_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Startap tasdiqlandi va kanalga joylandi',
            'data': {
                'id': startup_id,
                'status': 'active'
            }
        })
    except Exception as e:
        logger.error(f"Approve startup error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startup/<startup_id>/reject', methods=['POST'])
@login_required
@role_required(['superadmin', 'moderator'])
def reject_startup(startup_id):
    """Startapni rad etish"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        data = request.json
        reason = data.get('reason', 'Qoidalarga muvofiq emas')
        
        update_startup_status(startup_id, 'rejected')
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if startup and startup.get('owner_id'):
                    bot.send_message(
                        startup['owner_id'],
                        f"❌ <b>Xabar!</b>\n\n"
                        f"Sizning '<b>{startup['name']}</b>' startupingiz rad etildi.\n\n"
                        f"<b>Sabab:</b> {reason}\n\n"
                        f"Iltimos, qoidalarga muvofiq qayta yarating.",
                        parse_mode='HTML'
                    )
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
        
        logger.info(f"Startup rejected: {startup_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Startap rad etildi',
            'data': {
                'id': startup_id,
                'status': 'rejected'
            }
        })
    except Exception as e:
        logger.error(f"Reject startup error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startup/<startup_id>/complete', methods=['POST'])
@login_required
@role_required(['superadmin', 'moderator'])
def complete_startup(startup_id):
    """Startapni yakunlash (admin)"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        data = request.json
        results = data.get('results', 'Muvaffaqiyatli yakunlandi')
        
        # Startup holatini yangilash
        update_startup_status(startup_id, 'completed')
        update_startup_results(startup_id, results, datetime.now())
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if startup:
                    # Barcha a'zolarga xabar
                    members = get_all_startup_members(startup_id)
                    for member_id in members:
                        try:
                            bot.send_message(
                                member_id,
                                f"🏁 <b>Startup yakunlandi</b>\n\n"
                                f"🎯 <b>{startup['name']}</b>\n"
                                f"📅 <b>Yakunlangan sana:</b> {datetime.now().strftime('%d-%m-%Y')}\n"
                                f"📝 <b>Natijalar:</b>\n{results}",
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            logger.error(f"Memberga xabar yuborishda xato {member_id}: {e}")
                    
                    # Muallifga alohida xabar
                    if startup.get('owner_id'):
                        bot.send_message(
                            startup['owner_id'],
                            f"🎊 <b>Tabriklaymiz!</b>\n\n"
                            f"'{startup['name']}' startapingiz muvaffaqiyatli yakunlandi!\n\n"
                            f"<b>Natijalar:</b>\n{results}",
                            parse_mode='HTML'
                        )
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
        
        logger.info(f"Startup completed: {startup_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Startap yakunlandi',
            'data': {
                'id': startup_id,
                'status': 'completed',
                'results': results
            }
        })
    except Exception as e:
        logger.error(f"Complete startup error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/broadcast', methods=['POST'])
@login_required
@role_required(['superadmin'])
def broadcast_message():
    """Xabar yuborish"""
    try:
        data = request.json
        message = data.get('message')
        
        if not message:
            return jsonify({'success': False, 'error': 'Xabar matni kiritilmagan'}), 400
        
        if not BOT_AVAILABLE or not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Bot yoki Database mavjud emas'}), 500
        
        sent_count = 0
        failed_count = 0
        
        users_ids = get_all_users()
        total_users = len(users_ids)
        
        for user_id in users_ids:
            try:
                bot.send_message(user_id, f"📢 <b>Yangilik!</b>\n\n{message}", parse_mode='HTML')
                sent_count += 1
                time.sleep(0.1)  # Flood dan qochish
            except Exception as e:
                logger.error(f"Foydalanuvchiga xabar yuborishda xato {user_id}: {e}")
                failed_count += 1
        
        logger.info(f"Broadcast message: sent={sent_count}, failed={failed_count}, total={total_users}")
        
        return jsonify({
            'success': True,
            'message': 'Xabar yuborildi',
            'data': {
                'sent': sent_count,
                'failed': failed_count,
                'total': total_users,
                'success_rate': f"{(sent_count/total_users*100):.1f}%" if total_users > 0 else "0%"
            }
        })
    except Exception as e:
        logger.error(f"Broadcast error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories')
@login_required
def get_categories():
    """Barcha kategoriyalar"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        categories = get_all_categories()
        
        # Har bir kategoriya uchun statistikalar
        category_stats = []
        for category in categories:
            startups = get_startups_by_category(category)
            active_count = sum(1 for s in startups if s.get('status') == 'active')
            pending_count = sum(1 for s in startups if s.get('status') == 'pending')
            completed_count = sum(1 for s in startups if s.get('status') == 'completed')
            rejected_count = sum(1 for s in startups if s.get('status') == 'rejected')
            
            category_stats.append({
                'name': category,
                'total': len(startups),
                'active': active_count,
                'pending': pending_count,
                'completed': completed_count,
                'rejected': rejected_count
            })
        
        # Sort by total descending
        category_stats.sort(key=lambda x: x['total'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': category_stats
        })
    except Exception as e:
        logger.error(f"Categories error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admins')
@login_required
def get_admins():
    """Adminlar ro'yxati"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database mavjud emas'}), 500
        
        admins = get_all_admins()
        formatted = []
        for admin in admins:
            formatted.append({
                'id': admin.get('id'),
                'username': admin.get('username'),
                'full_name': admin.get('full_name', ''),
                'email': admin.get('email', ''),
                'role': admin.get('role', 'admin'),
                'last_login': admin.get('last_login')
            })
        
        return jsonify({'success': True, 'data': formatted})
    except Exception as e:
        logger.error(f"Admins list error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admins', methods=['POST'])
@role_required(['superadmin'])
def create_admin():
    """Admin qo'shish"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database mavjud emas'}), 500
        
        data = request.json or {}
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()
        full_name = (data.get('full_name') or '').strip()
        email = (data.get('email') or '').strip()
        role = (data.get('role') or 'admin').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username va parol majburiy'}), 400
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Parol kamida 6 belgidan iborat bo\'lishi kerak'}), 400
        if role not in ['admin', 'superadmin', 'moderator']:
            role = 'admin'
        
        password_hash = generate_password_hash(password)
        admin_id = add_admin(username, password_hash, full_name, email, role)
        if not admin_id:
            return jsonify({'success': False, 'error': 'Bunday username mavjud'}), 400
        
        return jsonify({
            'success': True,
            'data': {
                'id': admin_id,
                'username': username,
                'full_name': full_name,
                'email': email,
                'role': role
            }
        })
    except Exception as e:
        logger.error(f"Create admin error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admins/<int:admin_id>', methods=['DELETE'])
@role_required(['superadmin'])
def remove_admin(admin_id):
    """Adminni o'chirish"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database mavjud emas'}), 500
        
        current_admin_id = session.get('admin_id')
        if current_admin_id and int(current_admin_id) == int(admin_id):
            return jsonify({'success': False, 'error': 'O\'zingizni o\'chira olmaysiz'}), 400
        
        admin = get_admin_by_id(admin_id)
        if not admin:
            return jsonify({'success': False, 'error': 'Admin topilmadi'}), 404
        
        if admin.get('role') == 'superadmin':
            superadmins = [a for a in get_all_admins() if a.get('role') == 'superadmin']
            if len(superadmins) <= 1:
                return jsonify({'success': False, 'error': 'Oxirgi superadminni o\'chirib bo\'lmaydi'}), 400
        
        deleted = delete_admin(admin_id)
        if not deleted:
            return jsonify({'success': False, 'error': 'Admin o\'chirilmadi'}), 400
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Delete admin error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
@role_required(['superadmin'])
def settings():
    """Sozlamalar"""
    try:
        if request.method == 'GET':
            base_settings = get_app_settings() if DB_AVAILABLE else {
                'site_name': 'GarajHub',
                'admin_email': 'admin@garajhub.uz',
                'timezone': 'Asia/Tashkent'
            }
            settings_data = {
                **base_settings,
                'bot_token': BOT_TOKEN if BOT_AVAILABLE else 'Noma\'lum',
                'channel_username': CHANNEL_USERNAME if BOT_AVAILABLE else 'Noma\'lum',
                'admin_id': ADMIN_ID if BOT_AVAILABLE else 'Noma\'lum',
                'bot_status': 'online' if BOT_AVAILABLE else 'offline',
                'db_status': 'online' if DB_AVAILABLE else 'offline',
                'version': '1.0.0',
                'uptime': int(time.time()),
                'real_data': True,
                'demo_mode': False
            }
            
            return jsonify({
                'success': True,
                'data': settings_data
            })
        else:
            # Sozlamalarni yangilash
            data = request.json
            site_name = (data.get('site_name') or 'GarajHub').strip()
            admin_email = (data.get('admin_email') or 'admin@garajhub.uz').strip()
            timezone = (data.get('timezone') or 'Asia/Tashkent').strip()
            
            if DB_AVAILABLE:
                update_app_settings(site_name, admin_email, timezone)
            
            logger.info(f"Settings updated by {session.get('admin_username')}: {data}")
            
            return jsonify({
                'success': True, 
                'message': 'Sozlamalar saqlandi'
            })
    except Exception as e:
        logger.error(f"Settings error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/system/health')
@login_required
def system_health():
    """Tizim holati"""
    try:
        health_data = {
            'services': {
                'bot': 'online' if BOT_AVAILABLE else 'offline',
                'database': 'online' if DB_AVAILABLE else 'offline',
                'web_server': 'online',
                'real_data': True
            },
            'uptime': int(time.time()),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': health_data
        })
    except Exception as e:
        logger.error(f"System health error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notifications')
@login_required
def get_notifications():
    """Bildirishnomalar"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database mavjud emas'}), 500
        
        # So'nggi faoliyatlar
        recent_startups = get_recent_startups(10)
        recent_users = get_recent_users(10)
        
        notifications = []
        
        # Yangi startaplar
        for startup in recent_startups:
            if startup.get('status') == 'pending':
                notifications.append({
                    'id': str(startup.get('_id', '')),
                    'type': 'new_startup',
                    'title': f"Yangi startup: {startup.get('name', '')}",
                    'message': f"Yangi startup yaratildi. Holati: Kutilmoqda",
                    'timestamp': format_date_for_display(startup.get('created_at', '')),
                    'read': False,
                    'data': {
                        'startup_id': str(startup.get('_id', '')),
                        'startup_name': startup.get('name', '')
                    }
                })
        
        # Yangi foydalanuvchilar
        for user in recent_users[:5]:
            notifications.append({
                'id': str(user.get('user_id', '')),
                'type': 'new_user',
                'title': f"Yangi foydalanuvchi: {user.get('first_name', '')} {user.get('last_name', '')}",
                'message': f"Yangi foydalanuvchi ro'yxatdan o'tdi",
                'timestamp': format_date_for_display(user.get('joined_at', '')),
                'read': False,
                'data': {
                    'user_id': user.get('user_id'),
                    'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}"
                }
            })
        
        # Sort by timestamp
        notifications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'data': notifications[:20]
        })
    except Exception as e:
        logger.error(f"Notifications error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== STATIC FILES ====================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Static fayllarni yuklash"""
    return send_from_directory('static', filename)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Sahifa topilmadi'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {traceback.format_exc()}")
    return jsonify({'success': False, 'error': 'Ichki server xatosi'}), 500

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'success': False, 'error': 'Kirish talab qilinadi'}), 401

@app.errorhandler(403)
def forbidden(error):
    return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403

# ==================== MAIN ====================

if __name__ == '__main__':
    # Database ni ishga tushirish
    if DB_AVAILABLE:
        try:
            init_db()
            print("✅ Database ishga tushirildi")
        except Exception as e:
            print(f"⚠️ Database ishga tushirishda xato: {e}")
    
    # Botni ishga tushirish
    if BOT_AVAILABLE:
        try:
            start_bot()
            # Botning ishga tushishini kutish
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ Bot ishga tushirishda xato: {e}")
    
    # Portni environment dan olish yoki default
    port = int(os.environ.get('PORT', 5000))
    
    # Flask serverni ishga tushirish
    print(f"\n" + "="*50)
    print(f"🚀 GarajHub Admin Panel")
    print(f"="*50)
    print(f"🌐 URL: http://localhost:{port}")
    print(f"🤖 Bot status: {'✅ Online' if BOT_AVAILABLE else '❌ Offline'}")
    print(f"🗄️ Database: {'✅ MongoDB' if DB_AVAILABLE else '❌ Offline'}")
    print(f"🔑 Admin login: admin / admin123")
    print(f"🔑 Admin2 login: admin2 / admin2123")
    print(f"🔧 Moderator login: moderator / moderator123")
    print(f"📊 Real data: ✅ Ha")
    print(f"🚫 Demo mode: ❌ Yo'q")
    print(f"="*50 + "\n")
    
    # Development mode
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
