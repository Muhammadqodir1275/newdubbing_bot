from dotenv import load_dotenv
import os
import telebot
from telebot import types
import json
import time
import glob

load_dotenv()

TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]
bot = telebot.TeleBot(TOKEN)

ANIME_FILE = "anime.json"
CHANNELS_FILE = "channels.json" 
user_states = {}

def load_json(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if file == "subscription.json":
            return {"price": 10000}
        return []
    except Exception as e:
        print(f"JSON faylini o'qishda xatolik: {e}")
        if file == "subscription.json":
            return {"price": 10000}
        return []

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_channels():
    return load_json(CHANNELS_FILE)

def save_channels(channels):
    save_json(CHANNELS_FILE, channels)

def is_subscribed(user_id, channel_username):
    try:
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        
        member = bot.get_chat_member(channel_username, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except Exception as e:
        print(f"Obuna tekshirishda xatolik: {e}")
        return False

def is_subscribed_user(user_id):
    subscriptions = load_json("subscriptions.json") or []
    current_time = time.time()
    
    for sub in subscriptions:
        if sub["user_id"] == user_id and sub["active"] and sub["end_date"] > current_time:
            return True
    return False

def check_subscription(user_id):
    channels = load_channels()
    not_subscribed = []
    
    for ch in channels:
        if not is_subscribed(user_id, ch["username"]):
            not_subscribed.append(ch)
    
    return not_subscribed

def is_admin(user_id):
    return user_id in ADMINS

def channels_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Kanal qo'shish", "❌ Kanal o'chirish")
    markup.add("📋 Kanallar ro'yxati", "🔙 Orqaga")
    bot.send_message(message.chat.id, "📡 Kanallar bo'limi:", reply_markup=markup)

def cleanup_unused_files():
    anime_list = load_json(ANIME_FILE)  
    used_files = []
    for a in anime_list:
        used_files.append(a["image"])
        for ep in a.get("episodes", []):
            used_files.append(ep["video"])

    videos_dir = os.path.join("uploads", "videos")
    if os.path.exists(videos_dir):
        for f in glob.glob(os.path.join(videos_dir, "*")):
            if os.path.basename(f) not in [os.path.basename(u) for u in used_files]:
                try:
                    os.remove(f)
                    print(f"❌ Keraksiz video o'chirildi: {f}")
                except Exception as e:
                    print(f"Video o'chirishda xatolik: {e}")
    
    images_dir = os.path.join("uploads", "images")
    if os.path.exists(images_dir):
        for f in glob.glob(os.path.join(images_dir, "*")):
            if os.path.basename(f) not in [os.path.basename(u) for u in used_files]:
                try:
                    os.remove(f)
                    print(f"❌ Keraksiz rasm o'chirildi: {f}")
                except Exception as e:
                    print(f"Rasm o'chirishda xatolik: {e}")

def set_subscription_price_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    if state["step"] == "set_price":
        try:
            price = int(message.text)
            save_json("subscription.json", {"price": price})
            bot.send_message(message.chat.id, f"✅ Obuna narxi {price} so'mga o'zgartirildi!")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Raqam kiriting.")
        finally:
            del user_states[user_id]
            subscription_menu(message)

def subscribe_user_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    if state["step"] == "user_id":
        try:
            subscriber_id = int(message.text)
            state["subscriber_id"] = subscriber_id
            state["step"] = "duration"
            bot.send_message(message.chat.id, "Obuna muddatini kunlarda kiriting (masalan: 30):")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Raqam raqamli ID kiriting.")
            del user_states[user_id]
            subscription_menu(message)
    elif state["step"] == "duration":
        try:
            duration = int(message.text)
            subscriber_id = state["subscriber_id"]
            subscriptions = load_json("subscriptions.json") or []
            new_subscription = {
                "user_id": subscriber_id,
                "start_date": time.time(),
                "end_date": time.time() + (duration * 24 * 60 * 60),
                "active": True
            }
            existing = next((s for s in subscriptions if s["user_id"] == subscriber_id), None)
            if existing:
                existing.update(new_subscription)
            else:
                subscriptions.append(new_subscription)
            save_json("subscriptions.json", subscriptions)
            bot.send_message(message.chat.id, f"✅ {subscriber_id} {duration} kunga obuna qilindi!")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Raqam kiriting.")
        finally:
            del user_states[user_id]
            subscription_menu(message)

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id

    if is_admin(user_id):
        admin_menu(message)
    else:
        user_menu(message)

def remove_admin_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]

    if state["step"] == "remove_admin_id":
        try:
            remove_id = int(message.text)
            if remove_id == OWNER_ID:
                bot.send_message(message.chat.id, "❌ Egasini o‘chirib bo‘lmaydi!")
            elif remove_id not in ADMINS:
                bot.send_message(message.chat.id, "❌ Bu foydalanuvchi admin emas!")
            else:
                ADMINS.remove(remove_id)
                bot.send_message(message.chat.id, f"✅ Admin o‘chirildi: {remove_id}")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Iltimos, faqat raqamli ID kiriting.")
        finally:
            if user_id in user_states:
                del user_states[user_id]

def admin_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Statistika", "🎬 Anime sozlash")
    markup.add("👨‍💻 Adminlar", "📡 Kanallar") 
    markup.add("💎 Obunani boshqarish")
    bot.send_message(message.chat.id, "🔐 Admin paneliga xush kelibsiz!", reply_markup=markup)

    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]

def adminlar_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Admin qo'shish", "❌ Admin o'chirish")
    markup.add("📋 Adminlar ro'yxati", "🔙 Orqaga")
    bot.send_message(message.chat.id, "👨‍💻 Adminlar bo'limi:", reply_markup=markup)


        
def anime_settings_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Anime qo'shish", "🎞 Qism qo'shish")
    markup.add("✏️ Tahrirlash", "🔙 Orqaga")
    bot.send_message(message.chat.id, "🎬 Anime sozlash bo'limi:", reply_markup=markup)
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]

def user_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Anime izlash", "📖 Qo'llanma")
    markup.add("📢 Reklama va homiylik")
    bot.send_message(message.chat.id, "👋 Salom! Quyidagi bo'limlardan birini tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video'])
def menu_handler(message):
    user_id = message.from_user.id

    if message.text == "🔙 Orqaga":
        if user_id in user_states:
            del user_states[user_id]
        if is_admin(user_id):
            admin_menu(message)
        else:
            user_menu(message)
        return

    if user_id in user_states:
        state = user_states[user_id]
        if "step_type" in state:
            if state["step_type"] == "user_search":
                if state.get("step") == "search" and message.content_type == "text":
                    user_search_steps(message)
                else:
                    bot.send_message(message.chat.id, "❗️ Jarayon tugamaguncha boshqa tugmani bosmang yoki '🔙 Orqaga' bosing.")
                return
            elif state["step_type"] == "edit_anime":
                edit_anime_steps(message)
                return
            elif state["step_type"] == "add_anime":
                if state.get("step") == "name":
                    bot.send_message(message.chat.id, "❗️ Jarayon tugamaguncha boshqa tugmani bosmang yoki '🔙 Orqaga' bosing.")
                else:
                    bot.send_message(message.chat.id, "❗️ Jarayon tugamaguncha boshqa tugmani bosmang yoki '🔙 Orqaga' bosing.")
                return
            elif state["step_type"] == "add_episode":
                bot.send_message(message.chat.id, "❗️ Jarayon tugamaguncha boshqa tugmani bosmang yoki '🔙 Orqaga' bosing.")
                return
            elif state["step_type"] == "delete_episode":
                bot.send_message(message.chat.id, "❗️ Jarayon tugamaguncha boshqa tugmani bosmang yoki '🔙 Orqaga' bosing.")
                return
            # Agar yuqoridagilardan hech biri bo'lmasa:
            bot.send_message(message.chat.id, "❗️ Jarayon tugamaguncha boshqa tugmani bosmang yoki '🔙 Orqaga' bosing.")
            return

    elif message.text == "➕ Admin qo'shish":
        if user_id != OWNER_ID: 
            bot.send_message(message.chat.id, "❌ Faqat egasi admin qo'sha oladi!")
            return
        bot.send_message(message.chat.id, "➕ Qo'shmoqchi bo'lgan foydalanuvchi ID sini yuboring:")
        user_states[user_id] = {"step": "add_admin_id", "step_type": "add_admin"}
        return

    elif message.text == "❌ Admin o'chirish":
        if user_id != OWNER_ID:
            bot.send_message(message.chat.id, "❌ Faqat egasi adminni o'chira oladi!")
            return
        try:
            bot.send_message(message.chat.id, "❌ O'chirmoqchi bo'lgan admin ID sini yuboring:")
            user_states[user_id] = {"step": "remove_admin_id", "step_type": "remove_admin"}
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
        return

    elif message.text == "➕ Foydalanuvchini obuna qilish":
        if not is_admin(user_id):
            bot.send_message(message.chat.id, "❌ Faqat adminlar obuna qila oladi!")
            return
        bot.send_message(message.chat.id, "Obuna qilmoqchi bo'lgan foydalanuvchi ID sini yuboring:")
        user_states[user_id] = {"step": "user_id", "step_type": "subscribe_user"}
        return

    if message.text == "🔍 Anime izlash":
        if not is_admin(user_id): 
            try:
                not_subscribed = check_subscription(user_id)
                if not_subscribed:
                    markup = types.InlineKeyboardMarkup()
                    for ch in not_subscribed:
                        markup.add(types.InlineKeyboardButton(f"📡 {ch['name']}", url=f"https://t.me/{ch['username'].replace('@', '')}"))
                    bot.send_message(message.chat.id, "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=markup)
                    return
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error checking subscription: {str(e)}")
                return
                
        bot.send_message(message.chat.id, "🔎 Anime nomi yoki ID sini kiriting:")
        user_states[user_id] = {"step": "search", "step_type": "user_search"}
        return

    elif message.text == "📖 Qo'llanma":
        text = (
            "📖 <b>Qo‘llanma: New Dubbing botidan foydalanish</b>\n\n"
            "1. <b>🔍 Anime izlash</b> — anime nomi yoki ID ni kiriting, rasm va qismlar chiqadi. \"⬇️ Yuklash\" tugmasi orqali barcha qismlarni yuklab olishingiz mumkin.\n"
            "2. <b>📢 Reklama va homiylik</b> — reklama yoki homiylik uchun admin bilan bog‘lanish yoki to‘lov qilish.\n"
            "3. <b>📖 Qo‘llanma</b> — ushbu yordam matni.\n\n"
            "ℹ️ <b>New Dubbing haqida</b>:\n"
            "Yangi ovozlangan animelar va qismlar to‘plami. Har bir anime uchun qismlar va videolar muntazam yangilanadi.\n"
            "Rasmiy kanal: t.me/NeW_TV_Rasmiy\n"
            "Admin: @MAXKAMOV_ADMIN1"
        )
        bot.send_message(message.chat.id, text, parse_mode="HTML")
        return

    elif message.text == "📢 Reklama va homiylik":
        if not is_admin(user_id):
            not_subscribed = check_subscription(user_id)
            if not_subscribed:
                markup = types.InlineKeyboardMarkup()
                for ch in not_subscribed:
                    markup.add(types.InlineKeyboardButton(f"📡 {ch['name']}", url=f"https://t.me/{ch['username'].replace('@', '')}"))
                bot.send_message(message.chat.id, "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=markup)
                return

        if is_subscribed_user(user_id) or is_admin(user_id):
            bot.send_message(message.chat.id, "📢 Reklama va homiylik uchun admin bilan bog'laning: @MAXKAMOV_ADMIN1")
        else:
            try:
                subscription_data = load_json("subscription.json")
                price = subscription_data.get("price", 10000)  # Default 10,000 so'm

                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("💳 To'lov qilish", callback_data="subscribe_payment")
                )
                bot.send_message(
                    message.chat.id, 
                    f"❗️ Reklama va homiylik uchun avval obuna bo'lishingiz kerak.\n\n💰 Obuna narxi: {price} so'm/oy", 
                    reply_markup=markup
                )
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Xatolik yuz berdi: {str(e)}")
        return

    if is_admin(user_id):
        if message.text == "🎬 Anime sozlash":
            anime_settings_menu(message)
        elif message.text == "👨‍💻 Adminlar":
            adminlar_menu(message)
        elif message.text == "➕ Anime qo'shish":
            bot.send_message(message.chat.id, "➕ Yangi anime nomini yuboring:")
            user_states[user_id] = {"step": "name", "step_type": "add_anime"}
        elif message.text == "🎞 Qism qo'shish":
            anime_list = load_json(ANIME_FILE)
            if not anime_list:
                bot.send_message(message.chat.id, "❌ Hozircha hech qanday anime mavjud emas.")
                return
            bot.send_message(message.chat.id, "Qism qo‘shish uchun anime ID yoki nomini yozing.")
            user_states[user_id] = {"step": "episode_anime", "step_type": "add_episode"}
            return
        elif message.text == "✏️ Tahrirlash":
            anime_list = load_json(ANIME_FILE)
            if not anime_list:
                bot.send_message(message.chat.id, "❌ Hozircha hech qanday anime mavjud emas.")
                return
            text = "🎬 Animelar ro‘yxati:\n\n"
            for a in anime_list:
                text += f"{a['id']}. {a['name']}\n"
            text += "\nTahrirlash uchun anime ID raqamini yozing."
            bot.send_message(message.chat.id, text)
            user_states[user_id] = {"step": "select_anime", "step_type": "edit_anime"}
            return
        elif message.text == "🔙 Orqaga":
            admin_menu(message)
        elif message.text == "📊 Statistika":
            anime_list = load_json(ANIME_FILE) or []
            channels = load_channels() or []
            subscriptions = load_json("subscriptions.json") or []
            
            current_time = time.time()
            active_subs = [s for s in subscriptions if s.get("active", False) and s.get("end_date", 0) > current_time]
            
            try:
                all_users = set()
                for user_id in user_states.keys():
                    all_users.add(user_id)
                for sub in subscriptions:
                    all_users.add(sub["user_id"])
                total_users = len(all_users)
            except Exception as e:
                total_users = 0
                print(f"Foydalanuvchilar sonini hisoblashda xatolik: {e}")
            
            stats_text = f"📊 Statistika:\n\n"
            stats_text += f"👥 Jami foydalanuvchilar: {total_users}\n"
            stats_text += f"🎬 Animelar soni: {len(anime_list)}\n"
            
            episodes_count = sum(len(a.get('episodes', [])) for a in anime_list)
            stats_text += f"🎞 Jami qismlar soni: {episodes_count}\n\n"
            
            stats_text += f"📡 Kanallar soni: {len(channels)}\n"
            stats_text += f"👨‍💻 Adminlar soni: {len(ADMINS)}\n"
            stats_text += f"💎 Aktiv obunalar soni: {len(active_subs)}\n"
            
            bot.send_message(message.chat.id, stats_text)
        elif message.text == "👨‍💻 Adminlar":
            adminlar_menu(message)
        elif message.text == "📡 Kanallar":
            channels_menu(message)
        elif message.text == "💎 Obunani boshqarish":
            subscription_menu(message)
            return
        elif message.text == "➕ Kanal qo'shish":
            bot.send_message(message.chat.id, "➕ Yangi kanal nomini yuboring:")
            user_states[user_id] = {"step": "channel_name", "step_type": "add_channel"}
        elif message.text == "❌ Kanal o'chirish":
            channels = load_channels()
            if not channels:
                bot.send_message(message.chat.id, "❌ Hozircha hech qanday kanal mavjud emas.")
                channels_menu(message)
                return
                
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for ch in channels:
                markup.add(f"{ch['name']} ({ch['username']})")
            markup.add("🔙 Orqaga")
            bot.send_message(message.chat.id, "❌ Qaysi kanal o'chirilsin?", reply_markup=markup)
            user_states[user_id] = {"step": "select_channel", "step_type": "remove_channel"}
        elif message.text == "📋 Kanallar ro'yxati":
            channels = load_channels()
            if not channels:
                bot.send_message(message.chat.id, "❌ Hozircha hech qanday kanal mavjud emas.")
            else:
                text = "📋 Kanallar ro'yxati:\n\n"
                for i, ch in enumerate(channels, 1):
                    text += f"{i}. {ch['name']} - {ch['username']}\n"
                bot.send_message(message.chat.id, text)
        elif message.text == "💰 Obuna narxini o'zgartirish":
            if user_id != OWNER_ID:
                bot.send_message(message.chat.id, "❌ Faqat egasi narxni o'zgartira oladi!")
                return
            bot.send_message(message.chat.id, "Yangi obuna narxini so'mda kiriting:")
            user_states[user_id] = {"step": "set_price", "step_type": "set_subscription_price"}
            return
        elif message.text == "📋 Adminlar ro'yxati":
            if not ADMINS:
                bot.send_message(message.chat.id, "❌ Hozircha hech qanday admin mavjud emas.")
            else:
                text = "📋 Adminlar ro'yxati:\n\n"
                for i, admin_id in enumerate(ADMINS, 1):
                    text += f"{i}. <code>{admin_id}</code>\n"
                bot.send_message(message.chat.id, text, parse_mode="HTML")
            return

def subscription_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Obuna narxini o'zgartirish", "➕ Foydalanuvchini obuna qilish")
    markup.add("📋 Obunalar ro'yxati", "🔙 Orqaga")
    bot.send_message(message.chat.id, "💎 Obuna boshqaruvi:", reply_markup=markup)

def set_subscription_price_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    if state["step"] == "set_price":
        try:
            price = int(message.text)
            save_json("subscription.json", {"price": price})
            bot.send_message(message.chat.id, f"✅ Obuna narxi {price} so'mga o'zgartirildi!")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Raqam kiriting.")
        finally:
            del user_states[user_id]
            subscription_menu(message)

def subscribe_user_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    if state["step"] == "user_id":
        try:
            subscriber_id = int(message.text)
            state["subscriber_id"] = subscriber_id
            state["step"] = "duration"
            bot.send_message(message.chat.id, "Obuna muddatini kunlarda kiriting (masalan: 30):")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Raqam kiriting.")
            del user_states[user_id]
            subscription_menu(message)
    elif state["step"] == "duration":
        try:
            duration = int(message.text)
            subscriber_id = state["subscriber_id"]
            subscriptions = load_json("subscriptions.json") or []
            new_subscription = {
                "user_id": subscriber_id,
                "start_date": time.time(),
                "end_date": time.time() + (duration * 24 * 60 * 60),
                "active": True
            }
            existing = next((s for s in subscriptions if s["user_id"] == subscriber_id), None)
            if existing:
                existing.update(new_subscription)
            else:
                subscriptions.append(new_subscription)
            save_json("subscriptions.json", subscriptions)
            bot.send_message(message.chat.id, f"✅ {subscriber_id} {duration} kunga obuna qilindi!")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Raqam kiriting.")
        finally:
            del user_states[user_id]
            subscription_menu(message)

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id

    if is_admin(user_id):
        admin_menu(message)
    else:
        user_menu(message)
def remove_admin_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]

    if state["step"] == "remove_admin_id":
        try:
            remove_id = int(message.text)
            if remove_id == OWNER_ID:
                bot.send_message(message.chat.id, "❌ Egasini o‘chirib bo‘lmaydi!")
            elif remove_id not in ADMINS:
                bot.send_message(message.chat.id, "❌ Bu foydalanuvchi admin emas!")
            else:
                ADMINS.remove(remove_id)
                bot.send_message(message.chat.id, f"✅ Admin o‘chirildi: {remove_id}")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Iltimos, faqat raqamli ID kiriting.")
        finally:
            if user_id in user_states:
                del user_states[user_id]
def admin_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Statistika", "🎬 Anime sozlash")
    markup.add("👨‍💻 Adminlar", "📡 Kanallar") 
    markup.add("💎 Obunani boshqarish")
    bot.send_message(message.chat.id, "🔐 Admin paneliga xush kelibsiz!", reply_markup=markup)


    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
def adminlar_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Admin qo'shish", "❌ Admin o'chirish")
    markup.add("📋 Adminlar ro'yxati", "🔙 Orqaga")
    bot.send_message(message.chat.id, "👨‍💻 Adminlar bo'limi:", reply_markup=markup)
def anime_settings_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Anime qo'shish", "🎞 Qism qo'shish")
    markup.add("✏️ Tahrirlash", "🔙 Orqaga")
    bot.send_message(message.chat.id, "🎬 Anime sozlash bo'limi:", reply_markup=markup)
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
def user_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Anime izlash", "📖 Qo'llanma")
    markup.add("📢 Reklama va homiylik")
    bot.send_message(message.chat.id, "👋 Salom! Quyidagi bo'limlardan birini tanlang:", reply_markup=markup)

def edit_anime_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    anime_list = load_json(ANIME_FILE)

    if state["step"] == "select_anime":
        query = message.text.strip().lower()
        anime = None
        try:
            anime_id = int(query)
            anime = next((a for a in anime_list if a["id"] == anime_id), None)
        except ValueError:
            anime = next((a for a in anime_list if query in a["name"].lower()), None)

        if anime:
            state["anime_id"] = anime["id"]
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
            markup.add("✏️ Sifatini o'zgartirish", "✏️ Janrini o'zgartirish")
            markup.add("✏️ Tilini o'zgartirish")
            markup.add("❌ Qismlar o'chirish")
            markup.add("❌ Animeni o'chirish")  # <-- Yangi tugma
            markup.add("🔙 Orqaga")
            bot.send_message(message.chat.id, f"{anime['name']} tahrirlash bo‘limi:", reply_markup=markup)
            state["step"] = "select_field"
        else:
            bot.send_message(message.chat.id, "❌ Bunday anime topilmadi. ID yoki nomini to‘g‘ri kiriting.")
        return

    elif state["step"] == "select_field":
        if message.text == "✏️ Nomini o'zgartirish":
            bot.send_message(message.chat.id, "Yangi nomini yuboring:")
            state["step"] = "edit_name"
            return
        elif message.text == "✏️ Rasmini o'zgartirish":
            bot.send_message(message.chat.id, "Yangi rasmni yuboring:")
            state["step"] = "edit_image"
            return
        elif message.text == "✏️ Sifatini o'zgartirish":
            bot.send_message(message.chat.id, "Yangi sifatini yuboring (masalan: 720, 1080):")
            state["step"] = "edit_quality"
            return
        elif message.text == "✏️ Janrini o'zgartirish":
            bot.send_message(message.chat.id, "Yangi janrini yuboring:")
            state["step"] = "edit_genre"
            return
        elif message.text == "✏️ Tilini o'zgartirish":
            bot.send_message(message.chat.id, "Yangi tilini yuboring:")
            state["step"] = "edit_language"
            return
        elif message.text == "❌ Animeni o'chirish":
            anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
            if anime:
                anime_list.remove(anime)
                save_json(ANIME_FILE, anime_list)
                bot.send_message(message.chat.id, "✅ Anime o'chirildi!")
            else:
                bot.send_message(message.chat.id, "❌ Anime topilmadi.")
            del user_states[user_id]
            anime_settings_menu(message)
            return
        elif message.text == "❌ Qismlar o'chirish":
            anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
            if anime and anime["episodes"]:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for ep in anime["episodes"]:
                    markup.add(f"{ep['number']}-qismni o'chirish")
                markup.add("🔙 Orqaga")
                bot.send_message(message.chat.id, f"{anime['name']} qismlari ({len(anime['episodes'])} ta): Qaysi qismni o'chirasiz?", reply_markup=markup)
                state["step"] = "delete_episode_number"
            else:
                bot.send_message(message.chat.id, "❌ Qismlar yo‘q.")
            return
        elif message.text == "🔙 Orqaga":
            del user_states[user_id]
            anime_settings_menu(message)
            return
        else:
            bot.send_message(message.chat.id, "❌ Tugmani tanlang.")
            return

    elif state["step"] == "episode_control":
        if message.text == "❌ Qismlar o'chirish":
            anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
            if anime and anime["episodes"]:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for ep in anime["episodes"]:
                    markup.add(f"{ep['number']}-qismni o'chirish")
                markup.add("🔙 Orqaga")
                bot.send_message(message.chat.id, f"{anime['name']} qismlari ({len(anime['episodes'])} ta): Qaysi qismni o'chirasiz?", reply_markup=markup)
                state["step"] = "delete_episode_number"
            else:
                bot.send_message(message.chat.id, "❌ Qismlar yo‘q.")
            return
        elif message.text == "🔙 Orqaga":
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
            markup.add("🎞 Qismlar boshqaruvi")
            markup.add("🔙 Orqaga")
            bot.send_message(message.chat.id, "Tahrirlash bo‘limi:", reply_markup=markup)
            state["step"] = "select_field"
            return

    # 4️⃣ Qismni o‘chirish
    elif state["step"] == "delete_episode_number":
        anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
        if message.text == "🔙 Orqaga":
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
            markup.add("🎞 Qismlar boshqaruvi")
            markup.add("🔙 Orqaga")
            bot.send_message(message.chat.id, "Tahrirlash bo‘limi:", reply_markup=markup)
            state["step"] = "select_field"
            return
        if anime:
            try:
                if message.text.endswith("o'chirish"):
                    episode_number = int(message.text.split("-")[0])
                    episode_index = next((i for i, ep in enumerate(anime["episodes"]) if ep["number"] == episode_number), None)
                    if episode_index is not None:
                        video_path = anime["episodes"][episode_index]["video"]
                        if os.path.exists(video_path):
                            os.remove(video_path)
                        del anime["episodes"][episode_index]
                        save_json(ANIME_FILE, anime_list)
                        bot.send_message(message.chat.id, f"✅ {anime['name']} uchun {episode_number}-qism o'chirildi!")
                    else:
                        bot.send_message(message.chat.id, "❌ Qism topilmadi.")
                else:
                    bot.send_message(message.chat.id, "❌ Tugmani to'g'ri tanlang.")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Xatolik: {e}")
        # Qayta qismlar boshqaruvi menyusiga qaytish
        anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
        if anime and anime["episodes"]:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for ep in anime["episodes"]:
                markup.add(f"{ep['number']}-qismni o'chirish")
            markup.add("🔙 Orqaga")
            bot.send_message(message.chat.id, f"{anime['name']} qismlari ({len(anime['episodes'])} ta): Qaysi qismni o'chirasiz?", reply_markup=markup)
            state["step"] = "delete_episode_number"
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
            markup.add("🎞 Qismlar boshqaruvi")
            markup.add("🔙 Orqaga")
            bot.send_message(message.chat.id, "Tahrirlash bo‘limi:", reply_markup=markup)
            state["step"] = "select_field"
        return
    elif state["step"] == "edit_image":
        if message.content_type == "photo":
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            images_dir = os.path.join("uploads", "images")
            os.makedirs(images_dir, exist_ok=True)
            file_path = os.path.join(images_dir, file_info.file_path.split('/')[-1])
            with open(file_path, "wb") as f:
                f.write(downloaded_file)
            anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
            if anime:
                anime["image"] = file_path
                save_json(ANIME_FILE, anime_list)
                bot.send_message(message.chat.id, "✅ Rasm yangilandi!")
            else:
                bot.send_message(message.chat.id, "❌ Anime topilmadi.")
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
            markup.add("🎞 Qismlar boshqaruvi")
            markup.add("🔙 Orqaga")
            bot.send_message(message.chat.id, "Tahrirlash bo‘limi:", reply_markup=markup)
            state["step"] = "select_field"
        else:
            bot.send_message(message.chat.id, "❌ Iltimos, rasm yuboring.")
        return
    elif state["step"] == "edit_quality":
        new_quality = message.text.strip()
        anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
        if anime:
            anime["quality"] = new_quality
            save_json(ANIME_FILE, anime_list)
            bot.send_message(message.chat.id, "✅ Sifat yangilandi!")
        else:
            bot.send_message(message.chat.id, "❌ Anime topilmadi.")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
        markup.add("✏️ Sifatini o'zgartirish", "✏️ Janrini o'zgartirish")
        markup.add("✏️ Tilini o'zgartirish")
        markup.add("❌ Qismlar o'chirish")
        markup.add("🔙 Orqaga")
        bot.send_message(message.chat.id, "Tahrirlash bo‘limi:", reply_markup=markup)
        state["step"] = "select_field"
        return

    elif state["step"] == "edit_genre":
        new_genre = message.text.strip()
        anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
        if anime:
            anime["genre"] = new_genre
            save_json(ANIME_FILE, anime_list)
            bot.send_message(message.chat.id, "✅ Janr yangilandi!")
        else:
            bot.send_message(message.chat.id, "❌ Anime topilmadi.")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
        markup.add("✏️ Sifatini o'zgartirish", "✏️ Janrini o'zgartirish")
        markup.add("✏️ Tilini o'zgartirish")
        markup.add("❌ Qismlar o'chirish")
        markup.add("🔙 Orqaga")
        bot.send_message(message.chat.id, "Tahrirlash bo‘limi:", reply_markup=markup)
        state["step"] = "select_field"
        return

    elif state["step"] == "edit_language":
        new_language = message.text.strip()
        anime = next((a for a in anime_list if a["id"] == state["anime_id"]), None)
        if anime:
            anime["language"] = new_language
            save_json(ANIME_FILE, anime_list)
            bot.send_message(message.chat.id, "✅ Til yangilandi!")
        else:
            bot.send_message(message.chat.id, "❌ Anime topilmadi.")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("✏️ Nomini o'zgartirish", "✏️ Rasmini o'zgartirish")
        markup.add("✏️ Sifatini o'zgartirish", "✏️ Janrini o'zgartirish")
        markup.add("✏️ Tilini o'zgartirish")
        markup.add("❌ Qismlar o'chirish")
        markup.add("🔙 Orqaga")
        bot.send_message(message.chat.id, "Tahrirlash bo‘limi:", reply_markup=markup)
        state["step"] = "select_field"
        return
def user_search_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    if state["step"] == "search":
        query = message.text.strip().lower()
        anime_list = load_json(ANIME_FILE)
        results = []
        for a in anime_list:
            if query in a["name"].lower() or query == str(a["id"]):
                results.append(a)
        if results:
            for a in results:
                caption = (
                    f"🎬 <b>{a['name']}</b>\n"
                    f"📺 Sifat: {a.get('quality','-')}\n"
                    f"🆔 ID: {a.get('id','-')}\n"
                    f"🗣 Til: {a.get('language','-')}\n"
                    f"🎭 Janr: {a.get('genre','-')}\n"
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton(
                        f"⬇️ Yuklash {len(a.get('episodes', []))} qism",
                        callback_data=f"download_all_{a['id']}"
                    )
                )
                if a.get("image") and os.path.exists(a["image"]):
                    with open(a["image"], "rb") as photo:
                        bot.send_photo(
                            message.chat.id,
                            photo,
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=markup
                        )
                else:
                    bot.send_message(
                        message.chat.id,
                        caption,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
            del user_states[user_id]
        else:
            bot.send_message(message.chat.id, "❌ Hech narsa topilmadi.")
            del user_states[user_id]
            user_menu(message)
        return
    else:
        bot.send_message(message.chat.id, "❗️ Jarayon tugamaguncha boshqa tugmani bosmang yoki '🔙 Orqaga' bosing.")
        return

@bot.message_handler(func=lambda m: m.text and m.text.startswith("⬇️ Yuklash "))
def download_all_episodes_handler(message):
    try:
        anime_id = int(message.text.replace("⬇️ Yuklash ", "").strip())
        anime_list = load_json(ANIME_FILE)
        anime = next((a for a in anime_list if a["id"] == anime_id), None)
        if anime and anime.get("episodes"):
            for ep in anime["episodes"]:
                ep_number = ep.get("number") or (anime["episodes"].index(ep) + 1)
                if os.path.exists(ep["video"]):
                    with open(ep["video"], "rb") as video:
                        bot.send_video(
                            message.chat.id,
                            video,
                            caption=f"{anime['name']} {ep_number}-qism"
                        )
                else:
                    bot.send_message(message.chat.id, f"{ep_number}-qism videosi topilmadi.")
        else:
            bot.send_message(message.chat.id, "❌ Qismlar topilmadi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "subscribe_payment")
def subscribe_payment_callback(call):
    bot.send_message(
        call.message.chat.id,
        "💳 To‘lov uchun karta raqami:\n\n<code>8600 1234 5678 9012</code>\n\nTo‘lovdan so‘ng admin: @MAXKAMOV_ADMIN1 ga yozing.",
        parse_mode="HTML"
    )


if __name__ == "__main__":
    print("Bot ishga tushdi!")
    bot.infinity_polling()