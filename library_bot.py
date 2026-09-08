import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

TOKEN = '8731972267:AAECE78u7mUK_50ONzuXD2i7e5DwpxKHDyo'       # <--- امسح هذه الجملة وحط مكانها توكن البوت بين علامتي التنصيص
ADMIN_ID = 8860900391             # <--- امسح هذه الأرقام وحط مكانها رقم الآيدي الشخصي الخاص بك

bot = telebot.TeleBot(TOKEN)

# --- إعداد قاعدة البيانات الهرمية الذكية ---
conn = sqlite3.connect('mega_library.db', check_same_thread=False)
cursor = conn.cursor()

# 1. جدول الأقسام والفروع (شجري متفرع: قسم رئيسي، مادة، تصنيف فرعي)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        parent_id INTEGER DEFAULT 0
    )
''')

# 2. جدول الملفات والنماذج المتراكمة (كل ملف يتبع لقسم معين ويبقى للأبد)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        file_name TEXT,
        file_id TEXT,
        file_type TEXT
    )
''')
conn.commit()

admin_states = {}

# --- دالة عرض القائمة (تتعامل مع الهيكل الشجري ديناميكياً) ---
def get_menu_markup(cat_id, user_id):
    markup = InlineKeyboardMarkup(row_width=1)
    
    cursor.execute("SELECT id, name FROM categories WHERE parent_id = ?", (cat_id,))
    sub_cats = cursor.fetchall()
    for sub_id, sub_name in sub_cats:
        markup.add(InlineKeyboardButton(f"📁 {sub_name}", callback_data=f"cat_{sub_id}"))
        
    cursor.execute("SELECT id, file_name FROM files WHERE category_id = ?", (cat_id,))
    cat_files = cursor.fetchall()
    for f_id, f_name in cat_files:
        markup.add(InlineKeyboardButton(f"📄 {f_name}", callback_data=f"getfile_{f_id}"))
        
    if user_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("➕ إضافة قسم فرعي هنا", callback_data=f"addcat_{cat_id}"))
        if cat_id != 0:
            markup.add(InlineKeyboardButton("📤 إضافة ملف/نموذج جديد هنا", callback_data=f"addfile_{cat_id}"))

    if cat_id != 0:
        cursor.execute("SELECT parent_id FROM categories WHERE id = ?", (cat_id,))
        res = cursor.fetchone()
        parent = res[0] if res else 0
        markup.add(InlineKeyboardButton("🔙 رجوع للخلف", callback_data=f"cat_{parent}"))
    
    return markup

# --- بداية البوت (/start) ---
@bot.message_handler(commands=['start'])
def start_bot(message):
    markup = get_menu_markup(0, message.from_user.id)
    cursor.execute("SELECT COUNT(*) FROM categories WHERE parent_id = 0")
    if cursor.fetchone()[0] == 0 and message.from_user.id == ADMIN_ID:
        markup.add(InlineKeyboardButton("⭐ إنشاء أول قسم رئيسي (مثل: البكالوريا)", callback_data="add_main_cat"))
        
    bot.send_message(message.chat.id, "📚 **أهلاً بك في المكتبة التعليمية الشاملة**\nاختر القسم المناسب ترحيباً بك:", reply_markup=markup)

# --- معالجة الأزرار والتنقل الهرمي ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "add_main_cat" and user_id == ADMIN_ID:
        admin_states[user_id] = {'action': 'waiting_for_cat_name', 'parent_id': 0}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل الآن **اسم القسم الرئيسي الجديد** (مثلاً: قسم البكالوريا):")
        
    elif data.startswith("cat_"):
        cat_id = int(data.split("_")[1])
        markup = get_menu_markup(cat_id, user_id)
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📂 **مكتبة الملفات التعليمية**\nتفضل بتصفح الأقسام:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data.startswith("addcat_") and user_id == ADMIN_ID:
        target_parent = int(data.split("_")[1])
        admin_states[user_id] = {'action': 'waiting_for_cat_name', 'parent_id': target_parent}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل اسم القسم الفرعي الجديد (مثلاً: مادة الرياضيات، أو قسم النماذج):")
        
    elif data.startswith("addfile_") and user_id == ADMIN_ID:
        target_cat = int(data.split("_")[1])
        admin_states[user_id] = {'action': 'waiting_for_file_name', 'category_id': target_cat}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل الآن **اسم الملف أو النموذج** الذي سيظهر على الزر (مثلاً: نموذج حل إنجليزي):")
        
    elif data.startswith("getfile_"):
        file_db_id = data.split("_")[1]
        cursor.execute("SELECT file_id, file_type FROM files WHERE id = ?", (file_db_id,))
        f_data = cursor.fetchone()
        if f_data:
            f_id, f_type = f_data
            bot.answer_callback_query(call.id, "جاري إرسال الملف...")
            if f_type == 'document':
                bot.send_document(call.message.chat.id, f_id)
            elif f_type == 'photo':
                bot.send_photo(call.message.chat.id, f_id)
        else:
            bot.answer_callback_query(call.id, "عذراً، الملف غير موجود.")

# --- نظام استقبال رسائل المشرف ---
@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.from_user.id in admin_states)
def process_admin_inputs(message):
    user_id = message.from_user.id
    state_data = admin_states[user_id]
    action = state_data['action']
    
    if action == 'waiting_for_cat_name':
        parent_id = state_data['parent_id']
        cat_name = message.text
        cursor.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (cat_name, parent_id))
        conn.commit()
        del admin_states[user_id]
        bot.send_message(chat_id=message.chat.id, text=f"✅ تم إنشاء القسم (**{cat_name}**) بنجاح!\nأرسل /start لتحديث القائمة.")
        
    elif action == 'waiting_for_file_name':
        state_data['file_name'] = message.text
        state_data['action'] = 'waiting_for_file_document'
        bot.send_message(message.chat.id, f"ممتاز! اسم الملف هو: **{message.text}**.\nالآن **أرسل ملف الـ PDF أو الصورة**:")
        
    elif action == 'waiting_for_file_document':
        file_name = state_data['file_name']
        category_id = state_data['category_id']
        
        file_id = None
        file_type = 'text'
        
        if message.document:
            file_id = message.document.file_id
            file_type = 'document'
        elif message.photo:
            file_id = message.photo[-1].file_id
            file_type = 'photo'
        else:
            bot.send_message(message.chat.id, "⚠️ يرجى إرسال ملف (PDF أو صورة) حصراً.")
            return
            
        cursor.execute("INSERT INTO files (category_id, file_name, file_id, file_type) VALUES (?, ?, ?, ?)",
                       (category_id, file_name, file_id, file_type))
        conn.commit()
        
        del admin_states[user_id]
        bot.send_message(message.chat.id, f"🚀 تم رفع الملف (**{file_name}**) وإضافته بنجاح!\nاكتب /start لمشاهدته.")

bot.infinity_polling()
