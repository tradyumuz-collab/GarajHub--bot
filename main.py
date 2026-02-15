import os
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import telebot
import telebot.apihelper as apihelper
import time

from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

def _ensure_utf8_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

_ensure_utf8_stdio()

# Environment o'qish
load_dotenv()

# Bot tokenini environmentdan olish
BOT_TOKEN = os.getenv('BOT_TOKEN', '8545746982:AAFNOX6afGJ9ECRP5neHzinrM4DcT2seqeI')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@GarajHub_uz')

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(str(raw).strip().strip("'").strip('"'))
    except Exception:
        return default

ADMIN_ID = _env_int('ADMIN_ID', 6274852941)
ADMIN_ID_2 = _env_int('ADMIN_ID_2', 7903688837)
ADMIN_IDS = {ADMIN_ID}
if ADMIN_ID_2:
    ADMIN_IDS.add(ADMIN_ID_2)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def is_admin_user(user_id: int) -> bool:
    try:
        return int(user_id) in ADMIN_IDS
    except Exception:
        return False

# HTML belgilarni tozalash funksiyasi
def escape_html(text):
    """HTML belgilarini tozalash - Telegram HTML formatida ishlash uchun"""
    if not text:
        return ""
    
    text = str(text)
    
    # Faqat xavfli belgilarni escape qilish
    replacements = [
        ('&', '&amp;'),
        ('<', '&lt;'),
        ('>', '&gt;'),
    ]
    
    for old, new in replacements:
        text = text.replace(old, new)
    
    return text

# Database import
from db import (
    init_db,
    get_user, save_user, update_user_field,
    create_startup, get_startup, get_startups_by_owner,
    get_pending_startups, get_active_startups, update_startup_status, update_startup_results,
    add_startup_member, get_join_request_id, update_join_request, get_join_request,
    get_startup_members, get_statistics, get_all_users,
    get_recent_users, get_recent_startups, get_completed_startups,
    get_rejected_startups, get_all_startup_members,
    get_startups_by_category, get_all_categories,
    get_user_joined_startups, get_startups_by_ids,
    update_user_specialization, update_user_experience,
    update_startup_member_count, get_startup_member_count,
    update_startup_post_id, get_startup_by_post_id,
    update_startup_current_members,
    get_pro_settings, set_pro_enabled, set_pro_price, set_pro_card,
    is_user_pro, add_pro_subscription,
    create_pro_payment, get_payment, get_pending_payments, update_payment_status,
    register_referral, confirm_referral, get_confirmed_referral_count,
    get_referral_reward_count, add_referral_reward,
    get_user_startup_count, get_active_pro_subscription
)

# Database initialization
init_db()

# User state management
user_states = {}
category_data = {}  # Global dictionary for category data
pro_payment_data = {}
BOT_USERNAME_CACHE = None

def set_user_state(user_id: int, state: str):
    user_states[user_id] = state

def get_user_state(user_id: int) -> str:
    return user_states.get(user_id, '')

def clear_user_state(user_id: int):
    if user_id in user_states:
        del user_states[user_id]

def clear_user_data(user_id: int):
    """Foydalanuvchi ma'lumotlarini tozalash"""
    global category_data
    if user_id in category_data:
        del category_data[user_id]
    clear_user_state(user_id)

def get_bot_username():
    global BOT_USERNAME_CACHE
    if BOT_USERNAME_CACHE:
        return BOT_USERNAME_CACHE
    try:
        BOT_USERNAME_CACHE = bot.get_me().username
    except Exception:
        BOT_USERNAME_CACHE = None
    return BOT_USERNAME_CACHE

def is_pro_feature_enabled() -> bool:
    try:
        settings = get_pro_settings()
        return int(settings.get('pro_enabled', 0)) == 1
    except Exception:
        return False

def get_pro_status_text(user_id: int) -> str:
    sub = get_active_pro_subscription(user_id)
    if not sub:
        return "Pro: Yo'q"
    end_at = sub.get('end_at', '')
    end_text = end_at[:10] if isinstance(end_at, str) else ''
    return f"Pro: Faol (tugash: {end_text or 'N/A'})"

def parse_referral_id(message) -> Optional[int]:
    try:
        text = message.text or ""
        parts = text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            return int(parts[1].replace('ref_', '').strip())
    except Exception:
        return None
    return None

# Orqaga tugmasini yaratish
def create_back_button(include_menu=False):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('🔙 Orqaga'))
    if include_menu:
        markup.add(KeyboardButton('🏠 Asosiy menyu'))
    return markup

# Asosiy menyu tugmalari
def create_main_menu(user_id: int):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton('🌐 Startaplar'),
        KeyboardButton('🚀 Startup yaratish'),
        KeyboardButton('📌 Startaplarim'),
        KeyboardButton('👤 Profil')
    ]
    if is_pro_feature_enabled():
        if not is_user_pro(user_id):
            buttons.append(KeyboardButton('💳 Obuna'))
        buttons.append(KeyboardButton('🤝 Referal'))
    markup.add(*buttons)
    
    if is_admin_user(user_id):
        markup.add(KeyboardButton('⚙️ Admin panel'))
    
    return markup

# Qiymatni formatlash funksiyasi
def format_value(value):
    """None yoki bo'sh qiymatlarni "—" bilan almashtirish"""
    if value is None or value == '' or value == 'None':
        return '—'
    return str(value)

# START - BOSHLASH
@bot.message_handler(commands=['start', 'help', 'boshlash'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    referral_id = parse_referral_id(message)
    
    # Foydalanuvchi bazada bormi tekshirish
    user = get_user(user_id)

    if not user and referral_id:
        try:
            register_referral(referral_id, user_id)
        except Exception as e:
            logging.error(f"Referral register xatosi: {e}")
    
    # Kanalga obuna tekshirish
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            # Agar yangi foydalanuvchi
            if not user:
                save_user(user_id, username, first_name)
                request_phone_number(message)
            else:
                # Telefon borligini tekshirish
                if not user.get('phone'):
                    request_phone_number(message)
                else:
                    send_welcome_back_message(message, first_name)
        else:
            ask_for_subscription(message)
    except Exception as e:
        logging.error(f"Obuna tekshirishda xatolik: {e}")
        ask_for_subscription(message)

def ask_for_subscription(message):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('🔗 Kanalga otish', url=f'https://t.me/{CHANNEL_USERNAME[1:]}'),
        InlineKeyboardButton('✅ Tekshirish', callback_data='check_subscription')
    )
    bot.send_message(
        message.chat.id,
        "Davom etish uchun rasmiy kanalimizga obuna bo'ling:\n"
        f"👉 {CHANNEL_USERNAME}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check_subscription_callback(call):
    user_id = call.from_user.id
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            # Foydalanuvchi tekshirish
            user = get_user(user_id)
            
            if not user:
                # Yangi foydalanuvchi
                username = call.from_user.username or ""
                first_name = call.from_user.first_name or ""
                save_user(user_id, username, first_name)
                
                bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi")
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except:
                    pass
                request_phone_number(call.message)
            else:
                # Telefon borligini tekshirish
                if not user.get('phone'):
                    bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi")
                    try:
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                    except:
                        pass
                    request_phone_number(call.message)
                else:
                    # Mavjud foydalanuvchi
                    first_name = user.get('first_name', 'Foydalanuvchi')
                    bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi")
                    try:
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                    except:
                        pass
                    send_welcome_back_message(call, first_name)
        else:
            bot.answer_callback_query(call.id, "❌ Iltimos, kanalga obuna bo'ling!", show_alert=True)
    except Exception as e:
        logging.error(f"Obuna tekshirishda xatolik: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def request_phone_number(message):
    """Foydalanuvchidan telefon raqamni so'rash"""
    user_id = message.from_user.id
    set_user_state(user_id, 'waiting_phone')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton('📱 Telefon raqamni yuborish', request_contact=True))
    markup.add(KeyboardButton('🔙 Orqaga'))
    
    bot.send_message(
        message.chat.id,
        "Iltimos, telefon raqamingizni yuboring:",
        reply_markup=markup
    )

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    """Telefon raqamni qabul qilish"""
    user_id = message.from_user.id
    state = get_user_state(user_id)
    
    if state in ['waiting_phone', 'waiting_phone_edit']:
        # Telefon raqamni olish
        phone = message.contact.phone_number
        
        # Bazaga saqlash
        update_user_field(user_id, 'phone', phone)

        # Referral tasdiqlash
        try:
            inviter_id = confirm_referral(user_id)
            if inviter_id:
                confirmed = get_confirmed_referral_count(inviter_id)
                reward_count = get_referral_reward_count(inviter_id)
                next_goal = (reward_count + 1) * 10

                try:
                    bot.send_message(
                        inviter_id,
                        f"✅ <b>Yangi referral tasdiqlandi!</b>\n\n"
                        f"Hisob: <b>{confirmed}</b> / <b>{next_goal}</b>"
                    )
                except Exception:
                    pass

                if confirmed >= next_goal:
                    sub = add_pro_subscription(inviter_id, months=1, source='referral', note='referral_reward')
                    add_referral_reward(inviter_id, months=1)
                    end_at = sub.get('end_at', '')[:10] if sub else ''
                    try:
                        bot.send_message(
                            inviter_id,
                            "🎉 <b>Tabriklaymiz!</b>\n\n"
                            "Siz 10 ta referral to'pladingiz.\n"
                            f"Pro 1 oy berildi. Tugash: <b>{end_at or 'N/A'}</b>"
                        )
                    except Exception:
                        pass
        except Exception as e:
            logging.error(f"Referral confirm xatosi: {e}")
        
        # State tozalash
        clear_user_state(user_id)
        
        # Reply markup ni tozalash
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        
        if state == 'waiting_phone':
            # Foydalanuvchi ismi
            user = get_user(user_id)
            first_name = user.get('first_name', 'Foydalanuvchi')
            
            bot.send_message(
                message.chat.id,
                f"✅ <b>{first_name}, qoyil ro'yxatdan o'tdingiz!</b>\n\n",
                reply_markup=create_main_menu(user_id)
            )
        elif state == 'waiting_phone_edit':
            bot.send_message(
                message.chat.id,
                "✅ <b>Telefon raqami yangilandi!</b>",
                reply_markup=markup
            )
            # Profilga qaytish
            show_profile(message)

@bot.message_handler(content_types=['photo'])
def handle_photo_messages(message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    if state != 'waiting_pro_receipt':
        return

    settings = get_pro_settings()
    amount = pro_payment_data.get(user_id, {}).get('amount', settings.get('pro_price', 0))
    card = pro_payment_data.get(user_id, {}).get('card', settings.get('card_number', ''))
    receipt_file_id = message.photo[-1].file_id

    try:
        payment_id = create_pro_payment(user_id, amount, card, receipt_file_id)
    except Exception as e:
        logging.error(f"Pro payment create xatosi: {e}")
        bot.send_message(message.chat.id, "❌ <b>Xatolik yuz berdi.</b>\n\nKeyinroq urinib ko'ring.")
        clear_user_state(user_id)
        return

    user = get_user(user_id) or {}
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Noma'lum"
    text = (
        "🧾 <b>Yangi Pro to'lov cheki</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {name}\n"
        f"🆔 <b>ID:</b> {user_id}\n"
        f"👤 <b>Username:</b> @{user.get('username', '—')}\n"
        f"📞 <b>Telefon:</b> {user.get('phone', '—')}\n"
        f"💳 <b>Summa:</b> {amount} so'm\n"
        f'💳 <b>Karta:</b> {card or "Admin tomonidan qoshiladi"}\n'
        f"🧾 <b>Payment ID:</b> {payment_id}"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'pro_pay_approve_{payment_id}'),
        InlineKeyboardButton('❌ Rad etish', callback_data=f'pro_pay_reject_{payment_id}')
    )

    for admin_chat_id in ADMIN_IDS:
        try:
            bot.send_photo(admin_chat_id, receipt_file_id, caption=text, reply_markup=markup)
        except Exception as e:
            logging.error(f"Admin payment notify xatosi ({admin_chat_id}): {e}")

    bot.send_message(
        message.chat.id,
        "✅ <b>Chek qabul qilindi!</b>\n\n"
        "Administrator tasdiqlashini kuting."
    )
    pro_payment_data.pop(user_id, None)
    clear_user_state(user_id)

def send_welcome_back_message(message_or_call, first_name):
    """Avval ro'yxatdan o'tgan foydalanuvchi uchun"""
    if isinstance(message_or_call, types.CallbackQuery):
        chat_id = message_or_call.message.chat.id
        user_id = message_or_call.from_user.id
    else:
        chat_id = message_or_call.chat.id
        user_id = message_or_call.from_user.id
    
    clear_user_state(user_id)
    
    bot.send_message(
        chat_id,
        f"🎉 <b>Qaytganingiz bilan, {first_name}!</b>\n\n"
        f"🚀 <b>GarajHub</b> startaplar platformasiga xush kelibsiz!\n\n",
        reply_markup=create_main_menu(user_id)
    )

def show_main_menu(message_or_call):
    """Asosiy menyuni ko'rsatish"""
    if isinstance(message_or_call, types.CallbackQuery):
        chat_id = message_or_call.message.chat.id
        user_id = message_or_call.from_user.id
        try:
            bot.delete_message(chat_id, message_or_call.message.message_id)
        except:
            pass
    elif isinstance(message_or_call, types.Message):
        chat_id = message_or_call.chat.id
        user_id = message_or_call.from_user.id
    else:
        chat_id = message_or_call
        user_id = message_or_call
    
    clear_user_state(user_id)
    
    text = "🏠 <b>Asosiy menyu</b>\n\nQuyidagi menyudan kerakli bo'limni tanlang:"
    
    bot.send_message(chat_id, text, reply_markup=create_main_menu(user_id))

def send_subscription_info(chat_id: int, user_id: int):
    if not is_pro_feature_enabled():
        bot.send_message(
            chat_id,
            "ℹ️ <b>Pro funksiyasi hozir o'chirilgan.</b>\n\n"
            "Hozir barcha foydalanuvchilar uchun barcha funksiyalar ochiq."
        )
        return

    if is_user_pro(user_id):
        sub = get_active_pro_subscription(user_id)
        end_at = sub.get('end_at', '')[:10] if sub else ''
        bot.send_message(
            chat_id,
            f"⭐ <b>Sizda Pro obuna faol.</b>\n\n"
            f"Tugash sanasi: <b>{end_at or 'N/A'}</b>"
        )
        return

    settings = get_pro_settings()
    price = settings.get('pro_price', 0)
    card = settings.get('card_number', '')

    text = (
        "⭐ <b>Pro obuna</b>\n\n"
        f"💳 <b>Tarif:</b> {price} so'm\n"
        f'💳 <b>Karta:</b> {card or "Admin tomonidan qo'shiladi"}\n\n'
        "To'lov qiling va chek rasmini yuboring."
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('✅ Proga obuna bo\'lish', callback_data='pro_pay'),
        InlineKeyboardButton('🤝 Referal', callback_data='open_referral')
    )
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '💳 Obuna')
def handle_subscription_menu(message):
    send_subscription_info(message.chat.id, message.from_user.id)

def send_referral_info(chat_id: int, user_id: int):
    if not is_pro_feature_enabled():
        bot.send_message(
            chat_id,
            "ℹ️ <b>Pro funksiyasi hozir o'chirilgan.</b>\n\n"
            "Referal tizimi vaqtincha faol emas."
        )
        return

    bot_username = get_bot_username()
    link = f"https://t.me/{bot_username}?start=ref_{user_id}" if bot_username else "Bot username topilmadi"
    confirmed = get_confirmed_referral_count(user_id)
    reward_count = get_referral_reward_count(user_id)
    next_goal = (reward_count + 1) * 10
    remaining = max(0, next_goal - confirmed)

    text = (
        "🤝 <b>Referal havola</b>\n\n"
        f"🔗 <b>Havola:</b> {link}\n\n"
        f"📊 <b>Hisob:</b> {confirmed} / {next_goal}\n"
        f"⏳ <b>Qoldi:</b> {remaining} ta\n\n"
        "10 ta referral yig'ilsa 1 oylik Pro beriladi."
    )
    bot.send_message(chat_id, text)

@bot.message_handler(func=lambda message: message.text == '🤝 Referal')
def handle_referral_menu(message):
    send_referral_info(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == 'open_referral')
def handle_open_referral(call):
    try:
        send_referral_info(call.message.chat.id, call.from_user.id)
        bot.answer_callback_query(call.id)
    except Exception:
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'pro_pay')
def handle_pro_pay(call):
    user_id = call.from_user.id
    if not is_pro_feature_enabled():
        bot.answer_callback_query(call.id, "Pro funksiyasi o'chirilgan", show_alert=True)
        return
    if is_user_pro(user_id):
        bot.answer_callback_query(call.id, "Sizda Pro faol", show_alert=True)
        return

    settings = get_pro_settings()
    price = settings.get('pro_price', 0)
    card = settings.get('card_number', '')
    pro_payment_data[user_id] = {'amount': price, 'card': card}
    set_user_state(user_id, 'waiting_pro_receipt')

    text = (
        "💳 <b>Pro to'lov</b>\n\n"
        f"Summa: <b>{price} so'm</b>\n"
        f'Karta: <b>{card or "Admin tomonidan qo'shiladi"}</b>\n\n'
        "To'lovni amalga oshirib, chek rasmini yuboring."
    )
    bot.send_message(call.message.chat.id, text, reply_markup=create_back_button(True))
    bot.answer_callback_query(call.id)

# 👤 PROFIL BO'LIMI
@bot.message_handler(func=lambda message: message.text == '👤 Profil')
def show_profile(message):
    try:
        user_id = message.from_user.id
        clear_user_state(user_id)
        
        user = get_user(user_id)
        if not user:
            save_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
            user = get_user(user_id)
        
        profile_text = (
            "👤 <b>Profil ma'lumotlari:</b>\n\n"
            f"🧑 <b>Ism:</b> {format_value(user.get('first_name'))}\n"
            f"🧾 <b>Familiya:</b> {format_value(user.get('last_name'))}\n"
            f"⚧️ <b>Jins:</b> {format_value(user.get('gender'))}\n"
            f"📞 <b>Telefon:</b> {format_value(user.get('phone'))}\n"
            f"🎂 <b>Tug'ilgan sana:</b> {format_value(user.get('birth_date'))}\n"
            f"🔧 <b>Mutaxassislik:</b> {format_value(user.get('specialization'))}\n"
            f"📈 <b>Tajriba:</b> {format_value(user.get('experience'))}\n"
            f"📝 <b>Bio:</b> {format_value(user.get('bio'))}\n\n"
            "🛠 <b>Tahrirlash uchun tugmalardan birini tanlang:</b>"
        )
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton('✏️ Ism', callback_data='edit_first_name'),
            InlineKeyboardButton('✏️ Familiya', callback_data='edit_last_name'),
            InlineKeyboardButton('📞 Telefon', callback_data='edit_phone'),
            InlineKeyboardButton('⚧️ Jins', callback_data='edit_gender'),
            InlineKeyboardButton('🎂 Tug\'ilgan sana', callback_data='edit_birth_date'),
            InlineKeyboardButton('🔧 Mutaxassislik', callback_data='edit_specialization'),
            InlineKeyboardButton('📈 Tajriba', callback_data='edit_experience'),
            InlineKeyboardButton('📝 Bio', callback_data='edit_bio')
        )
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_main_menu'))

        bot.send_message(message.chat.id, profile_text, reply_markup=markup)
        
    except Exception as e:
        logging.error(f"Profil ko'rsatishda xatolik: {e}")
        bot.send_message(message.chat.id, "⚠️ <b>Xatolik yuz berdi!</b>",
                        reply_markup=create_back_button(True))

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit_profile(call):
    user_id = call.from_user.id
    
    try:
        if call.data == 'edit_first_name':
            set_user_state(user_id, 'editing_first_name')
            msg = bot.send_message(call.message.chat.id, "📝 <b>Ismingizni kiriting:</b>", 
                                  reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_first_name)
        
        elif call.data == 'edit_last_name':
            set_user_state(user_id, 'editing_last_name')
            msg = bot.send_message(call.message.chat.id, "📝 <b>Familiyangizni kiriting:</b>", 
                                  reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_last_name)
        
        elif call.data == 'edit_phone':
            set_user_state(user_id, 'waiting_phone_edit')
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton('📱 Telefon raqamni yuborish', request_contact=True))
            markup.add(KeyboardButton('🔙 Orqaga'))
            
            bot.send_message(
                call.message.chat.id,
                "📱 <b>Yangi telefon raqamingizni yuboring:</b>",
                reply_markup=markup
            )
        
        elif call.data == 'edit_gender':
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton('👨 Erkak', callback_data='gender_male'),
                InlineKeyboardButton('👩 Ayol', callback_data='gender_female'),
                InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_profile')
            )
            
            try:
                bot.edit_message_text(
                    "⚧️ <b>Jinsingizni tanlang:</b>",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup
                )
            except:
                bot.send_message(call.message.chat.id, "⚧️ <b>Jinsingizni tanlang:</b>", reply_markup=markup)
        
        elif call.data == 'edit_birth_date':
            set_user_state(user_id, 'editing_birth_date')
            msg = bot.send_message(
                call.message.chat.id, 
                "🎂 <b>Tug'ilgan sanangizni kiriting (kun-oy-yil)</b>\n"
                "Masalan: 30-04-2000", 
                reply_markup=create_back_button()
            )
            bot.register_next_step_handler(msg, process_birth_date)
        
        elif call.data == 'edit_specialization':
            set_user_state(user_id, 'editing_specialization')
            msg = bot.send_message(
                call.message.chat.id, 
                "🔧 <b>Mutaxassisligingizni kiriting:</b>\n\n"
                "Masalan: Python, AI, ML", 
                reply_markup=create_back_button()
            )
            bot.register_next_step_handler(msg, process_specialization)
        
        elif call.data == 'edit_experience':
            set_user_state(user_id, 'editing_experience')
            msg = bot.send_message(
                call.message.chat.id, 
                "📈 <b>Tajribangizni kiriting:</b>\n\n"
                "Masalan: 5 yil", 
                reply_markup=create_back_button()
            )
            bot.register_next_step_handler(msg, process_experience)
        
        elif call.data == 'edit_bio':
            set_user_state(user_id, 'editing_bio')
            msg = bot.send_message(call.message.chat.id, "📝 <b>Bio kiriting:</b>", 
                                  reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_bio)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Profil tahrirlashda xatolik: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)
        show_profile(call.message)

def process_first_name(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    if not message.text or message.text.strip() == '':
        bot.send_message(message.chat.id, "❌ <b>Ism kiritilmadi!</b>", 
                        reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "📝 <b>Ismingizni kiriting:</b>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_first_name)
        return
    
    first_name = message.text.strip()
    update_user_field(user_id, 'first_name', first_name)
    bot.send_message(message.chat.id, "✅ <b>Ismingiz muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_last_name(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    if not message.text or message.text.strip() == '':
        bot.send_message(message.chat.id, "❌ <b>Familiya kiritilmadi!</b>", 
                        reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "📝 <b>Familiyangizni kiriting:</b>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_last_name)
        return
    
    last_name = message.text.strip()
    update_user_field(user_id, 'last_name', last_name)
    bot.send_message(message.chat.id, "✅ <b>Familiyangiz muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

@bot.callback_query_handler(func=lambda call: call.data in ['gender_male', 'gender_female'])
def process_gender(call):
    try:
        user_id = call.from_user.id
        gender = 'Erkak' if call.data == 'gender_male' else 'Ayol'
        update_user_field(user_id, 'gender', gender)
        
        bot.answer_callback_query(call.id, "✅ Jins muvaffaqiyatli saqlandi")
        show_profile(call.message)
        
    except Exception as e:
        logging.error(f"Jinsni saqlashda xatolik: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_profile')
def back_to_profile(call):
    try:
        show_profile(call.message)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Profilga qaytishda xatolik: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def process_birth_date(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    if not message.text or message.text.strip() == '':
        bot.send_message(message.chat.id, "❌ <b>Sana kiritilmadi!</b>", 
                        reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "🎂 <b>Tug'ilgan sanangizni kiriting:</b>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_birth_date)
        return
    
    birth_date = message.text.strip()
    update_user_field(user_id, 'birth_date', birth_date)
    bot.send_message(message.chat.id, "✅ <b>Tug'ilgan sana muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_specialization(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    if not message.text or message.text.strip() == '':
        bot.send_message(message.chat.id, "❌ <b>Mutaxassislik kiritilmadi!</b>", 
                        reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "🔧 <b>Mutaxassisligingizni kiriting:</b>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_specialization)
        return
    
    specialization = message.text.strip()
    update_user_specialization(user_id, specialization)
    bot.send_message(message.chat.id, "✅ <b>Mutaxassislik muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_experience(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    if not message.text or message.text.strip() == '':
        bot.send_message(message.chat.id, "❌ <b>Tajriba kiritilmadi!</b>", 
                        reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "📈 <b>Tajribangizni kiriting:</b>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_experience)
        return
    
    experience = message.text.strip()
    update_user_experience(user_id, experience)
    bot.send_message(message.chat.id, "✅ <b>Tajriba muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_bio(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    if not message.text or message.text.strip() == '':
        bot.send_message(message.chat.id, "❌ <b>Bio kiritilmadi!</b>", 
                        reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "📝 <b>Bio kiriting:</b>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_bio)
        return
    
    bio = message.text.strip()
    update_user_field(user_id, 'bio', bio)
    bot.send_message(message.chat.id, "✅ <b>Bio saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

# 🌐 STARTAPLAR BO'LIMI
@bot.message_handler(func=lambda message: message.text == '🌐 Startaplar')
def show_startups_menu(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_startups_menu')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('🎯 Tavsiyalar'),
        KeyboardButton('🔎 Kategoriya bo\'yicha'),
        KeyboardButton('🏠 Asosiy menyu')
    )
    
    bot.send_message(message.chat.id, "🌐 <b>Startaplar bo'limi:</b>\n\nKerakli bo'limni tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🎯 Tavsiyalar' and get_user_state(message.from_user.id) == 'in_startups_menu')
def show_recommended_startups(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'viewing_recommended')
    show_recommended_page(message.chat.id, 1)

def show_recommended_page(chat_id, page, message_id=None):
    per_page = 1
    startups, total = get_active_startups(page, per_page=per_page)
    
    if not startups:
        if message_id:
            try:
                bot.edit_message_text(
                    "📭 <b>Hozircha startup mavjud emas.</b>",
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=create_back_button(True)
                )
            except:
                bot.send_message(chat_id, 
                                "📭 <b>Hozircha startup mavjud emas.</b>", 
                                reply_markup=create_back_button(True))
        else:
            bot.send_message(chat_id, 
                            "📭 <b>Hozircha startup mavjud emas.</b>", 
                            reply_markup=create_back_button(True))
        return
    
    startup = startups[0]
    
    # A'zolar sonini olish
    current_members = get_startup_member_count(startup['_id'])
    max_members = startup.get('max_members', 10)
    
    user = get_user(startup['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    # Sanani formatlash
    start_date = startup.get('started_at', '—')
    if start_date and start_date != '—':
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%d-%m-%Y')
        else:
            try:
                start_date = datetime.fromisoformat(str(start_date)).strftime('%d-%m-%Y')
            except:
                pass
    
    text = (
        f"💡 <b>Tavsiya {page}/{total_pages}</b>\n\n"
        f"🎯 <b>Nomi:</b> {startup['name']}\n"
        f"📅 <b>Boshlangan sana:</b> {start_date}\n"
        f"👤 <b>Muallif:</b> {owner_name}\n"
        f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
        f"🔧 <b>Kerakli mutaxassislar:</b> {startup.get('required_skills', '—')}\n"
        f"👥 <b>A'zolar:</b> {current_members} / {max_members}\n"
        f"📌 <b>Tavsif:</b> {startup['description']}"
    )
    
    markup = InlineKeyboardMarkup()
    
    # Agar a'zolar to'liq bo'lsa
    if current_members >= max_members:
        markup.add(InlineKeyboardButton('❌ A\'zolar to\'ldi', callback_data='full_members'))
    else:
        markup.add(InlineKeyboardButton('🤝 Qo\'shilish', callback_data=f'join_startup_{startup["_id"]}'))
    
    # Navigatsiya tugmalari
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton('◀️ Oldingi', callback_data=f'rec_page_{page-1}'))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton('Keyingi ▶️', callback_data=f'rec_page_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_startups_menu'))
    
    try:
        if message_id:
            if startup.get('logo'):
                try:
                    bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=types.InputMediaPhoto(startup['logo'], caption=text),
                        reply_markup=markup
                    )
                except:
                    try:
                        bot.edit_message_caption(
                            chat_id=chat_id,
                            message_id=message_id,
                            caption=text,
                            reply_markup=markup
                        )
                    except:
                        try:
                            bot.delete_message(chat_id, message_id)
                        except:
                            pass
                        msg = bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
            else:
                try:
                    bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=markup
                    )
                except:
                    try:
                        bot.delete_message(chat_id, message_id)
                    except:
                        pass
                    bot.send_message(chat_id, text, reply_markup=markup)
        else:
            if startup.get('logo'):
                bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
            else:
                bot.send_message(chat_id, text, reply_markup=markup)
    except Exception as e:
        logging.error(f"Xabar yuborish/yangilashda xatolik: {e}")
        if startup.get('logo'):
            bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rec_page_'))
def handle_recommended_page(call):
    try:
        page = int(call.data.split('_')[2])
        show_recommended_page(call.message.chat.id, page, call.message.message_id)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# 🔎 KATEGORIYA BO'YICHA
@bot.message_handler(func=lambda message: message.text == '🔎 Kategoriya bo\'yicha' and get_user_state(message.from_user.id) == 'in_startups_menu')
def show_categories(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'choosing_category')
    
    categories = get_all_categories()
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    if categories:
        for category in categories:
            category_emojis = {
                'Biznes': '💼',
                'Sog\'liq': '🏥',
                'Texnologiya': '📱',
                'Ekologiya': '🌿',
                'Ta\'lim': '🎓',
                'Dizayn': '🎨',
                'Dasturlash': '💻',
                'Savdo': '🛒',
                'Media': '🎬',
                'Karyera': '💼'
            }
            emoji = category_emojis.get(category, '🏷️')
            markup.add(InlineKeyboardButton(f'{emoji} {category}', callback_data=f'category_{category}'))
    else:
        markup.add(InlineKeyboardButton('💼 Biznes', callback_data='category_Biznes'))
        markup.add(InlineKeyboardButton('🏥 Sog\'liq', callback_data='category_Sog\'liq'))
        markup.add(InlineKeyboardButton('📱 Texnologiya', callback_data='category_Texnologiya'))
        markup.add(InlineKeyboardButton('🌿 Ekologiya', callback_data='category_Ekologiya'))
        markup.add(InlineKeyboardButton('🎓 Ta\'lim', callback_data='category_Ta\'lim'))
        markup.add(InlineKeyboardButton('🎨 Dizayn', callback_data='category_Dizayn'))
        markup.add(InlineKeyboardButton('💻 Dasturlash', callback_data='category_Dasturlash'))
        markup.add(InlineKeyboardButton('🛒 Savdo', callback_data='category_Savdo'))
        markup.add(InlineKeyboardButton('🎬 Media', callback_data='category_Media'))
        markup.add(InlineKeyboardButton('💼 Karyera', callback_data='category_Karyera'))
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_startups_menu'))
    
    bot.send_message(message.chat.id, "🏷️ <b>Kategoriya tanlang:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    try:
        category_name = call.data.split('_')[1]
        show_category_startups(call.message.chat.id, category_name, 1, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Category selection error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def show_category_startups(chat_id, category_name, page, message_id=None):
    try:
        startups = get_startups_by_category(category_name)
        
        if not startups:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_categories'))
            
            if message_id:
                try:
                    bot.edit_message_text(
                        f"🏷️ <b>{category_name}</b> kategoriyasida hozircha startup mavjud emas.",
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=markup
                    )
                except:
                    bot.send_message(chat_id, 
                                    f"🏷️ <b>{category_name}</b> kategoriyasida hozircha startup mavjud emas.",
                                    reply_markup=markup)
            else:
                bot.send_message(chat_id, 
                                f"🏷️ <b>{category_name}</b> kategoriyasida hozircha startup mavjud emas.",
                                reply_markup=markup)
            return
        
        per_page = 5
        total = len(startups)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = min(max(1, page), total_pages)
        
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total)
        page_startups = startups[start_idx:end_idx]
        
        category_emojis = {
            'Biznes': '💼',
            'Sog\'liq': '🏥',
            'Texnologiya': '📱',
            'Ekologiya': '🌿',
            'Ta\'lim': '🎓',
            'Dizayn': '🎨',
            'Dasturlash': '💻',
            'Savdo': '🛒',
            'Media': '🎬',
            'Karyera': '💼'
        }
        emoji = category_emojis.get(category_name, '🏷️')
        
        text = f"{emoji} <b>{category_name} startaplari</b>\n\n"
        
        for i, startup in enumerate(page_startups, start=start_idx+1):
            user = get_user(startup['owner_id'])
            owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
            
            # A'zolar sonini olish
            current_members = get_startup_member_count(startup['_id'])
            max_members = startup.get('max_members', 10)
            
            status_emoji = '✅' if current_members < max_members else '❌'
            text += f"{i}. <b>{startup['name']}</b> – {owner_name} {status_emoji}\n"
        
        markup = InlineKeyboardMarkup(row_width=5)
        
        # Raqamli tugmalar
        numbers = []
        for i in range(start_idx+1, start_idx+len(page_startups)+1):
            startup_idx = i - 1
            if startup_idx < len(startups):
                numbers.append(InlineKeyboardButton(f'{i}️⃣', callback_data=f'cat_startup_{startups[startup_idx]["_id"]}'))
        
        if numbers:
            markup.row(*numbers)
        
        # Navigatsiya
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton('◀️ Oldingi', callback_data=f'cat_page_{category_name}_{page-1}'))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton('Keyingi ▶️', callback_data=f'cat_page_{category_name}_{page+1}'))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_categories'))
        
        if message_id:
            try:
                bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=markup
                )
            except:
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
                bot.send_message(chat_id, text, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
    except Exception as e:
        logging.error(f"Show category startups error: {e}")
        bot.send_message(chat_id, f"⚠️ Xatolik yuz berdi!", reply_markup=create_back_button(True))

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_page_'))
def handle_category_page(call):
    try:
        parts = call.data.split('_')
        category_name = parts[2]
        page = int(parts[3])
        show_category_startups(call.message.chat.id, category_name, page, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Category page error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_startup_'))
def handle_category_startup_view(call):
    try:
        startup_id = call.data.split('_')[2]
        startup = get_startup(startup_id)
        
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        # A'zolar sonini olish
        current_members = get_startup_member_count(startup_id)
        max_members = startup.get('max_members', 10)
        
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        
        # Sanani formatlash
        start_date = startup.get('started_at', '—')
        if start_date and start_date != '—':
            if isinstance(start_date, datetime):
                start_date = start_date.strftime('%d-%m-%Y')
            else:
                try:
                    start_date = datetime.fromisoformat(str(start_date)).strftime('%d-%m-%Y')
                except:
                    pass
        
        text = (
            f"🎯 <b>Nomi:</b> {startup['name']}\n"
            f"📅 <b>Boshlangan sana:</b> {start_date}\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerakli mutaxassislar:</b> {startup.get('required_skills', '—')}\n"
            f"👥 <b>A'zolar:</b> {current_members} / {max_members}\n"
            f"📌 <b>Tavsif:</b> {startup['description']}"
        )
        
        markup = InlineKeyboardMarkup()
        
        # Agar a'zolar to'liq bo'lsa
        if current_members >= max_members:
            markup.add(InlineKeyboardButton('❌ A\'zolar to\'ldi', callback_data='full_members'))
        else:
            markup.add(InlineKeyboardButton('🤝 Startupga Qo\'shilish', callback_data=f'join_startup_{startup_id}'))
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_categories'))
        
        try:
            if startup.get('logo'):
                try:
                    bot.edit_message_media(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        media=types.InputMediaPhoto(startup['logo'], caption=text),
                        reply_markup=markup
                    )
                except:
                    try:
                        bot.edit_message_caption(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            caption=text,
                            reply_markup=markup
                        )
                    except:
                        bot.send_photo(call.message.chat.id, startup['logo'], caption=text, reply_markup=markup)
            else:
                try:
                    bot.edit_message_text(
                        text=text,
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        reply_markup=markup
                    )
                except:
                    bot.send_message(call.message.chat.id, text, reply_markup=markup)
        except:
            if startup.get('logo'):
                bot.send_photo(call.message.chat.id, startup['logo'], caption=text, reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, text, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Category startup view xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# 🤝 QO'SHILISH JARAYONI
@bot.callback_query_handler(func=lambda call: call.data.startswith('join_startup_'))
def handle_join_startup(call):
    try:
        startup_id = call.data.replace('join_startup_', '', 1)
        user_id = call.from_user.id

        # Startup ma'lumotlarini olish
        startup = get_startup(startup_id)
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return

        # A'zolar sonini tekshirish
        current_members = get_startup_member_count(startup_id)
        max_members = startup.get('max_members', 10)
        if current_members >= max_members:
            bot.answer_callback_query(call.id, "❌ A'zolar to'ldi!", show_alert=True)
            return

        # Startup egasi ekanligini tekshirish
        if startup['owner_id'] == user_id:
            bot.answer_callback_query(call.id, "❌ Siz bu startupning egasisiz!", show_alert=True)
            return

        # Avval so'rov yuborilganligini tekshirish
        request_id = get_join_request_id(startup_id, user_id)
        if request_id:
            member_request = get_join_request(request_id)
            if member_request:
                if member_request['status'] == 'pending':
                    bot.answer_callback_query(call.id, "📩 Sizning so'rovingiz hali ko'rib chiqilmoqda!", show_alert=True)
                elif member_request['status'] == 'accepted':
                    bot.answer_callback_query(call.id, "✅ Siz allaqachon bu startupda a'zosiz!", show_alert=True)
                elif member_request['status'] == 'rejected':
                    bot.answer_callback_query(call.id, "❌ So'rovingiz avval rad etilgan.", show_alert=True)
            return

        # Yangi so'rov yaratish
        add_startup_member(startup_id, user_id)
        request_id = get_join_request_id(startup_id, user_id)
        if not request_id:
            logging.error(f"Join request saqlanmadi: startup_id={startup_id}, user_id={user_id}")
            bot.answer_callback_query(call.id, "⚠️ So'rovni saqlashda xatolik yuz berdi.", show_alert=True)
            return

        # Foydalanuvchiga xabar
        bot.answer_callback_query(call.id, "✅ So'rovingiz muvaffaqiyatli yuborildi.", show_alert=True)

        # Startup egasiga xabar yuborish
        user = get_user(user_id)
        if not user:
            try:
                save_user(user_id, call.from_user.username or "", call.from_user.first_name or "")
                user = get_user(user_id)
            except Exception as e:
                logging.warning(f"Join so'rovida user create bo'lmadi: {e}")
                user = None

        user = user or {}
        first_name = user.get('first_name') or (call.from_user.first_name or "")
        last_name = user.get('last_name') or (call.from_user.last_name or "")
        user_name = f"{first_name} {last_name}".strip()
        if not user_name:
            user_name = call.from_user.username or f"User {user_id}"

        text = (
            f"🆕 <b>Qo'shilish so'rovi</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> <a href='tg://user?id={user_id}'>{escape_html(user_name)}</a>\n"
            f"📞 <b>Telefon:</b> {escape_html(format_value(user.get('phone')))}\n"
            f"🔧 <b>Mutaxassislik:</b> {escape_html(format_value(user.get('specialization')))}\n"
            f"📈 <b>Tajriba:</b> {escape_html(format_value(user.get('experience')))}\n"
            f"📝 <b>Bio:</b> {escape_html(format_value(user.get('bio')))}\n\n"
            f"🎯 <b>Startup:</b> {escape_html(startup['name'])}"
        )

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'approve_join_{request_id}'),
            InlineKeyboardButton('❌ Rad etish', callback_data=f'reject_join_{request_id}')
        )

        try:
            bot.send_message(startup['owner_id'], text, reply_markup=markup)
        except Exception as e:
            logging.error(f"Egaga xabar yuborishda xatolik: {e}")
    except Exception as e:
        logging.error(f"Join startup xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_join_'))
def approve_join_request(call):
    try:
        request_id = call.data.split('_')[2]
        
        # So'rov ma'lumotlarini olish
        member = get_join_request(request_id)
        
        if not member:
            bot.answer_callback_query(call.id, "❌ So'rov topilmadi!", show_alert=True)
            return
        
        startup_id = str(member['startup_id'])
        user_id = member['user_id']
        
        # A'zolar sonini tekshirish
        startup = get_startup(startup_id)
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        current_members = get_startup_member_count(startup_id)
        max_members = startup.get('max_members', 10)
        
        if current_members >= max_members:
            # So'rovni rad etish
            update_join_request(request_id, 'rejected')
            
            # Egaga xabar
            try:
                bot.edit_message_text(
                    "❌ <b>A'zolar to'ldi, so'rov rad etildi.</b>",
                    call.message.chat.id,
                    call.message.message_id
                )
            except:
                pass
            bot.answer_callback_query(call.id, "❌ A'zolar to'ldi!")
            
            # Foydalanuvchiga xabar
            try:
                bot.send_message(
                    user_id,
                    "❌ <b>Afsus, startupda joy qolmagan.</b>\n\n"
                    "Boshqa startaplarga qo'shilishingiz mumkin."
                )
            except:
                pass
            return
        
        # So'rov holatini yangilash
        update_join_request(request_id, 'accepted')
        
        # A'zolar sonini yangilash
        update_startup_member_count(startup_id)
        
        if startup:
            # Foydalanuvchiga xabar
            try:
                bot.send_message(
                    user_id,
                    f"🎉 <b>Tabriklaymiz!</b>\n\n"
                    f"✅ Sizning so'rovingiz qabul qilindi.\n\n"
                    f"🎯 <b>Startup:</b> {startup['name']}\n"
                    f"🔗 <b>Guruhga qo'shilish:</b> {startup.get('group_link', '—')}"
                )
            except Exception as e:
                logging.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
        
        # Egaga xabar
        try:
            bot.edit_message_text(
                "✅ <b>So'rov tasdiqlandi va foydalanuvchiga havola yuborildi.</b>",
                call.message.chat.id,
                call.message.message_id
            )
        except:
            pass
        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        
        # Kanal postini yangilash
        try:
            update_channel_post(startup_id)
        except:
            pass
        
    except Exception as e:
        logging.error(f"Approve join xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_join_'))
def reject_join_request(call):
    try:
        request_id = call.data.split('_')[2]
        
        # So'rov holatini yangilash
        update_join_request(request_id, 'rejected')
        
        # So'rov ma'lumotlarini olish
        member = get_join_request(request_id)
        if member:
            user_id = member['user_id']
            
            # Foydalanuvchiga xabar
            try:
                bot.send_message(
                    user_id,
                    "❌ <b>Afsus, so'rovingiz rad etildi.</b>\n\n"
                    "Boshqa startaplarga qo'shilishingiz mumkin."
                )
            except:
                pass
        
        # Egaga xabar
        try:
            bot.edit_message_text(
                "❌ <b>So'rov rad etildi.</b>",
                call.message.chat.id,
                call.message.message_id
            )
        except:
            pass
        bot.answer_callback_query(call.id, "✅ Rad etildi!")
        
    except Exception as e:
        logging.error(f"Reject join xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'full_members')
def handle_full_members(call):
    bot.answer_callback_query(call.id, "❌ A'zolar to'ldi!", show_alert=True)

# Qolgan kodlar uchun message handler ...
# (Character limit tufayli to'liq kod 2-qismda davom etiladi)
# bot_part2.py - Bu qismni bot_part1.py ga qo'shish kerak

# 🚀 STARTUP YARATISH
@bot.message_handler(func=lambda message: message.text == '🚀 Startup yaratish')
def start_creation(message):
    user_id = message.from_user.id
    
    # Telefon raqam borligini tekshirish
    user = get_user(user_id)
    if not user or not user.get('phone'):
        bot.send_message(
            message.chat.id,
            "📞 <b>Avval telefon raqamingizni kiritishingiz kerak!</b>\n\n"
            "Iltimos, profilingizga o'tib telefon raqamingizni qo'shing.",
            reply_markup=create_back_button(True)
        )
        return

    if is_pro_feature_enabled() and not is_user_pro(user_id):
        try:
            startup_count = get_user_startup_count(user_id)
        except Exception:
            startup_count = 0
        if startup_count >= 1:
            settings = get_pro_settings()
            price = settings.get('pro_price', 0)
            card = settings.get('card_number', '')
            text = (
                "⚠️ <b>Pro kerak!</b>\n\n"
                "Siz 1 ta bepul startup yaratdingiz.\n"
                "Keyingi startup uchun Pro obuna kerak.\n\n"
                f"💳 <b>Tarif:</b> {price} so'm\n"
                f'💳 <b>Karta:</b> {card or "Admin tomonidan qo'shiladi"}'
            )
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton('⭐ Proga obuna bo\'lish', callback_data='pro_pay'),
                InlineKeyboardButton('🤝 Referal', callback_data='open_referral')
            )
            bot.send_message(message.chat.id, text, reply_markup=markup)
            return
    
    set_user_state(user_id, 'creating_startup')
    
    msg = bot.send_message(message.chat.id, 
                          "📝 <b>Startup nomini kiriting:</b>", 
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_name)

def process_startup_name(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    if not hasattr(message, 'text') or not message.text:
        bot.send_message(message.chat.id, "❌ <b>Iltimos, startup nomini kiriting!</b>", reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "📝 <b>Startup nomini kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_name)
        return
    
    startup_name = message.text.strip()
    
    # Global category_data ga saqlaymiz
    global category_data
    category_data[user_id] = {
        'owner_id': user_id,
        'name': startup_name
    }
    
    msg = bot.send_message(message.chat.id, "📝 <b>Startup tavsifini kiriting:</b>", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_description)

def process_startup_description(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    if not hasattr(message, 'text') or not message.text:
        bot.send_message(message.chat.id, "❌ <b>Iltimos, startup tavsifini kiriting!</b>", reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "📝 <b>Startup tavsifini kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_description)
        return
    
    description = message.text.strip()
    
    global category_data
    if user_id in category_data:
        category_data[user_id]['description'] = description
    else:
        category_data[user_id] = {
            'owner_id': user_id,
            'description': description
        }
    
    # Kategoriya tanlash
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('💼 Biznes', callback_data='create_cat_Biznes'),
        InlineKeyboardButton('🏥 Sog\'liq', callback_data='create_cat_Sog\'liq'),
        InlineKeyboardButton('📱 Texnologiya', callback_data='create_cat_Texnologiya'),
        InlineKeyboardButton('🌿 Ekologiya', callback_data='create_cat_Ekologiya'),
        InlineKeyboardButton('🎓 Ta\'lim', callback_data='create_cat_Ta\'lim'),
        InlineKeyboardButton('🎨 Dizayn', callback_data='create_cat_Dizayn'),
        InlineKeyboardButton('💻 Dasturlash', callback_data='create_cat_Dasturlash'),
        InlineKeyboardButton('🛒 Savdo', callback_data='create_cat_Savdo'),
        InlineKeyboardButton('🎬 Media', callback_data='create_cat_Media'),
        InlineKeyboardButton('💼 Karyera', callback_data='create_cat_Karyera')
    )
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_main_menu_create'))
    
    bot.send_message(message.chat.id, "🏷️ <b>Kategoriya tanlang:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main_menu_create')
def handle_back_to_main_menu_from_create(call):
    """Startup yaratishdan asosiy menyuga qaytish"""
    try:
        user_id = call.from_user.id
        clear_user_data(user_id)
        show_main_menu(call)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"back_to_main_menu_create xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('create_cat_'))
def handle_create_category(call):
    try:
        category_map = {
            'create_cat_Biznes': 'Biznes',
            'create_cat_Sog\'liq': 'Sog\'liq',
            'create_cat_Texnologiya': 'Texnologiya',
            'create_cat_Ekologiya': 'Ekologiya',
            'create_cat_Ta\'lim': 'Ta\'lim',
            'create_cat_Dizayn': 'Dizayn',
            'create_cat_Dasturlash': 'Dasturlash',
            'create_cat_Savdo': 'Savdo',
            'create_cat_Media': 'Media',
            'create_cat_Karyera': 'Karyera'
        }
        
        if call.data not in category_map:
            bot.answer_callback_query(call.id, "❌ Kategoriya topilmadi!", show_alert=True)
            return
        
        category_name = category_map[call.data]
        user_id = call.from_user.id
        
        # Global category_data ni yangilash
        global category_data
        if user_id not in category_data:
            category_data[user_id] = {}
        
        category_data[user_id]['category'] = category_name
        
        # State ni saqlash
        set_user_state(user_id, 'creating_startup_logo')
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton('Skip'))
        markup.add(KeyboardButton('🔙 Orqaga'))
        
        msg = bot.send_message(call.message.chat.id,
                              "🖼 <b>Logo (rasm) yuboring yoki \"Skip\" tugmasini bosing:</b>",
                              reply_markup=markup)
        bot.register_next_step_handler(msg, process_startup_logo)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Kategoriya tanlash xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def process_startup_logo(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    global category_data
    if user_id not in category_data:
        category_data[user_id] = {}
    
    if message.text == 'Skip':
        category_data[user_id]['logo'] = None
    elif message.photo:
        category_data[user_id]['logo'] = message.photo[-1].file_id
    else:
        # Agar rasm emas matn kiritilsa
        category_data[user_id]['logo'] = None
    
    msg = bot.send_message(message.chat.id,
                          "🔗 <b>Guruh yoki kanal havolasini kiriting:</b>\n\n"
                          "Masalan: https://t.me/GarajHub_uz yoki @GarajHub_uz",
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_group_link)

def process_startup_group_link(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    # Havola formatini tekshirish
    link = message.text.strip()
    if not (link.startswith('https://t.me/') or link.startswith('@')):
        msg = bot.send_message(message.chat.id,
                              "⚠️ <b>Noto'g'ri havola format!</b>\n\n"
                              "Iltimos, Telegram guruh yoki kanal havolasini kiriting:\n"
                              "• https://t.me/GarajHub_uz\n"
                              "• @Garajhub_uz\n\n"
                              "Yoki '🔙 Orqaga' tugmasini bosing:",
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_group_link)
        return
    
    global category_data
    if user_id not in category_data:
        category_data[user_id] = {}
    
    category_data[user_id]['group_link'] = link
    
    msg = bot.send_message(message.chat.id,
                          "🔧 <b>Kerakli mutaxassislarni kiriting:</b>\n\n"
                          "Masalan: Python, Designer, Manager",
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_skills)

def process_startup_skills(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    global category_data
    if user_id not in category_data:
        category_data[user_id] = {}
    
    skills = message.text.strip()
    category_data[user_id]['required_skills'] = skills
    
    msg = bot.send_message(message.chat.id,
                          "👥 <b>Maksimal a'zolar sonini kiriting (sizga qancha a'zo kerak):</b>\n\n"
                          "Masalan: 10",
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_max_members)

def process_startup_max_members(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    try:
        max_members = int(message.text)
        if max_members <= 0:
            raise ValueError
    except ValueError:
        msg = bot.send_message(message.chat.id,
                              "⚠️ <b>Iltimos, musbat raqam kiriting!</b>\n\n"
                              "Masalan: 10",
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_max_members)
        return
    
    global category_data
    if user_id not in category_data:
        bot.send_message(message.chat.id,
                        "❌ <b>Ma'lumotlar saqlanmagan. Iltimos, qaytadan boshlang.</b>",
                        reply_markup=create_back_button())
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    data = category_data[user_id]
    data['max_members'] = max_members
    
    # Barcha kerakli ma'lumotlarni tekshirish
    required_fields = ['owner_id', 'name', 'description', 'category', 'group_link']
    for field in required_fields:
        if field not in data:
            bot.send_message(message.chat.id,
                            f"❌ <b>{field} maydoni topilmadi. Iltimos, qaytadan boshlang.</b>",
                            reply_markup=create_back_button())
            clear_user_data(user_id)
            show_main_menu(message)
            return
    
    # Startup yaratish (escape qilish shu yerda)
    startup_id = create_startup(
        name=escape_html(data['name']),
        description=escape_html(data['description']),
        logo=data.get('logo'),
        group_link=data['group_link'],
        owner_id=data['owner_id'],
        required_skills=escape_html(data.get('required_skills', '')),
        category=data.get('category', 'Boshqa'),
        max_members=data['max_members']
    )
    
    if not startup_id:
        bot.send_message(message.chat.id,
                        "❌ <b>Startup yaratishda xatolik yuz berdi!</b>\n\n"
                        "Iltimos, keyinroq qayta urinib ko'ring.",
                        reply_markup=create_back_button())
        clear_user_data(user_id)
        show_main_menu(message)
        return
    
    # Foydalanuvchiga xabar
    bot.send_message(message.chat.id,
                    "✅ <b>Startup yaratildi!</b>\n\n"
                    "⏳ Administrator tasdig'ini kutmoqda.",
                    reply_markup=create_main_menu(user_id))

    if is_pro_feature_enabled() and not is_user_pro(user_id):
        try:
            startup_count = get_user_startup_count(user_id)
        except Exception:
            startup_count = 0
        if startup_count == 1:
            settings = get_pro_settings()
            price = settings.get('pro_price', 0)
            card = settings.get('card_number', '')
            text = (
                "💡 <b>Ma'lumot:</b>\n\n"
                "Siz 1 ta bepul startup yaratdingiz.\n"
                "Keyingi startup uchun Pro obuna kerak bo'ladi.\n\n"
                f"💳 <b>Tarif:</b> {price} so'm\n"
                f'💳 <b>Karta:</b> {card or "Admin tomonidan qo'shiladi"}'
            )
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton('⭐ Proga obuna bo\'lish', callback_data='pro_pay'),
                InlineKeyboardButton('🤝 Referal', callback_data='open_referral')
            )
            bot.send_message(message.chat.id, text, reply_markup=markup)
    
    # Adminga xabar
    startup = get_startup(startup_id)
    user = get_user(data['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    text = (
        f"🆕 <b>Yangi startup yaratildi!</b>\n\n"
        f"🎯 <b>Nomi:</b> {startup['name']}\n"
        f"📌 <b>Tavsif:</b> {startup['description'][:200]}...\n"
        f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
        f"🔧 <b>Kerak:</b> {startup.get('required_skills', '—')}\n"
        f"👥 <b>Maksimal a'zolar:</b> {startup.get('max_members', '—')}\n\n"
        f"👤 <b>Muallif:</b> {owner_name}\n"
        f"📱 <b>Aloqa:</b> @{user.get('username', '—')}"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'admin_approve_{startup_id}'),
        InlineKeyboardButton('❌ Rad etish', callback_data=f'admin_reject_{startup_id}')
    )
    
    for admin_chat_id in ADMIN_IDS:
        try:
            if startup.get('logo'):
                bot.send_photo(admin_chat_id, startup['logo'], caption=text, reply_markup=markup)
            else:
                bot.send_message(admin_chat_id, text, reply_markup=markup)
        except Exception as e:
            logging.error(f"Adminga xabar yuborishda xatolik ({admin_chat_id}): {e}")
    
    # Ma'lumotlarni tozalash
    clear_user_data(user_id)

# 📌 STARTAPLARIM BO'LIMI
@bot.message_handler(func=lambda message: message.text == '📌 Startaplarim')
def show_my_startups_main(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_my_startups')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('📋 Mening startaplarim'),
        KeyboardButton('🤝 Qo\'shilgan startaplar'),
        KeyboardButton('🏠 Asosiy menyu')
    )
    
    bot.send_message(message.chat.id, "📌 <b>Startaplarim bo'limi:</b>\n\nKerakli bo'limni tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📋 Mening startaplarim' and get_user_state(message.from_user.id) == 'in_my_startups')
def show_my_startups_list(message):
    user_id = message.from_user.id
    startups = get_startups_by_owner(user_id)
    
    if not startups:
        bot.send_message(message.chat.id,
                        "📭 <b>Sizda hali startup mavjud emas.</b>",
                        reply_markup=create_back_button(True))
        return
    
    show_my_startups_page(message.chat.id, user_id, 1)

def show_my_startups_page(chat_id, user_id, page, message_id=None):
    startups = get_startups_by_owner(user_id)
    
    per_page = 5
    total = len(startups)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    page_startups = startups[start_idx:end_idx]
    
    text = f"📋 <b>Mening startaplarim</b>\n\n"
    
    for i, startup in enumerate(page_startups, start=start_idx + 1):
        status_emoji = {
            'pending': '⏳',
            'active': '▶️',
            'completed': '✅',
            'rejected': '❌'
        }.get(startup['status'], '❓')
        
        text += f"{i}. {startup['name']} – {status_emoji}\n"
    
    markup = InlineKeyboardMarkup(row_width=5)
    
    # Raqamli tugmalar
    buttons = []
    for i in range(start_idx + 1, start_idx + len(page_startups) + 1):
        startup_idx = i - 1
        if startup_idx < len(startups):
            buttons.append(InlineKeyboardButton(f'{i}️⃣', callback_data=f'my_startup_num_{startup_idx}'))
    
    if buttons:
        markup.row(*buttons)
    
    # Navigatsiya
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton('◀️ Oldingi', callback_data=f'my_startup_page_{page-1}'))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton('Keyingi ▶️', callback_data=f'my_startup_page_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_my_startups'))
    
    if message_id:
        try:
            bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup
            )
        except:
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            bot.send_message(chat_id, text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('my_startup_page_'))
def handle_my_startup_page(call):
    try:
        page = int(call.data.split('_')[3])
        user_id = call.from_user.id
        show_my_startups_page(call.message.chat.id, user_id, page, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"My startup page error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('my_startup_num_'))
def handle_my_startup_number(call):
    try:
        idx = int(call.data.split('_')[3])
        user_id = call.from_user.id
        startups = get_startups_by_owner(user_id)
        
        if idx < 0 or idx >= len(startups):
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        startup = startups[idx]
        view_my_startup_details(call.message.chat.id, user_id, startup, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"My startup number error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def view_my_startup_details(chat_id, user_id, startup, message_id=None):
    user = get_user(startup['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    # A'zolar soni
    current_members = get_startup_member_count(startup['_id'])
    max_members = startup.get('max_members', 10)
    
    status_texts = {
        'pending': '⏳ Kutilmoqda',
        'active': '▶️ Faol',
        'completed': '✅ Yakunlangan',
        'rejected': '❌ Rad etilgan'
    }
    status_text = status_texts.get(startup['status'], startup['status'])
    
    # Sanani formatlash
    start_date = startup.get('started_at', '—')
    if start_date and start_date != '—':
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%d-%m-%Y')
        else:
            try:
                start_date = datetime.fromisoformat(str(start_date)).strftime('%d-%m-%Y')
            except:
                pass
    
    text = (
        f"🎯 <b>Nomi:</b> {startup['name']}\n"
        f"📊 <b>Holati:</b> {status_text}\n"
        f"📅 <b>Boshlanish sanasi:</b> {start_date}\n"
        f"👤 <b>Muallif:</b> {owner_name}\n"
        f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
        f"👥 <b>A'zolar:</b> {current_members} / {max_members}\n"
        f"📌 <b>Tavsif:</b> {startup['description']}"
    )
    
    markup = InlineKeyboardMarkup()
    
    if startup['status'] == 'pending':
        markup.add(InlineKeyboardButton('⏳ Admin tasdig\'ini kutyapti', callback_data='waiting_approval'))
    elif startup['status'] == 'active':
        markup.add(InlineKeyboardButton('👥 A\'zolar', callback_data=f'view_members_{startup["_id"]}_1'))
        markup.add(InlineKeyboardButton('⏹️ Yakunlash', callback_data=f'complete_startup_{startup["_id"]}'))
    elif startup['status'] == 'completed':
        markup.add(InlineKeyboardButton('👥 A\'zolar', callback_data=f'view_members_{startup["_id"]}_1'))
        if startup.get('results'):
            markup.add(InlineKeyboardButton('📊 Natijalar', callback_data=f'view_results_{startup["_id"]}'))
    elif startup['status'] == 'rejected':
        markup.add(InlineKeyboardButton('❌ Rad etilgan', callback_data='rejected_info'))
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_my_startups_list'))
    
    if message_id:
        try:
            if startup.get('logo'):
                try:
                    bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=types.InputMediaPhoto(startup['logo'], caption=text),
                        reply_markup=markup
                    )
                except:
                    try:
                        bot.edit_message_caption(
                            chat_id=chat_id,
                            message_id=message_id,
                            caption=text,
                            reply_markup=markup
                        )
                    except:
                        bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
            else:
                try:
                    bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=markup
                    )
                except:
                    bot.send_message(chat_id, text, reply_markup=markup)
        except:
            if startup.get('logo'):
                bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
            else:
                bot.send_message(chat_id, text, reply_markup=markup)
    else:
        if startup.get('logo'):
            bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_members_'))
def view_startup_members(call):
    try:
        parts = call.data.split('_')
        startup_id = parts[2]
        page = int(parts[3])
        
        members, total = get_startup_members(startup_id, page)
        total_pages = max(1, (total + 4) // 5)
        
        if not members:
            text = "👥 <b>A'zolar</b>\n\n📭 <b>Hozircha a'zolar yo'q.</b>"
            markup = InlineKeyboardMarkup()
        else:
            text = f"👥 <b>A'zolar</b>\n\n"
            for i, member in enumerate(members, start=(page-1)*5+1):
                member_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
                if not member_name:
                    member_name = f"User {member.get('user_id', '')}"
                
                bio_short = member.get('bio', '')
                if bio_short and len(bio_short) > 30:
                    bio_short = bio_short[:30] + '...'
                
                text += f"{i}. <b>{member_name}</b>\n"
                if member.get('phone'):
                    text += f"   📱 {member.get('phone')}\n"
                if bio_short:
                    text += f"   📝 {bio_short}\n"
                text += "\n"
        
        markup = InlineKeyboardMarkup()
        
        # Navigatsiya
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton('◀️ Oldingi', callback_data=f'view_members_{startup_id}_{page-1}'))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton('Keyingi ▶️', callback_data=f'view_members_{startup_id}_{page+1}'))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data=f'back_to_my_startup_{startup_id}'))
        
        try:
            bot.edit_message_text(
                text=text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"View members xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_startup_'))
def complete_startup(call):
    try:
        startup_id = call.data.split('_')[2]
        user_id = call.from_user.id
        set_user_state(user_id, f'completing_startup_{startup_id}')
        
        msg = bot.send_message(call.message.chat.id, 
                              "📝 <b>Nimalarga erishdingiz?</b>\nNatijalarni yozing:", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_results, startup_id)
        
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def process_startup_results(message, startup_id):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        # Startup ko'rinishiga qaytish
        startups = get_startups_by_owner(user_id)
        for startup in startups:
            if startup['_id'] == startup_id:
                view_my_startup_details(message.chat.id, user_id, startup)
                break
        return
    
    results_text = escape_html(message.text)
    
    msg = bot.send_message(message.chat.id, 
                          "🖼 <b>Natijalar rasmini yuboring:</b>", 
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_photo, startup_id, results_text)

def process_startup_photo(message, startup_id, results_text):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        msg = bot.send_message(message.chat.id, 
                              "📝 <b>Nimalarga erishdingiz?</b>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_results, startup_id)
        return
    
    if message.photo:
        photo_id = message.photo[-1].file_id
        
        # Startup holati va natijalarini yangilash
        update_startup_status(startup_id, 'completed')
        update_startup_results(startup_id, results_text, datetime.now())
        
        # Barcha a'zolarni olish
        members = get_all_startup_members(startup_id)
        
        # Barcha a'zolarga xabar yuborish
        startup = get_startup(startup_id)
        end_date = datetime.now().strftime('%d-%m-%Y')
        success_count = 0
        
        for member_id in members:
            try:
                bot.send_photo(
                    member_id,
                    photo_id,
                    caption=(
                        f"🏁 <b>Startup yakunlandi</b>\n\n"
                        f"🎯 <b>{startup['name']}</b>\n"
                        f"📅 <b>Yakunlangan sana:</b> {end_date}\n"
                        f"📝 <b>Natijalar:</b> {results_text}"
                    )
                )
                success_count += 1
            except:
                pass
        
        bot.send_message(message.chat.id, 
                        f"✅ <b>Startup muvaffaqiyatli yakunlandi!</b>\n\n"
                        f"📤 Xabar yuborildi: {success_count} ta a'zoga")
        
        clear_user_state(user_id)
        
        # Yangilangan startup ma'lumotlarini ko'rsatish
        startups = get_startups_by_owner(user_id)
        for startup in startups:
            if startup['_id'] == startup_id:
                view_my_startup_details(message.chat.id, user_id, startup)
                break
    else:
        bot.send_message(message.chat.id, "⚠️ <b>Iltimos, rasm yuboring!</b>", reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "🖼 <b>Natijalar rasmini yuboring:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_photo, startup_id, results_text)

# Davom etadi (3-qismda admin panel)...
# bot_part3.py - Bu qismni bot_part2.py ga qo'shish kerak

# 🤝 QO'SHILGAN STARTAPLAR
@bot.message_handler(func=lambda message: message.text == '🤝 Qo\'shilgan startaplar' and get_user_state(message.from_user.id) == 'in_my_startups')
def show_joined_startups(message):
    user_id = message.from_user.id
    joined_startup_ids = get_user_joined_startups(user_id)
    
    if not joined_startup_ids:
        bot.send_message(message.chat.id,
                        "🤝 <b>Qo'shilgan startaplar:</b>\n\n"
                        "🔜 Hozircha qo'shilgan startapingiz yo'q.",
                        reply_markup=create_back_button(True))
        return
    
    startups = get_startups_by_ids(joined_startup_ids)
    
    # Sahifalangan ko'rinishda chiqaramiz
    show_joined_startups_page(message.chat.id, user_id, startups, 1)

def show_joined_startups_page(chat_id, user_id, startups, page, message_id=None):
    """Qo'shilgan startaplarni sahifalangan ko'rinishda ko'rsatish"""
    per_page = 5
    total = len(startups)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    page_startups = startups[start_idx:end_idx]
    
    text = f"🤝 <b>Qo'shilgan startaplar</b>\n\n"
    
    for i, startup in enumerate(page_startups, start=start_idx + 1):
        status_emoji = {
            'pending': '⏳',
            'active': '▶️',
            'completed': '✅',
            'rejected': '❌'
        }.get(startup['status'], '❓')
        
        # A'zolar sonini olish
        current_members = get_startup_member_count(startup['_id'])
        max_members = startup.get('max_members', 10)
        
        text += f"{i}. <b>{startup['name']}</b> {status_emoji}\n"
        text += f"   👥 {current_members}/{max_members} | 🏷️ {startup.get('category', '—')}\n\n"
    
    markup = InlineKeyboardMarkup(row_width=5)
    
    # Raqamli tugmalar (1️⃣, 2️⃣, 3️⃣...)
    numbers = []
    for i in range(start_idx + 1, start_idx + len(page_startups) + 1):
        startup_idx = i - 1
        if startup_idx < len(startups):
            numbers.append(InlineKeyboardButton(f'{i}️⃣', callback_data=f'joined_startup_{startups[startup_idx]["_id"]}'))
    
    if numbers:
        markup.row(*numbers)
    
    # Navigatsiya tugmalari
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton('◀️ Oldingi', callback_data=f'joined_page_{page-1}'))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton('Keyingi ▶️', callback_data=f'joined_page_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_my_startups'))
    
    if message_id:
        try:
            bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup
            )
        except:
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            bot.send_message(chat_id, text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('joined_page_'))
def handle_joined_page(call):
    """Qo'shilgan startaplar sahifasini o'zgartirish"""
    try:
        page = int(call.data.split('_')[2])
        user_id = call.from_user.id
        joined_startup_ids = get_user_joined_startups(user_id)
        
        if not joined_startup_ids:
            bot.answer_callback_query(call.id, "❌ Startaplar topilmadi!", show_alert=True)
            return
        
        startups = get_startups_by_ids(joined_startup_ids)
        show_joined_startups_page(call.message.chat.id, user_id, startups, page, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Joined page error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('joined_startup_'))
def handle_joined_startup_view(call):
    """Qo'shilgan startup tafsilotlarini ko'rsatish"""
    try:
        startup_id = call.data.split('_')[2]
        startup = get_startup(startup_id)
        
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        user_id = call.from_user.id
        
        # Startup muallifini olish
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        
        # A'zolar sonini olish
        current_members = get_startup_member_count(startup_id)
        max_members = startup.get('max_members', 10)
        
        # Sanani formatlash
        start_date = startup.get('started_at', '—')
        if start_date and start_date != '—':
            if isinstance(start_date, datetime):
                start_date = start_date.strftime('%d-%m-%Y')
            else:
                try:
                    start_date = datetime.fromisoformat(str(start_date)).strftime('%d-%m-%Y')
                except:
                    pass
        
        text = (
            f"🤝 <b>Qo'shilgan startup:</b>\n\n"
            f"🎯 <b>Nomi:</b> {startup['name']}\n"
            f"📅 <b>Boshlangan sana:</b> {start_date}\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerakli mutaxassislar:</b> {startup.get('required_skills', '—')}\n"
            f"👥 <b>A'zolar:</b> {current_members} / {max_members}\n"
            f"📌 <b>Tavsif:</b> {startup['description']}\n"
            f"🔗 <b>Guruh havolasi:</b> {startup.get('group_link', '—')}"
        )
        
        markup = InlineKeyboardMarkup()
        
        # Guruhga kirish tugmasi
        if startup.get('group_link'):
            markup.add(InlineKeyboardButton('📲 Guruhga kirish', url=startup['group_link']))
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_joined_list'))
        
        try:
            if startup.get('logo'):
                bot.edit_message_media(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    media=types.InputMediaPhoto(startup['logo'], caption=text),
                    reply_markup=markup
                )
            else:
                bot.edit_message_text(
                    text=text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=markup
                )
        except:
            if startup.get('logo'):
                bot.send_photo(call.message.chat.id, startup['logo'], caption=text, reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, text, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Joined startup view error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_joined_list')
def handle_back_to_joined_list(call):
    """Qo'shilgan startaplar ro'yxatiga qaytish"""
    try:
        user_id = call.from_user.id
        joined_startup_ids = get_user_joined_startups(user_id)
        
        if not joined_startup_ids:
            bot.answer_callback_query(call.id, "❌ Startaplar topilmadi!", show_alert=True)
            return
        
        startups = get_startups_by_ids(joined_startup_ids)
        show_joined_startups_page(call.message.chat.id, user_id, startups, 1, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Back to joined list error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# ⚙️ ADMIN PANEL
@bot.message_handler(func=lambda message: message.text == '⚙️ Admin panel' and is_admin_user(message.chat.id))
def admin_panel(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_admin_panel')
    
    stats = get_statistics()
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('📊 Dashboard'),
        KeyboardButton('🚀 Startaplar'),
        KeyboardButton('👥 Foydalanuvchilar'),
        KeyboardButton('⭐ Pro sozlamalar'),
        KeyboardButton('🧾 Pro to\'lovlar'),
        KeyboardButton('📢 Xabar yuborish'),
        KeyboardButton('🏠 Asosiy menyu')
    )
    
    welcome_text = (
        f"👨‍💼 <b>Admin Panel</b>\n\n"
        f"📊 <b>Statistika:</b>\n"
        f" 👥 Foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f" 🚀 Startaplar: <b>{stats['total_startups']}</b>\n"
        f" ⏳ Kutilayotgan: <b>{stats['pending_startups']}</b>\n"
        f" ▶️ Faol: <b>{stats['active_startups']}</b>\n"
        f" ✅ Yakunlangan: <b>{stats['completed_startups']}</b>"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📊 Dashboard' and is_admin_user(message.chat.id))
def admin_dashboard(message):
    stats = get_statistics()
    recent_users = get_recent_users(5)
    recent_startups = get_recent_startups(5)
    
    dashboard_text = (
        f"📊 <b>Dashboard</b>\n\n"
        f"📈 <b>Umumiy statistikalar:</b>\n"
        f" 👥 Foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f" 🚀 Startaplar: <b>{stats['total_startups']}</b>\n"
        f" ⏳ Kutilayotgan: <b>{stats['pending_startups']}</b>\n"
        f" ▶️ Faol: <b>{stats['active_startups']}</b>\n"
        f" ✅ Yakunlangan: <b>{stats['completed_startups']}</b>\n\n"
    )
    
    if recent_users:
        dashboard_text += f"👥 <b>So'nggi foydalanuvchilar:</b>\n"
        for i, user in enumerate(recent_users, 1):
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            if not name:
                name = "Noma'lum"
            
            dashboard_text += f"{i}. <b>{name}</b>\n"
        dashboard_text += "\n"
    
    if recent_startups:
        dashboard_text += f"🚀 <b>So'nggi startaplar:</b>\n"
        for i, startup in enumerate(recent_startups, 1):
            status_emoji = {
                'pending': '⏳',
                'active': '▶️',
                'completed': '✅',
                'rejected': '❌'
            }.get(startup['status'], '❓')
            
            dashboard_text += f"{i}. {startup['name']} {status_emoji}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('🔄 Yangilash', callback_data='refresh_dashboard'),
        InlineKeyboardButton('📈 To\'liq statistikalar', callback_data='full_stats'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    bot.send_message(message.chat.id, dashboard_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '⭐ Pro sozlamalar' and is_admin_user(message.chat.id))
def admin_pro_settings(message):
    settings = get_pro_settings()
    status = "✅ Yoqilgan" if settings.get('pro_enabled', 0) else "❌ O'chirilgan"
    price = settings.get('pro_price', 0)
    card = settings.get('card_number', '')

    text = (
        "⭐ <b>Pro sozlamalar</b>\n\n"
        f"Status: <b>{status}</b>\n"
        f"Narx: <b>{price} so'm</b>\n"
        f'Karta: <b>{card or "Admin tomonidan qo'shiladi"}</b>\n\n'
        "Quyidagi tugmalardan birini tanlang:"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('🔁 Yoqish/O\'chirish', callback_data='pro_toggle'),
        InlineKeyboardButton('💳 Narxni o\'zgartirish', callback_data='pro_edit_price'),
        InlineKeyboardButton('💳 Kartani o\'zgartirish', callback_data='pro_edit_card'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🧾 Pro to\'lovlar' and is_admin_user(message.chat.id))
def admin_pro_payments(message):
    pending = get_pending_payments(10)
    if not pending:
        bot.send_message(message.chat.id, "✅ <b>Pending pro to'lovlar yo'q.</b>")
        return

    bot.send_message(message.chat.id, f"🧾 <b>Pending to'lovlar:</b> {len(pending)} ta")
    for pay in pending:
        user = get_user(pay['user_id']) or {}
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Noma'lum"
        text = (
            "🧾 <b>Pro to'lov</b>\n\n"
            f"🧾 <b>ID:</b> {pay['id']}\n"
            f"👤 <b>Foydalanuvchi:</b> {name}\n"
            f"🆔 <b>User ID:</b> {pay['user_id']}\n"
            f"💳 <b>Summa:</b> {pay['amount']} so'm\n"
            f"💳 <b>Karta:</b> {pay.get('card_number', '')}\n"
            f"⏳ <b>Holat:</b> {pay.get('status', 'pending')}"
        )
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('👁 Chekni ko\'rish', callback_data=f'pro_pay_view_{pay["id"]}'),
            InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'pro_pay_approve_{pay["id"]}'),
            InlineKeyboardButton('❌ Rad etish', callback_data=f'pro_pay_reject_{pay["id"]}')
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🚀 Startaplar' and is_admin_user(message.chat.id))
def admin_startups_menu(message):
    stats = get_statistics()
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('⏳ Kutilayotgan', callback_data='pending_startups_1'),
        InlineKeyboardButton('▶️ Faol', callback_data='active_startups_1'),
        InlineKeyboardButton('✅ Yakunlangan', callback_data='completed_startups_1'),
        InlineKeyboardButton('❌ Rad etilgan', callback_data='rejected_startups_1'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    text = (
        f"🚀 <b>Startaplar boshqaruvi</b>\n\n"
        f"📊 <b>Statistikalar:</b>\n"
        f" ⏳ Kutilayotgan: <b>{stats['pending_startups']}</b>\n"
        f" ▶️ Faol: <b>{stats['active_startups']}</b>\n"
        f" ✅ Yakunlangan: <b>{stats['completed_startups']}</b>\n"
        f" ❌ Rad etilgan: <b>{stats['rejected_startups']}</b>"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pending_startups_'))
def show_pending_startups(call):
    if not is_admin_user(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    page = int(call.data.split('_')[2])
    startups, total = get_pending_startups(page)
    
    if not startups:
        text = "⏳ <b>Kutilayotgan startaplar yo'q.</b>"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_startups'))
    else:
        total_pages = max(1, (total + 4) // 5)
        text = f"⏳ <b>Kutilayotgan startaplar</b>\n\n"
        
        for i, startup in enumerate(startups, start=(page-1)*5+1):
            user = get_user(startup['owner_id'])
            owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
            
            text += f"{i}. <b>{startup['name']}</b> – {owner_name}\n\n"
        
        markup = InlineKeyboardMarkup()
        
        # Sahifa navigatsiyasi
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton('◀️ Oldingi', callback_data=f'pending_startups_{page-1}'))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton('Keyingi ▶️', callback_data=f'pending_startups_{page+1}'))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        # Startup tanlash
        for i, startup in enumerate(startups):
            startup_name_short = startup['name'][:20] + '...' if len(startup['name']) > 20 else startup['name']
            markup.add(InlineKeyboardButton(f'{i+1}. {startup_name_short}', 
                                           callback_data=f'admin_view_startup_{startup["_id"]}'))
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_startups'))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_view_startup_'))
def admin_view_startup_details(call):
    if not is_admin_user(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    try:
        startup_id = call.data.split('_')[3]
        startup = get_startup(startup_id)
        
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        owner_contact = f"@{user.get('username', '')}" if user and user.get('username') else f"ID: {startup['owner_id']}"
        
        text = (
            f"🖼 <b>Startup ma'lumotlari</b>\n\n"
            f"🎯 <b>Nomi:</b> {startup['name']}\n"
            f"📌 <b>Tavsif:</b> {startup['description']}\n\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"📱 <b>Aloqa:</b> {owner_contact}\n"
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerak:</b> {startup.get('required_skills', '—')}\n"
            f"👥 <b>Maksimal a'zolar:</b> {startup.get('max_members', '—')}\n"
            f"🔗 <b>Guruh havolasi:</b> {startup['group_link']}\n"
            f"📅 <b>Yaratilgan sana:</b> {startup.get('created_at', '—')[:10]}\n"
            f"📊 <b>Holati:</b> {startup['status']}"
        )
        
        markup = InlineKeyboardMarkup()
        
        if startup['status'] == 'pending':
            markup.add(
                InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'admin_approve_{startup_id}'),
                InlineKeyboardButton('❌ Rad etish', callback_data=f'admin_reject_{startup_id}')
            )
        elif startup['status'] == 'active':
            markup.add(InlineKeyboardButton('✅ Faol', callback_data='already_active'))
        elif startup['status'] == 'completed':
            markup.add(InlineKeyboardButton('✅ Yakunlangan', callback_data='already_completed'))
        elif startup['status'] == 'rejected':
            markup.add(InlineKeyboardButton('❌ Rad etilgan', callback_data='already_rejected'))
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='pending_startups_1'))
        
        try:
            if startup.get('logo'):
                bot.edit_message_media(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    media=types.InputMediaPhoto(startup['logo'], caption=text),
                    reply_markup=markup
                )
            else:
                bot.edit_message_text(
                    text=text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=markup
                )
        except:
            if startup.get('logo'):
                bot.send_photo(call.message.chat.id, startup['logo'], caption=text, reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, text, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Admin view startup xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_approve_'))
def admin_approve_startup(call):
    if not is_admin_user(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    try:
        startup_id = call.data.split('_')[2]
        
        # Startup holatini yangilash
        update_startup_status(startup_id, 'active')
        
        startup = get_startup(startup_id)
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        # Egaga xabar
        try:
            bot.send_message(
                startup['owner_id'],
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"✅ '<b>{startup['name']}</b>' startupingiz tasdiqlandi va kanalga joylandi!"
            )
        except:
            pass
        
        # Kanalga post joylash
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        
        channel_text = (
            f"🚀 <b>{startup['name']}</b>\n\n"
            f"📝 {startup['description']}\n\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerakli mutaxassislar:</b>\n{startup.get('required_skills', '—')}\n\n"
            f"👥 <b>A'zolar:</b> 0 / {startup.get('max_members', '—')}\n\n"
            f"➕ <b>O'z startupingizni yaratish uchun:</b> @{bot.get_me().username}"
        )
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🤝 Startupga qo\'shilish', callback_data=f'join_startup_{startup_id}'))
        
        try:
            if startup.get('logo'):
                sent_message = bot.send_photo(CHANNEL_USERNAME, startup['logo'], caption=channel_text, reply_markup=markup)
            else:
                sent_message = bot.send_message(CHANNEL_USERNAME, channel_text, reply_markup=markup)
            
            # Post ID sini saqlash
            update_startup_post_id(startup_id, sent_message.message_id)
            
        except Exception as e:
            logging.error(f"Kanalga post yuborishda xatolik: {e}")
        
        bot.answer_callback_query(call.id, "✅ Startup tasdiqlandi!")
        
        # Kutilayotgan startaplarga qaytish
        show_pending_startups(call)
        
    except Exception as e:
        logging.error(f"Admin approve xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_reject_'))
def admin_reject_startup(call):
    if not is_admin_user(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    try:
        startup_id = call.data.split('_')[2]
        update_startup_status(startup_id, 'rejected')
        
        # Egaga xabar
        startup = get_startup(startup_id)
        if startup:
            try:
                bot.send_message(
                    startup['owner_id'],
                    f"❌ <b>Xabar!</b>\n\n"
                    f"Sizning '<b>{startup['name']}</b>' startupingiz rad etildi."
                )
            except:
                pass
        
        bot.answer_callback_query(call.id, "❌ Startup rad etildi!")
        
        # Kutilayotgan startaplarga qaytish
        show_pending_startups(call)
        
    except Exception as e:
        logging.error(f"Admin reject xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.message_handler(func=lambda message: message.text == '👥 Foydalanuvchilar' and is_admin_user(message.chat.id))
def admin_users(message):
    stats = get_statistics()
    recent_users = get_recent_users(10)
    
    text = (
        f"👥 <b>Foydalanuvchilar boshqaruvi</b>\n\n"
        f"📊 <b>Umumiy foydalanuvchilar:</b> <b>{stats['total_users']}</b> ta\n\n"
        f"📋 <b>So'nggi foydalanuvchilar:</b>\n"
    )
    
    for i, user in enumerate(recent_users, 1):
        joined_date = user.get('joined_at', '—')
        if joined_date and joined_date != '—':
            try:
                if isinstance(joined_date, str):
                    joined_date = joined_date[:10]
            except:
                pass
        
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        if not name:
            name = "Noma'lum"
        
        text += f"{i}. <b>{name}</b>\n"
        text += f"   👤 @{user.get('username', '—')} | 📅 {joined_date}\n\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('📥 Foydalanuvchilar ro\'yxati', callback_data='users_list_1'),
        InlineKeyboardButton('📊 Statistika', callback_data='users_stats'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📢 Xabar yuborish' and is_admin_user(message.chat.id))
def broadcast_message_start(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'broadcasting_message')
    
    msg = bot.send_message(message.chat.id, 
                          "📢 <b>Xabaringizni yozing:</b>\n\n"
                          "<i>Barcha foydalanuvchilarga yuboriladi.</i>",
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        admin_panel(message)
        return
    
    text = escape_html(message.text)
    users = get_all_users()
    
    bot.send_message(message.chat.id, f"📤 <b>Xabar yuborilmoqda...</b>\n\nFoydalanuvchilar: {len(users)} ta")
    
    success = 0
    fail = 0
    
    for user in users:
        try:
            # Xabar turini tekshirish
            if message.photo:
                bot.send_photo(user, message.photo[-1].file_id, caption=text if text else None)
            elif message.video:
                bot.send_video(user, message.video.file_id, caption=text if text else None)
            elif message.document:
                bot.send_document(user, message.document.file_id, caption=text if text else None)
            else:
                bot.send_message(user, f"📢 <b>Yangilik!</b>\n\n{text}")
            
            success += 1
            time.sleep(0.05)  # Flood limitdan qochish uchun
        except Exception as e:
            fail += 1
    
    bot.send_message(
        message.chat.id,
        f"✅ <b>Xabar yuborish yakunlandi!</b>\n\n"
        f"✅ Yuborildi: {success} ta\n"
        f"❌ Yuborilmadi: {fail} ta\n\n"
        f"📊 Umumiy foiz: {success/(success+fail)*100:.1f}%"
    )
    
    clear_user_state(message.from_user.id)
    admin_panel(message)

# 📍 CALLBACK HANDLERLAR
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_admin_panel')
def handle_back_to_admin_panel(call):
    admin_panel(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_admin_startups')
def handle_back_to_admin_startups(call):
    admin_startups_menu(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'refresh_dashboard')
def handle_refresh_dashboard(call):
    admin_dashboard(call.message)
    bot.answer_callback_query(call.id, "🔄 Dashboard yangilandi!")

@bot.callback_query_handler(func=lambda call: call.data == 'full_stats')
def handle_full_stats(call):
    stats = get_statistics()
    bot.answer_callback_query(call.id, 
                             f"👥 Foydalanuvchilar: {stats['total_users']}\n"
                             f"🚀 Startaplar: {stats['total_startups']}\n"
                             f"⏳ Kutilayotgan: {stats['pending_startups']}\n"
                             f"▶️ Faol: {stats['active_startups']}\n"
                             f"✅ Yakunlangan: {stats['completed_startups']}\n"
                             f"❌ Rad etilgan: {stats['rejected_startups']}", 
                             show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'users_list_1')
def handle_users_list(call):
    bot.answer_callback_query(call.id, "⏳ Foydalanuvchilar ro'yxati tuzilmoqda...")

@bot.callback_query_handler(func=lambda call: call.data == 'users_stats')
def handle_users_stats(call):
    stats = get_statistics()
    bot.answer_callback_query(call.id, 
                             f"👥 Foydalanuvchilar: {stats['total_users']}\n"
                             f"🚀 Startaplar: {stats['total_startups']}", 
                             show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'pro_toggle')
def handle_pro_toggle(call):
    if not is_admin_user(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    settings = get_pro_settings()
    enabled = bool(settings.get('pro_enabled', 0))
    set_pro_enabled(not enabled)
    bot.answer_callback_query(call.id, "✅ Yangilandi")
    admin_pro_settings(call.message)

@bot.callback_query_handler(func=lambda call: call.data == 'pro_edit_price')
def handle_pro_edit_price(call):
    if not is_admin_user(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    set_user_state(call.from_user.id, 'admin_edit_pro_price')
    msg = bot.send_message(call.message.chat.id, "💳 <b>Yangi narxni kiriting (faqat raqam):</b>", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_admin_pro_price)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'pro_edit_card')
def handle_pro_edit_card(call):
    if not is_admin_user(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    set_user_state(call.from_user.id, 'admin_edit_pro_card')
    msg = bot.send_message(call.message.chat.id, "💳 <b>Yangi karta raqamini kiriting:</b>", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_admin_pro_card)
    bot.answer_callback_query(call.id)

def process_admin_pro_price(message):
    user_id = message.from_user.id
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        admin_pro_settings(message)
        return
    try:
        price = int(''.join(ch for ch in message.text if ch.isdigit()))
        if price <= 0:
            raise ValueError
    except Exception:
        msg = bot.send_message(message.chat.id, "❌ <b>Noto'g'ri qiymat.</b>\n\nQayta kiriting:", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_admin_pro_price)
        return
    set_pro_price(price)
    clear_user_state(user_id)
    bot.send_message(message.chat.id, "✅ <b>Narx yangilandi.</b>")
    admin_pro_settings(message)

def process_admin_pro_card(message):
    user_id = message.from_user.id
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        admin_pro_settings(message)
        return
    card = (message.text or '').strip()
    if not card:
        msg = bot.send_message(message.chat.id, "❌ <b>Karta raqami bo'sh.</b>\n\nQayta kiriting:", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_admin_pro_card)
        return
    set_pro_card(card)
    clear_user_state(user_id)
    bot.send_message(message.chat.id, "✅ <b>Karta raqami yangilandi.</b>")
    admin_pro_settings(message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pro_pay_view_'))
def handle_pro_pay_view(call):
    if not is_admin_user(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    try:
        payment_id = int(call.data.split('_')[-1])
        payment = get_payment(payment_id)
        if not payment:
            bot.answer_callback_query(call.id, "To'lov topilmadi", show_alert=True)
            return
        receipt_id = payment.get('receipt_file_id')
        if not receipt_id:
            bot.answer_callback_query(call.id, "Chek topilmadi", show_alert=True)
            return
        user = get_user(payment['user_id']) or {}
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Noma'lum"
        text = (
            "🧾 <b>Pro to'lov cheki</b>\n\n"
            f"🧾 <b>ID:</b> {payment['id']}\n"
            f"👤 <b>Foydalanuvchi:</b> {name}\n"
            f"🆔 <b>User ID:</b> {payment['user_id']}\n"
            f"💳 <b>Summa:</b> {payment['amount']} so'm\n"
            f"💳 <b>Karta:</b> {payment.get('card_number', '')}\n"
            f"⏳ <b>Holat:</b> {payment.get('status', 'pending')}"
        )
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'pro_pay_approve_{payment_id}'),
            InlineKeyboardButton('❌ Rad etish', callback_data=f'pro_pay_reject_{payment_id}')
        )
        bot.send_photo(call.message.chat.id, receipt_id, caption=text, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"pro_pay_view xatosi: {e}")
        bot.answer_callback_query(call.id, "Xatolik", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pro_pay_approve_'))
def handle_pro_pay_approve(call):
    if not is_admin_user(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    try:
        payment_id = int(call.data.split('_')[-1])
        payment = get_payment(payment_id)
        if not payment or payment.get('status') != 'pending':
            bot.answer_callback_query(call.id, "To'lov topilmadi yoki tasdiqlangan", show_alert=True)
            return
        update_payment_status(payment_id, 'approved')
        sub = add_pro_subscription(payment['user_id'], months=1, source='payment', note=f'payment_id:{payment_id}')
        end_at = sub.get('end_at', '')[:10] if sub else ''
        try:
            bot.send_message(
                payment['user_id'],
                "✅ <b>Pro obuna tasdiqlandi!</b>\n\n"
                f"Tugash sanasi: <b>{end_at or 'N/A'}</b>"
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "✅ Tasdiqlandi")
    except Exception as e:
        logging.error(f"pro_pay_approve xatosi: {e}")
        bot.answer_callback_query(call.id, "Xatolik", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pro_pay_reject_'))
def handle_pro_pay_reject(call):
    if not is_admin_user(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    try:
        payment_id = int(call.data.split('_')[-1])
        payment = get_payment(payment_id)
        if not payment or payment.get('status') != 'pending':
            bot.answer_callback_query(call.id, "To'lov topilmadi yoki qayta ishlangan", show_alert=True)
            return
        update_payment_status(payment_id, 'rejected')
        try:
            bot.send_message(
                payment['user_id'],
                "❌ <b>Pro to'lovingiz rad etildi.</b>\n\n"
                "Iltimos, to'lovni tekshirib qayta yuboring."
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "❌ Rad etildi")
    except Exception as e:
        logging.error(f"pro_pay_reject xatosi: {e}")
        bot.answer_callback_query(call.id, "Xatolik", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main_menu')
def handle_back_to_main_menu(call):
    show_main_menu(call)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_startups_menu')
def handle_back_to_startups_menu(call):
    user_id = call.from_user.id
    set_user_state(user_id, 'in_startups_menu')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('🎯 Tavsiyalar'),
        KeyboardButton('🔎 Kategoriya bo\'yicha'),
        KeyboardButton('🏠 Asosiy menyu')
    )
    
    try:
        bot.edit_message_text(
            "🌐 <b>Startaplar bo'limi:</b>\n\nKerakli bo'limni tanlang:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(call.message.chat.id, "🌐 <b>Startaplar bo'limi:</b>\n\nKerakli bo'limni tanlang:", reply_markup=markup)
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_categories')
def handle_back_to_categories(call):
    user_id = call.from_user.id
    set_user_state(user_id, 'choosing_category')
    
    categories = get_all_categories()
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    if categories:
        for category in categories:
            category_emojis = {
                'Biznes': '💼',
                'Sog\'liq': '🏥',
                'Texnologiya': '📱',
                'Ekologiya': '🌿',
                'Ta\'lim': '🎓',
                'Dizayn': '🎨',
                'Dasturlash': '💻',
                'Savdo': '🛒',
                'Media': '🎬',
                'Karyera': '💼'
            }
            emoji = category_emojis.get(category, '🏷️')
            markup.add(InlineKeyboardButton(f'{emoji} {category}', callback_data=f'category_{category}'))
    else:
        markup.add(InlineKeyboardButton('💼 Biznes', callback_data='category_Biznes'))
        markup.add(InlineKeyboardButton('🏥 Sog\'liq', callback_data='category_Sog\'liq'))
        markup.add(InlineKeyboardButton('📱 Texnologiya', callback_data='category_Texnologiya'))
        markup.add(InlineKeyboardButton('🌿 Ekologiya', callback_data='category_Ekologiya'))
        markup.add(InlineKeyboardButton('🎓 Ta\'lim', callback_data='category_Ta\'lim'))
        markup.add(InlineKeyboardButton('🎨 Dizayn', callback_data='category_Dizayn'))
        markup.add(InlineKeyboardButton('💻 Dasturlash', callback_data='category_Dasturlash'))
        markup.add(InlineKeyboardButton('🛒 Savdo', callback_data='category_Savdo'))
        markup.add(InlineKeyboardButton('🎬 Media', callback_data='category_Media'))
        markup.add(InlineKeyboardButton('💼 Karyera', callback_data='category_Karyera'))
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_startups_menu'))
    
    try:
        bot.edit_message_text(
            "🏷️ <b>Kategoriya tanlang:</b>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(call.message.chat.id, "🏷️ <b>Kategoriya tanlang:</b>", reply_markup=markup)
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_my_startups')
def handle_back_to_my_startups(call):
    user_id = call.from_user.id
    set_user_state(user_id, 'in_my_startups')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('📋 Mening startaplarim'),
        KeyboardButton('🤝 Qo\'shilgan startaplar'),
        KeyboardButton('🏠 Asosiy menyu')
    )
    
    try:
        bot.edit_message_text(
            "📌 <b>Startaplarim bo'limi:</b>\n\nKerakli bo'limni tanlang:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(call.message.chat.id, "📌 <b>Startaplarim bo'limi:</b>\n\nKerakli bo'limni tanlang:", reply_markup=markup)
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_my_startups_list')
def handle_back_to_my_startups_list(call):
    user_id = call.from_user.id
    show_my_startups_page(call.message.chat.id, user_id, 1, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('back_to_my_startup_'))
def handle_back_to_my_startup(call):
    try:
        startup_id = call.data.split('_')[4]
        user_id = call.from_user.id
        startups = get_startups_by_owner(user_id)
        
        # Startupni topish
        for idx, startup in enumerate(startups):
            if startup['_id'] == startup_id:
                view_my_startup_details(call.message.chat.id, user_id, startup, call.message.message_id)
                break
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Back to my startup error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data in ['already_active', 'already_completed', 'already_rejected', 
                                                          'rejected_info', 'waiting_approval', 'current_page',
                                                          'view_results_'])
def handle_info_callbacks(call):
    bot.answer_callback_query(call.id)

# 🔙 ORQAGA TUGMASI UCHUN HANDLER
@bot.message_handler(func=lambda message: message.text == '🔙 Orqaga')
def handle_back_button(message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if user_state.startswith('editing_') or user_state == 'waiting_phone_edit':
        # Profil tahrirlashdan orqaga
        clear_user_state(user_id)
        show_profile(message)
    
    elif user_state in ['in_startups_menu', 'viewing_recommended', 'choosing_category']:
        # Startaplar bo'limidan orqaga
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state == 'waiting_phone':
        # Telefon kiritishdan orqaga
        clear_user_state(user_id)
        show_main_menu(message)

    elif user_state == 'waiting_pro_receipt':
        # Pro to'lovdan orqaga
        clear_user_state(user_id)
        pro_payment_data.pop(user_id, None)
        show_main_menu(message)
    
    elif user_state == 'creating_startup' or user_state == 'creating_startup_logo':
        # Startup yaratishdan orqaga
        clear_user_data(user_id)
        show_main_menu(message)
    
    elif user_state.startswith('completing_startup_'):
        # Startup yakunlashdan orqaga
        clear_user_state(user_id)
        # Startup ko'rinishiga qaytish
        startup_id = user_state.split('_')[2]
        startups = get_startups_by_owner(user_id)
        for startup in startups:
            if startup['_id'] == startup_id:
                view_my_startup_details(message.chat.id, user_id, startup)
                break
    
    elif user_state == 'in_my_startups':
        # Startaplarim bo'limidan orqaga
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state == 'in_admin_panel' or user_state == 'broadcasting_message':
        # Admin panelidan orqaga
        clear_user_state(user_id)
        show_main_menu(message)

    elif user_state in ['admin_edit_pro_price', 'admin_edit_pro_card']:
        clear_user_state(user_id)
        admin_pro_settings(message)
    
    elif user_state == 'in_profile':
        # Profildan orqaga
        clear_user_state(user_id)
        show_main_menu(message)
    
    else:
        # Boshqa hollarda asosiy menyuga qaytish
        clear_user_state(user_id)
        show_main_menu(message)

@bot.message_handler(func=lambda message: message.text == '🏠 Asosiy menyu')
def handle_main_menu_button(message):
    user_id = message.from_user.id
    clear_user_data(user_id)
    pro_payment_data.pop(user_id, None)
    show_main_menu(message)

# BARCHA XABARLARNI QAYTA ISHLASH
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        user_id = message.from_user.id

        if get_user_state(user_id) == 'waiting_pro_receipt':
            bot.send_message(
                message.chat.id,
                "🧾 <b>Iltimos, chek rasmini yuboring.</b>\n\n"
                "Agar to'lov qilmagan bo'lsangiz, avval to'lovni amalga oshiring."
            )
            return
        
        # Agar admin bo'lsa
        if is_admin_user(user_id):
            # Admin menyusi tugmalari allaqachon handlerlari bor
            return
        
        # Agar asosiy menyu tugmalaridan biri bosilsa
        if message.text in ['🌐 Startaplar', '🚀 Startup yaratish', '📌 Startaplarim', '👤 Profil', '💳 Obuna', '🤝 Referal']:
            return
        
        # Boshqa hollarda asosiy menyuni ko'rsatish
        show_main_menu(message)
        
    except Exception as e:
        logging.error(f"Umumiy xabar qayta ishlash xatosi: {e}")
        bot.send_message(message.chat.id, "⚠️ <b>Xatolik yuz berdi!</b>\n\nIltimos, /start buyrug'ini yuboring.", reply_markup=create_back_button())

# 📍 KANAL POSTLARINI YANGILASH FUNKSIYASI
def update_channel_post(startup_id: str):
    try:
        startup = get_startup(startup_id)
        if not startup:
            return False
        
        post_id = startup.get('channel_post_id')
        if not post_id:
            return False
        
        # A'zolar sonini olish
        current_members = get_startup_member_count(startup_id)
        max_members = startup.get('max_members', 10)
        
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        
        # POST MATNI - HTML formatida
        channel_text = (
            f"🚀 <b>{startup['name']}</b>\n\n"
            f"📝 {startup['description']}\n\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerakli mutaxassislar:</b>\n{startup.get('required_skills', '—')}\n\n"
            f"👥 <b>A'zolar:</b> {current_members} / {max_members}\n\n"
        )
        
        # Agar a'zolar to'liq bo'lsa
        if current_members >= max_members:
            channel_text += f"❌ <b>Startup to'ldi, yangi a'zolar qabul qilinmaydi.</b>\n\n"
        else:
            channel_text += (
                f"➕ <b>O'z startupingizni yaratish uchun:</b> @{bot.get_me().username}"
            )
        
        markup = InlineKeyboardMarkup()
        if current_members < max_members:
            markup.add(InlineKeyboardButton('🤝 Startupga qo\'shilish', callback_data=f'join_startup_{startup_id}'))
        else:
            markup.add(InlineKeyboardButton('❌ A\'zolar to\'ldi', callback_data='full_members'))
        
        try:
            # Postni tahrirlash
            if startup.get('logo'):
                bot.edit_message_caption(
                    chat_id=CHANNEL_USERNAME,
                    message_id=post_id,
                    caption=channel_text,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            else:
                bot.edit_message_text(
                    text=channel_text,
                    chat_id=CHANNEL_USERNAME,
                    message_id=post_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            
            # A'zolar sonini yangilash
            update_startup_current_members(startup_id, current_members)
            
            return True
        except Exception as e:
            logging.error(f"Postni yangilashda xatolik: {e}")
            return False
    except Exception as e:
        logging.error(f"Update channel post xatosi: {e}")
        return False

# BOTNI ISHGA TUSHIRISH
if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 GarajHub Bot ishga tushdi...")
    print(f"👨‍💼 Admin IDs: {', '.join(str(x) for x in sorted(ADMIN_IDS))}")
    print(f"📢 Kanal: {CHANNEL_USERNAME}")
    try:
        bot_info = bot.get_me()
        print(f"🤖 Bot: @{bot_info.username}")
    except:
        print("🤖 Bot: (get_me() failed)")
    print("🗄️ Database: MongoDB")
    print("=" * 60)
    
    while True:
        try:
            try:
                bot.remove_webhook()
            except:
                pass
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except apihelper.ApiTelegramException as e:
            if hasattr(e, 'result_json') and isinstance(e.result_json, dict) and e.result_json.get('error_code') == 409 or '409' in str(e):
                logging.error(f"Telegram 409 conflict: {e}. Removing webhook and retrying...")
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

