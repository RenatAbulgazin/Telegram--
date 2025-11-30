# bot_full_part2.py
import os
import sqlite3
import time
from telebot import TeleBot, types

# ========== CONFIG ==========
TOKEN = "8357748799:AAHvSYPeaAlC8beUAYNWlOv48yNGIxEWaV4"  
ADMIN_IDS = {1679367766}   
DATA_DIR = "data"
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)

bot = TeleBot(TOKEN)

# ========== DB ==========
conn = sqlite3.connect(os.path.join(DATA_DIR, "ecosystem.db"), check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS startups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER,
  name TEXT,
  description TEXT,
  contact TEXT,
  tg_username TEXT,
  photo_file_id TEXT,
  created_at INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS teams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER,
  name TEXT,
  members TEXT,
  project TEXT,
  contact TEXT,
  tg_username TEXT,
  created_at INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  email TEXT,
  phone TEXT,
  tg_username TEXT,
  created_at INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  date TEXT,
  time TEXT,
  goal TEXT,
  created_at INTEGER
)
""")
conn.commit()

# ========== State store ==========
# simple in-memory per-user state for multi-step flows
user_state = {}

def set_state(user_id, key, value):
    user_state.setdefault(user_id, {})[key] = value

def get_state(user_id, key, default=None):
    return user_state.get(user_id, {}).get(key, default)

def clear_state(user_id):
    user_state.pop(user_id, None)

# ========== Keyboards ==========
def start_screen_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("Start", "Help")
    return kb

def main_menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎯 Стартапы", "👥 Команды")
    kb.row("📰 Новости", "ℹ️ О нас")
    kb.row("📅 События", "📞 Контакты")
    kb.row("➕ Регистрация Стартапа", "➕ Регистрация Команды")
    kb.row("➕ Добавить событие", "📤 Экспорт данных")
    kb.row("🔧 Админ: редактирование")
    return kb

def cancel_kb(label="Отмена"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(label)
    return kb

# ========== Utils ==========
def now_ts():
    return int(time.time())

def is_admin(user_id):
    return user_id in ADMIN_IDS

# helper to download photo (optional) and return file_id and local path
def save_photo_from_message(msg):
    if msg.content_type != 'photo':
        return None, None
    file_id = msg.photo[-1].file_id
    # optionally download to local storage
    try:
        finfo = bot.get_file(file_id)
        data = bot.download_file(finfo.file_path)
        filename = f"{int(time.time()*1000)}_{file_id}.jpg"
        path = os.path.join(PHOTOS_DIR, filename)
        with open(path, "wb") as fh:
            fh.write(data)
    except Exception:
        path = None
    return file_id, path

# ========== Start / Help ==========
@bot.message_handler(commands=['start'])
def cmd_start(m):
    bot.send_message(m.chat.id, "Welcome! Please choose:", reply_markup=start_screen_kb())

@bot.message_handler(func=lambda m: m.text == "Start")
def on_start(m):
    
    try:
        with open("logo.png", "rb") as ph:
            bot.send_photo(m.chat.id, ph, caption="Welcome to AQMOLA IT Ecosystem!", reply_markup=main_menu_kb())
            return
    except Exception:
        pass
    bot.send_message(m.chat.id, "Welcome to AQMOLA IT Ecosystem!", reply_markup=main_menu_kb())

@bot.message_handler(func=lambda m: m.text == "Help")
def on_help(m):
    txt = (
        "Навигация:\n"
        "- Start — главное меню\n"
        "- Help — эта подсказка\n\n"
        "Через меню можно регистрировать стартапы и команды, добавлять события и контакты.\n"
        "Редактирование записей доступно только админам.\n\n"
        "Если хочешь, админы могут быть изменены в переменной ADMIN_IDS."
    )
    bot.send_message(m.chat.id, txt, reply_markup=start_screen_kb())

# ========== Main menu handling ==========
@bot.message_handler(func=lambda m: True)
def main_handler(m):
    text = (m.text or "").strip()
    uid = m.from_user.id

    if text == "🎯 Стартапы":
        show_startups_menu(m)

    elif text == "👥 Команды":
        show_teams_menu(m)

    elif text == "📅 События" or text == "📰 Новости":
        show_events(m)

    elif text == "📞 Контакты":
        show_contacts(m)

    elif text == "ℹ️ О нас":
        bot.send_message(m.chat.id, "Aqmola Hub и WebClub — организаторы хакатона CodeMasters.", reply_markup=main_menu_kb())

    elif text == "➕ Регистрация Стартапа":
        
        set_state(uid, "flow", "reg_startup")
        set_state(uid, "step", "name")
        bot.send_message(m.chat.id, "Введите название стартапа (или 'Отмена'):", reply_markup=cancel_kb("Отмена"))

    elif text == "➕ Регистрация Команды":
        set_state(uid, "flow", "reg_team")
        set_state(uid, "step", "name")
        bot.send_message(m.chat.id, "Введите название команды (или 'Отмена'):", reply_markup=cancel_kb("Отмена"))

    elif text == "➕ Добавить событие":
        set_state(uid, "flow", "reg_event")
        set_state(uid, "step", "name")
        bot.send_message(m.chat.id, "Введите название события (или 'Отмена'):", reply_markup=cancel_kb("Отмена"))

    elif text == "📤 Экспорт данных":
        
        export_all(m)

    elif text == "🔧 Админ: редактирование":
        if not is_admin(uid):
            bot.send_message(m.chat.id, "Доступно только админам.", reply_markup=main_menu_kb())
            return
       
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Редактировать Стартапы", callback_data="admin_edit_startups"))
        kb.add(types.InlineKeyboardButton("Редактировать Команды", callback_data="admin_edit_teams"))
        kb.add(types.InlineKeyboardButton("Редактировать Контакты", callback_data="admin_edit_contacts"))
        kb.add(types.InlineKeyboardButton("Редактировать События", callback_data="admin_edit_events"))
        bot.send_message(m.chat.id, "Админ редактор: выберите тип:", reply_markup=kb)

    else:
        
        flow = get_state(uid, "flow")
        step = get_state(uid, "step")
        if flow == "reg_startup":
            handle_reg_startup_steps(m, step)
        elif flow == "reg_team":
            handle_reg_team_steps(m, step)
        elif flow == "reg_event":
            handle_reg_event_steps(m, step)
        else:
            bot.send_message(m.chat.id, "Пожалуйста, используйте главное меню (Start) или Help.", reply_markup=start_screen_kb())

# ========== Display functions ==========
def show_startups_menu(m):
    cur.execute("SELECT id, name, description, photo_file_id FROM startups ORDER BY id DESC")
    rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "Пока нет зарегистрированных стартапов.", reply_markup=main_menu_kb())
        return
    for r in rows:
        sid, name, desc, file_id = r
        caption = f"{name}\n{(desc or '')[:400]}\n/id_{sid}"
        if file_id:
            try:
                bot.send_photo(m.chat.id, file_id, caption=caption)
            except Exception:
                bot.send_message(m.chat.id, caption)
        else:
            bot.send_message(m.chat.id, caption)
    bot.send_message(m.chat.id, "Меню:", reply_markup=main_menu_kb())

def show_teams_menu(m):
    cur.execute("SELECT id, name, members, project FROM teams ORDER BY id DESC")
    rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "Пока нет зарегистрированных команд.", reply_markup=main_menu_kb())
        return
    for r in rows:
        tid, name, members, project = r
        bot.send_message(m.chat.id, f"{name}\nУчастники: {members}\nПроект: {project}\n/id_team_{tid}")
    bot.send_message(m.chat.id, "Меню:", reply_markup=main_menu_kb())

def show_events(m):
    cur.execute("SELECT id, name, date, time, goal FROM events ORDER BY id DESC")
    rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "Событий нет.", reply_markup=main_menu_kb())
        return
    for r in rows:
        eid, name, date, time_s, goal = r
        bot.send_message(m.chat.id, f"{name}\nДата: {date}  Время: {time_s}\nЦель: {goal}\n/id_event_{eid}")
    bot.send_message(m.chat.id, "Меню:", reply_markup=main_menu_kb())

def show_contacts(m):
    cur.execute("SELECT id, email, phone, tg_username FROM contacts ORDER BY id DESC")
    rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "Контактов нет.", reply_markup=main_menu_kb())
        return
    for r in rows:
        cid, email, phone, tg = r
        bot.send_message(m.chat.id, f"{email}\n{phone}\n@{tg}\n/id_contact_{cid}")
    bot.send_message(m.chat.id, "Меню:", reply_markup=main_menu_kb())

# ========== Export ==========
def export_all(m):
    
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "Экспорт доступен только админам.", reply_markup=main_menu_kb())
        return
    tables = {
        "startups": cur.execute("SELECT * FROM startups").fetchall(),
        "teams": cur.execute("SELECT * FROM teams").fetchall(),
        "contacts": cur.execute("SELECT * FROM contacts").fetchall(),
        "events": cur.execute("SELECT * FROM events").fetchall()
    }
    
    for name, rows in tables.items():
        txt = "\n".join([str(row) for row in rows]) or "empty"
        bot.send_message(m.chat.id, f"{name}:\n{txt}")
    bot.send_message(m.chat.id, "Экспорт завершён.", reply_markup=main_menu_kb())

# ========== Registration step handlers ==========
def handle_reg_startup_steps(m, step):
    uid = m.from_user.id
    if m.text and m.text.lower() == "отмена":
        clear_state(uid)
        bot.send_message(m.chat.id, "Регистрация отменена.", reply_markup=main_menu_kb())
        return

    if step == "name":
        set_state(uid, "startup_name", m.text)
        set_state(uid, "step", "description")
        bot.send_message(m.chat.id, "Введите описание стартапа:", reply_markup=cancel_kb("Отмена"))
    elif step == "description":
        set_state(uid, "startup_desc", m.text)
        set_state(uid, "step", "contact")
        bot.send_message(m.chat.id, "Введите контакт (телефон или @username):", reply_markup=cancel_kb("Отмена"))
    elif step == "contact":
        set_state(uid, "startup_contact", m.text)
        set_state(uid, "step", "photo")
        bot.send_message(m.chat.id, "Пришлите фото проекта (как фото) или напишите 'нет':", reply_markup=cancel_kb("Отмена"))
    elif step == "photo":
        
        file_id = None
        if m.content_type == "photo":
            file_id = m.photo[-1].file_id
        elif m.text and m.text.lower() == "нет":
            file_id = None
        else:
            bot.send_message(m.chat.id, "Пожалуйста, пришлите фото (как фото) или 'нет':", reply_markup=cancel_kb("Отмена"))
            return
        
        name = get_state(uid, "startup_name")
        desc = get_state(uid, "startup_desc")
        contact = get_state(uid, "startup_contact")
        tg = None
        if contact and contact.startswith("@"):
            tg = contact.lstrip("@")
        cur.execute("INSERT INTO startups (owner_id, name, description, contact, tg_username, photo_file_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uid, name, desc, contact, tg, file_id, now_ts()))
        conn.commit()
        clear_state(uid)
        bot.send_message(m.chat.id, f"Стартап '{name}' зарегистрирован!", reply_markup=main_menu_kb())

def handle_reg_team_steps(m, step):
    uid = m.from_user.id
    if m.text and m.text.lower() == "отмена":
        clear_state(uid)
        bot.send_message(m.chat.id, "Регистрация отменена.", reply_markup=main_menu_kb())
        return
    if step == "name":
        set_state(uid, "team_name", m.text)
        set_state(uid, "step", "members")
        bot.send_message(m.chat.id, "Введите участников (через запятую):", reply_markup=cancel_kb("Отмена"))
    elif step == "members":
        set_state(uid, "team_members", m.text)
        set_state(uid, "step", "project")
        bot.send_message(m.chat.id, "Введите описание проекта команды:", reply_markup=cancel_kb("Отмена"))
    elif step == "project":
        name = get_state(uid, "team_name")
        members = get_state(uid, "team_members")
        project = m.text
        
        cur.execute("INSERT INTO teams (owner_id, name, members, project, created_at) VALUES (?, ?, ?, ?, ?)",
                    (uid, name, members, project, now_ts()))
        conn.commit()
        clear_state(uid)
        bot.send_message(m.chat.id, f"Команда '{name}' зарегистрирована!", reply_markup=main_menu_kb())

def handle_reg_event_steps(m, step):
    uid = m.from_user.id
    if m.text and m.text.lower() == "отмена":
        clear_state(uid)
        bot.send_message(m.chat.id, "Отмена.", reply_markup=main_menu_kb())
        return
    if step == "name":
        set_state(uid, "event_name", m.text)
        set_state(uid, "step", "date")
        bot.send_message(m.chat.id, "Введите дату (ДД.MM.ГГГГ):", reply_markup=cancel_kb("Отмена"))
    elif step == "date":
        set_state(uid, "event_date", m.text)
        set_state(uid, "step", "time")
        bot.send_message(m.chat.id, "Введите время (ЧЧ:ММ):", reply_markup=cancel_kb("Отмена"))
    elif step == "time":
        set_state(uid, "event_time", m.text)
        set_state(uid, "step", "goal")
        bot.send_message(m.chat.id, "Введите цель события:", reply_markup=cancel_kb("Отмена"))
    elif step == "goal":
        name = get_state(uid, "event_name")
        date = get_state(uid, "event_date")
        time_s = get_state(uid, "event_time")
        goal = m.text
        cur.execute("INSERT INTO events (name, date, time, goal, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, date, time_s, goal, now_ts()))
        conn.commit()
        clear_state(uid)
        bot.send_message(m.chat.id, f"Событие '{name}' добавлено.", reply_markup=main_menu_kb())

# ========== Admin inline handlers for editing ==========
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_edit_"))
def admin_edit_menu(cb):
    user_id = cb.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(cb.id, "Только админам", show_alert=True)
        return

    data = cb.data
    if data == "admin_edit_startups":
        rows = cur.execute("SELECT id, name FROM startups ORDER BY id DESC").fetchall()
        if not rows:
            bot.send_message(cb.message.chat.id, "Стартапов нет.", reply_markup=main_menu_kb()); return
        kb = types.InlineKeyboardMarkup()
        for sid, name in rows:
            kb.add(types.InlineKeyboardButton(name, callback_data=f"admin_edit_startup_{sid}"))
        bot.send_message(cb.message.chat.id, "Выберите стартап для редактирования:", reply_markup=kb)

    elif data == "admin_edit_teams":
        rows = cur.execute("SELECT id, name FROM teams ORDER BY id DESC").fetchall()
        if not rows:
            bot.send_message(cb.message.chat.id, "Команд нет.", reply_markup=main_menu_kb()); return
        kb = types.InlineKeyboardMarkup()
        for tid, name in rows:
            kb.add(types.InlineKeyboardButton(name, callback_data=f"admin_edit_team_{tid}"))
        bot.send_message(cb.message.chat.id, "Выберите команду:", reply_markup=kb)

    elif data == "admin_edit_contacts":
        rows = cur.execute("SELECT id, email FROM contacts ORDER BY id DESC").fetchall()
        if not rows:
            bot.send_message(cb.message.chat.id, "Контактов нет.", reply_markup=main_menu_kb()); return
        kb = types.InlineKeyboardMarkup()
        for cid, email in rows:
            kb.add(types.InlineKeyboardButton(email or f"#{cid}", callback_data=f"admin_edit_contact_{cid}"))
        bot.send_message(cb.message.chat.id, "Выберите контакт:", reply_markup=kb)

    elif data == "admin_edit_events":
        rows = cur.execute("SELECT id, name FROM events ORDER BY id DESC").fetchall()
        if not rows:
            bot.send_message(cb.message.chat.id, "Событий нет.", reply_markup=main_menu_kb()); return
        kb = types.InlineKeyboardMarkup()
        for eid, name in rows:
            kb.add(types.InlineKeyboardButton(name, callback_data=f"admin_edit_event_{eid}"))
        bot.send_message(cb.message.chat.id, "Выберите событие:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_edit_startup_"))
def admin_edit_startup_cb(cb):
    if not is_admin(cb.from_user.id):
        bot.answer_callback_query(cb.id, "Только админам", show_alert=True); return
    sid = int(cb.data.split("_")[-1])
    row = cur.execute("SELECT id, name, description, contact, tg_username, photo_file_id FROM startups WHERE id = ?", (sid,)).fetchone()
    if not row:
        bot.send_message(cb.message.chat.id, "Стартап не найден.", reply_markup=main_menu_kb()); return
    _, name, desc, contact, tg, file_id = row
    txt = f"#{sid} {name}\n{desc}\nContact: {contact or ''}\nTG: @{tg or ''}"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("Изменить название", callback_data=f"admin_act_startup_{sid}_name"),
           types.InlineKeyboardButton("Изменить описание", callback_data=f"admin_act_startup_{sid}_desc"))
    kb.row(types.InlineKeyboardButton("Изменить контакт", callback_data=f"admin_act_startup_{sid}_contact"),
           types.InlineKeyboardButton("Изменить TG", callback_data=f"admin_act_startup_{sid}_tg"))
    kb.row(types.InlineKeyboardButton("Изменить фото", callback_data=f"admin_act_startup_{sid}_photo"),
           types.InlineKeyboardButton("Удалить стартап", callback_data=f"admin_act_startup_{sid}_delete"))
    bot.send_message(cb.message.chat.id, txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_act_startup_"))
def admin_act_startup(cb):
    if not is_admin(cb.from_user.id):
        bot.answer_callback_query(cb.id, "Только админам"); return
    parts = cb.data.split("_")
    sid = int(parts[3])
    action = parts[4]
    uid = cb.from_user.id

    if action == "name":
        set_state(uid, "admin_edit_mode", ("startup", sid, "name"))
        bot.send_message(cb.message.chat.id, "Введите новое название:", reply_markup=cancel_kb("Отмена"))
    elif action == "desc":
        set_state(uid, "admin_edit_mode", ("startup", sid, "description"))
        bot.send_message(cb.message.chat.id, "Введите новое описание:", reply_markup=cancel_kb("Отмена"))
    elif action == "contact":
        set_state(uid, "admin_edit_mode", ("startup", sid, "contact"))
        bot.send_message(cb.message.chat.id, "Введите новый контакт (номер или @username):", reply_markup=cancel_kb("Отмена"))
    elif action == "tg":
        set_state(uid, "admin_edit_mode", ("startup", sid, "tg_username"))
        bot.send_message(cb.message.chat.id, "Введите TG username без @:", reply_markup=cancel_kb("Отмена"))
    elif action == "photo":
        set_state(uid, "admin_edit_mode", ("startup", sid, "photo"))
        bot.send_message(cb.message.chat.id, "Пришлите новое фото (как фото):", reply_markup=cancel_kb("Отмена"))
    elif action == "delete":
        cur.execute("DELETE FROM startups WHERE id = ?", (sid,))
        conn.commit()
        bot.send_message(cb.message.chat.id, "Стартап удалён.", reply_markup=main_menu_kb())



@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_edit_team_"))
def admin_edit_team_cb(cb):
    if not is_admin(cb.from_user.id): bot.answer_callback_query(cb.id, "Только админам"); return
    tid = int(cb.data.split("_")[-1])
    row = cur.execute("SELECT id, name, members, project, contact, tg_username FROM teams WHERE id = ?", (tid,)).fetchone()
    if not row:
        bot.send_message(cb.message.chat.id, "Команда не найдена.", reply_markup=main_menu_kb()); return
    _, name, members, project, contact, tg = row
    txt = f"#{tid} {name}\nУчастники: {members}\nПроект: {project}\nКонтакт: {contact or ''}\nTG: @{tg or ''}"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("Изм. название", callback_data=f"admin_act_team_{tid}_name"),
           types.InlineKeyboardButton("Изм. участников", callback_data=f"admin_act_team_{tid}_members"))
    kb.row(types.InlineKeyboardButton("Изм. проект", callback_data=f"admin_act_team_{tid}_project"),
           types.InlineKeyboardButton("Удалить команду", callback_data=f"admin_act_team_{tid}_delete"))
    bot.send_message(cb.message.chat.id, txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_act_team_"))
def admin_act_team(cb):
    if not is_admin(cb.from_user.id): bot.answer_callback_query(cb.id, "Только админам"); return
    parts = cb.data.split("_")
    tid = int(parts[3])
    action = parts[4]
    uid = cb.from_user.id
    if action == "name":
        set_state(uid, "admin_edit_mode", ("team", tid, "name"))
        bot.send_message(cb.message.chat.id, "Введите новое название:", reply_markup=cancel_kb("Отмена"))
    elif action == "members":
        set_state(uid, "admin_edit_mode", ("team", tid, "members"))
        bot.send_message(cb.message.chat.id, "Введите новых участников (через запятую):", reply_markup=cancel_kb("Отмена"))
    elif action == "project":
        set_state(uid, "admin_edit_mode", ("team", tid, "project"))
        bot.send_message(cb.message.chat.id, "Введите описание проекта:", reply_markup=cancel_kb("Отмена"))
    elif action == "delete":
        cur.execute("DELETE FROM teams WHERE id = ?", (tid,))
        conn.commit()
        bot.send_message(cb.message.chat.id, "Команда удалена.", reply_markup=main_menu_kb())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_edit_contact_"))
def admin_edit_contact_cb(cb):
    if not is_admin(cb.from_user.id): bot.answer_callback_query(cb.id, "Только админам"); return
    cid = int(cb.data.split("_")[-1])
    row = cur.execute("SELECT id, email, phone, tg_username FROM contacts WHERE id = ?", (cid,)).fetchone()
    if not row:
        bot.send_message(cb.message.chat.id, "Контакт не найден.", reply_markup=main_menu_kb()); return
    _, email, phone, tg = row
    txt = f"#{cid}\nEmail: {email}\nPhone: {phone}\nTG: @{tg or ''}"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("Изм. email", callback_data=f"admin_act_contact_{cid}_email"),
           types.InlineKeyboardButton("Изм. phone", callback_data=f"admin_act_contact_{cid}_phone"))
    kb.row(types.InlineKeyboardButton("Изм. TG", callback_data=f"admin_act_contact_{cid}_tg"),
           types.InlineKeyboardButton("Удалить контакт", callback_data=f"admin_act_contact_{cid}_delete"))
    bot.send_message(cb.message.chat.id, txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_act_contact_"))
def admin_act_contact(cb):
    if not is_admin(cb.from_user.id): bot.answer_callback_query(cb.id, "Только админам"); return
    parts = cb.data.split("_")
    cid = int(parts[3])
    action = parts[4]
    uid = cb.from_user.id
    if action == "email":
        set_state(uid, "admin_edit_mode", ("contact", cid, "email"))
        bot.send_message(cb.message.chat.id, "Введите новый email:", reply_markup=cancel_kb("Отмена"))
    elif action == "phone":
        set_state(uid, "admin_edit_mode", ("contact", cid, "phone"))
        bot.send_message(cb.message.chat.id, "Введите новый телефон:", reply_markup=cancel_kb("Отмена"))
    elif action == "tg":
        set_state(uid, "admin_edit_mode", ("contact", cid, "tg_username"))
        bot.send_message(cb.message.chat.id, "Введите TG username без @:", reply_markup=cancel_kb("Отмена"))
    elif action == "delete":
        cur.execute("DELETE FROM contacts WHERE id = ?", (cid,))
        conn.commit()
        bot.send_message(cb.message.chat.id, "Контакт удалён.", reply_markup=main_menu_kb())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_edit_event_"))
def admin_edit_event_cb(cb):
    if not is_admin(cb.from_user.id): bot.answer_callback_query(cb.id, "Только админам"); return
    eid = int(cb.data.split("_")[-1])
    row = cur.execute("SELECT id, name, date, time, goal FROM events WHERE id = ?", (eid,)).fetchone()
    if not row:
        bot.send_message(cb.message.chat.id, "Событие не найдено.", reply_markup=main_menu_kb()); return
    _, name, date, time_s, goal = row
    txt = f"#{eid} {name}\nДата: {date}  Время: {time_s}\nЦель: {goal}"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("Изм. название", callback_data=f"admin_act_event_{eid}_name"),
           types.InlineKeyboardButton("Изм. дату", callback_data=f"admin_act_event_{eid}_date"))
    kb.row(types.InlineKeyboardButton("Изм. время", callback_data=f"admin_act_event_{eid}_time"),
           types.InlineKeyboardButton("Изм. цель", callback_data=f"admin_act_event_{eid}_goal"))
    kb.row(types.InlineKeyboardButton("Удалить событие", callback_data=f"admin_act_event_{eid}_delete"))
    bot.send_message(cb.message.chat.id, txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_act_event_"))
def admin_act_event(cb):
    if not is_admin(cb.from_user.id): bot.answer_callback_query(cb.id, "Только админам"); return
    parts = cb.data.split("_")
    eid = int(parts[3])
    action = parts[4]
    uid = cb.from_user.id
    if action == "name":
        set_state(uid, "admin_edit_mode", ("event", eid, "name"))
        bot.send_message(cb.message.chat.id, "Введите новое название:", reply_markup=cancel_kb("Отмена"))
    elif action == "date":
        set_state(uid, "admin_edit_mode", ("event", eid, "date"))
        bot.send_message(cb.message.chat.id, "Введите новую дату (ДД.MM.ГГГГ):", reply_markup=cancel_kb("Отмена"))
    elif action == "time":
        set_state(uid, "admin_edit_mode", ("event", eid, "time"))
        bot.send_message(cb.message.chat.id, "Введите новое время (ЧЧ:ММ):", reply_markup=cancel_kb("Отмена"))
    elif action == "goal":
        set_state(uid, "admin_edit_mode", ("event", eid, "goal"))
        bot.send_message(cb.message.chat.id, "Введите новую цель:", reply_markup=cancel_kb("Отмена"))
    elif action == "delete":
        cur.execute("DELETE FROM events WHERE id = ?", (eid,))
        conn.commit()
        bot.send_message(cb.message.chat.id, "Событие удалено.", reply_markup=main_menu_kb())

# ========== Catch admin edit replies (finalize edits) ==========
@bot.message_handler(func=lambda m: get_state(m.from_user.id, "admin_edit_mode") is not None)
def finish_admin_edit(m):
    mode = get_state(m.from_user.id, "admin_edit_mode")
    if not mode:
        return
    kind, rec_id, field = mode
    
    if m.text and m.text.lower() == "отмена":
        clear_state(m.from_user.id)
        bot.send_message(m.chat.id, "Отмена.", reply_markup=main_menu_kb())
        return
    if kind == "startup":
        if field == "photo":
            if m.content_type != "photo":
                bot.send_message(m.chat.id, "Пришлите фото (как фотографию) или напишите 'Отмена'."); return
            file_id = m.photo[-1].file_id
            cur.execute("UPDATE startups SET photo_file_id = ? WHERE id = ?", (file_id, rec_id))
        else:
            value = m.text
            if field == "tg_username":
                value = value.lstrip("@")
            cur.execute(f"UPDATE startups SET {field} = ? WHERE id = ?", (value, rec_id))
        conn.commit()
        bot.send_message(m.chat.id, "Обновлено.", reply_markup=main_menu_kb())

    elif kind == "team":
        value = m.text
        cur.execute(f"UPDATE teams SET {field} = ? WHERE id = ?", (value, rec_id))
        conn.commit()
        bot.send_message(m.chat.id, "Команда обновлена.", reply_markup=main_menu_kb())

    elif kind == "contact":
        value = m.text
        if field == "tg_username":
            value = value.lstrip("@")
        cur.execute(f"UPDATE contacts SET {field} = ? WHERE id = ?", (value, rec_id))
        conn.commit()
        bot.send_message(m.chat.id, "Контакт обновлён.", reply_markup=main_menu_kb())

    elif kind == "event":
        value = m.text
        cur.execute(f"UPDATE events SET {field} = ? WHERE id = ?", (value, rec_id))
        conn.commit()
        bot.send_message(m.chat.id, "Событие обновлено.", reply_markup=main_menu_kb())

    clear_state(m.from_user.id)

# ========== Run ==========
if __name__ == "__main__":
    print("Bot started (Part 2) — admin editing enabled for ADMIN_IDS:", ADMIN_IDS)
    bot.polling(none_stop=True)
