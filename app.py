import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
from streamlit_autorefresh import st_autorefresh

# --- إعدادات المنطقة الزمنية ---
HOURS_DIFF = 3 

# --- إعدادات الملفات ---
LOG_FILE = 'attendance_log.csv'
USERS_FILE = 'users.csv'
SETTINGS_FILE = 'settings.csv'
CHAT_FILE = 'chat_history.csv'
FONT_FILE = 'Amiri-Regular.ttf'

# رابط صوت الجرس
NOTIFICATION_SOUND_URL = "https://upload.wikimedia.org/wikipedia/commons/0/05/Beep-09.ogg"

st.set_page_config(page_title="نظام الحضور الذكي", layout="centered")

# تحديث كل 3 ثواني
count = st_autorefresh(interval=3000, limit=None, key="fizzbuzzcounter")

# --- CSS ---
st.markdown("""
<style>
div.stButton > button {
    background-color: #ffffff !important;
    color: #000000 !important;
    border: 1px solid #cccccc !important;
    font-size: 16px !important;
    padding: 10px !important;
}
div.stButton > button:hover {
    background-color: #f9f9f9 !important;
    border-color: #999999 !important;
}
.stChatMessage {
    background-color: #f1f1f1;
    border-radius: 15px;
    padding: 10px;
    margin-bottom: 5px;
}
</style>
""", unsafe_allow_html=True)

# --- دوال البيانات ---
def load_data(file_path, columns):
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path, dtype=str)
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_data(df, file_path):
    try:
        df.to_csv(file_path, index=False)
    except OSError:
        pass

# --- دوال الدردشة ---
def send_message(sender, receiver, message):
    df = load_data(CHAT_FILE, ["sender", "receiver", "message", "date", "time", "read"])
    now = get_local_time()
    new_msg = {
        "sender": sender,
        "receiver": receiver,
        "message": message,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "read": "False"
    }
    df = pd.concat([df, pd.DataFrame([new_msg])], ignore_index=True)
    save_data(df, CHAT_FILE)

def get_chat_history(user1, user2):
    df = load_data(CHAT_FILE, ["sender", "receiver", "message", "date", "time", "read"])
    if df.empty: return pd.DataFrame()
    mask = ((df['sender'] == user1) & (df['receiver'] == user2)) | \
           ((df['sender'] == user2) & (df['receiver'] == user1))
    return df[mask]

def mark_as_read(user_reader, sender_user):
    df = load_data(CHAT_FILE, ["sender", "receiver", "message", "date", "time", "read"])
    if not df.empty:
        mask = (df['sender'] == sender_user) & (df['receiver'] == user_reader) & (df['read'] == "False")
        if mask.any():
            df.loc[mask, 'read'] = "True"
            save_data(df, CHAT_FILE)

# --- دالة التوقيت المحلي ---
def get_local_time():
    return datetime.utcnow() + timedelta(hours=HOURS_DIFF)

# --- دالة التجميل ---
def style_data(df):
    if df.empty: return df
    df_view = df.copy()
    def add_color(val):
        val_str = str(val)
        if "دخول" in val_str: return f"🟢 {val_str}"
        elif "خروج" in val_str: return f"🔴 {val_str}"
        return val_str
    if "نوع الحركة" in df_view.columns:
        df_view["نوع الحركة"] = df_view["نوع الحركة"].apply(add_color)
    return df_view

# --- إعدادات الخمول والتنبيه اليدوي ---
@st.cache_data
def get_settings_cached(_dummy_trigger=None):
    if os.path.exists(SETTINGS_FILE):
        try:
            df = pd.read_csv(SETTINGS_FILE)
            if 'manual_alert_time' not in df.columns: df['manual_alert_time'] = '0'
            if 'manual_alert_target' not in df.columns: df['manual_alert_target'] = 'all'
            return df.iloc[0]
        except: return pd.Series({'timeout': 5, 'manual_alert_time': '0', 'manual_alert_target': 'all'})
    return pd.Series({'timeout': 5, 'manual_alert_time': '0', 'manual_alert_target': 'all'})

def update_settings(timeout=None, alert_time=None, alert_target=None):
    current = get_settings_cached()
    
    new_timeout = timeout if timeout is not None else current.get('timeout', 5)
    new_alert_time = alert_time if alert_time is not None else current.get('manual_alert_time', '0')
    new_alert_target = alert_target if alert_target is not None else current.get('manual_alert_target', 'all')
    
    df = pd.DataFrame([{
        'timeout': new_timeout, 
        'manual_alert_time': new_alert_time,
        'manual_alert_target': new_alert_target
    }])
    save_data(df, SETTINGS_FILE)
    get_settings_cached.clear()

def trigger_manual_alert(target_user):
    now_str = datetime.now().strftime("%Y%m%d%H%M%S")
    update_settings(alert_time=now_str, alert_target=target_user)

# --- التسجيل ---
def record_action(user, action, auto=False, specific_time=None):
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    if specific_time: log_time = specific_time
    else: log_time = get_local_time()
    
    if not df.empty:
        last_entry = df[df["الاسم"] == user].tail(1)
        if not last_entry.empty:
            last_action = last_entry.iloc[0]["نوع الحركة"]
            last_time_str = last_entry.iloc[0]["الوقت"]
            if last_action == action and str(log_time.strftime("%H:%M")) in str(last_time_str):
                 if not auto:
                     st.session_state['msg_type'] = 'warning'
                     st.session_state['msg_text'] = f"⚠️ مسجل مسبقاً: {action}"
                 return 

    new_row = {"الاسم": user, "نوع الحركة": action, "التاريخ": log_time.strftime("%Y-%m-%d"), "الوقت": log_time.strftime("%H:%M:%S")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(df, LOG_FILE)
    
    if auto:
        st.session_state['msg_type'] = 'warning'
        st.session_state['msg_text'] = f"⚠️ خروج تلقائي ({log_time.strftime('%H:%M')})"
    else:
        st.session_state['msg_type'] = 'success'
        st.session_state['msg_text'] = f"✅ تم {action} ({log_time.strftime('%H:%M')})"

# --- الخروج التلقائي ---
def check_inactivity():
    if st.session_state.get('logged_in') and not st.session_state.get('is_admin'):
        last_active = st.session_state.get('last_active_time')
        current_status = st.session_state.get('current_status')
        if last_active:
            settings = get_settings_cached()
            timeout = int(settings.get('timeout', 5)) * 60
            if (get_local_time() - last_active).total_seconds() > timeout:
                if current_status == "منزل":
                    user = st.session_state['username']
                    logout_time = last_active + timedelta(minutes=int(settings.get('timeout', 5)))
                    record_action(user, "خروج منزلي", auto=True, specific_time=logout_time)
                    st.session_state.update({'logged_in': False, 'username': '', 'current_status': None})
                    st.rerun()

def update_activity(): st.session_state['last_active_time'] = get_local_time()

# --- الحسابات ---
def calculate_daily_hours(df_logs):
    if df_logs.empty: return pd.DataFrame()
    df_logs['DateTime'] = pd.to_datetime(df_logs['التاريخ'] + ' ' + df_logs['الوقت'], errors='coerce')
    df_logs = df_logs.sort_values(by=['الاسم', 'DateTime'])
    summary_data = []
    grouped = df_logs.groupby(['الاسم', 'التاريخ'])

    for (name, date), group in grouped:
        office_sec = 0; home_sec = 0
        records = group.to_dict('records')
        last_office = None; last_home = None
        for rec in records:
            act = rec['نوع الحركة']; ts = rec['DateTime']
            if pd.isna(ts): continue
            if "دخول مقر" in act: last_office = ts
            elif "خروج مقر" in act and last_office:
                d = (ts - last_office).total_seconds(); 
                if d > 0: office_sec += d
                last_office = None
            elif "دخول منزلي" in act: last_home = ts
            elif "خروج منزلي" in act and last_home:
                d = (ts - last_home).total_seconds(); 
                if d > 0: home_sec += d
                last_home = None
        def fmt(s): return f"{int(s//3600):02d}:{int((s%3600)//60):02d}"
        total = office_sec + home_sec
        if total > 0: summary_data.append({"الاسم": name, "التاريخ": date, "ساعات المقر": fmt(office_sec), "ساعات المنزل": fmt(home_sec), "الإجمالي": fmt(total)})
    return pd.DataFrame(summary_data)

# --- PDF ---
def make_text_arabic(text):
    if not isinstance(text, str): text = str(text)
    return get_display(arabic_reshaper.reshape(text))

def generate_pdf(dataframe, title="تقرير"):
    if not os.path.exists(FONT_FILE): return None
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("Amiri", style="", fname=FONT_FILE); pdf.set_font("Amiri", size=12)
        pdf.set_font("Amiri", size=16); pdf.cell(0, 10, make_text_arabic(title), ln=True, align='C'); pdf.ln(5)
        pdf.set_font("Amiri", size=10); headers = dataframe.columns.tolist()[::-1]
        for h in headers: pdf.cell(35, 10, make_text_arabic(h), border=1, align='C')
        pdf.ln(10)
        for _, row in dataframe.iterrows():
            for item in row.tolist()[::-1]: pdf.cell(35, 10, make_text_arabic(str(item)), border=1, align='C')
            pdf.ln(10)
        return bytes(pdf.output())
    except: return None

# --- Init ---
if not os.path.exists(USERS_FILE): save_data(pd.DataFrame([{"username": "admin", "password": "123"}]), USERS_FILE)
if not os.path.exists(SETTINGS_FILE): save_data(pd.DataFrame([{'timeout': 5, 'manual_alert_time': '0', 'manual_alert_target': 'all'}]), SETTINGS_FILE)
if not os.path.exists(CHAT_FILE): save_data(pd.DataFrame(columns=["sender", "receiver", "message", "date", "time", "read"]), CHAT_FILE)

if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False, 'last_active_time': get_local_time(), 'current_status': None})
check_inactivity()

def show_messages():
    if 'msg_text' in st.session_state and st.session_state['msg_text']:
        if st.session_state['msg_type'] == 'success':
            st.success(st.session_state['msg_text']); st.toast(st.session_state['msg_text'], icon="✅")
        else:
            st.warning(st.session_state['msg_text']); st.toast(st.session_state['msg_text'], icon="⚠️")
        st.session_state['msg_text'] = None

# --- دالة فحص التنبيهات ---
def check_alerts_and_notify(username):
    history = get_chat_history(username, "admin")
    current_count = len(history)
    
    if 'last_msg_count' not in st.session_state: st.session_state['last_msg_count'] = current_count
    
    should_play_sound = False
    notification_text = ""

    if current_count > st.session_state['last_msg_count']:
        if not history.empty and history.iloc[-1]['sender'] == 'admin':
            should_play_sound = True
            notification_text = "📨 رسالة جديدة من الإدارة!"
    st.session_state['last_msg_count'] = current_count

    settings = get_settings_cached()
    server_alert_time = str(settings.get('manual_alert_time', '0'))
    server_alert_target = str(settings.get('manual_alert_target', 'all'))
    
    if 'last_manual_alert' not in st.session_state: st.session_state['last_manual_alert'] = server_alert_time
        
    if server_alert_time != st.session_state['last_manual_alert']:
        if server_alert_target == 'all' or server_alert_target == username:
            should_play_sound = True
            notification_text = "🔔 تنبيه إداري عاجل!"
        st.session_state['last_manual_alert'] = server_alert_time

    if should_play_sound:
        st.markdown(f"""<audio autoplay><source src="{NOTIFICATION_SOUND_URL}" type="audio/ogg"></audio>""", unsafe_allow_html=True)
        if notification_text: st.toast(notification_text, icon="🔔")

# --- Pages ---
def login_page():
    st.title("🔒 تسجيل الدخول")
    users = load_data(USERS_FILE, ["username", "password"])
    u = st.text_input("المستخدم").strip(); p = st.text_input("كلمة المرور", type="password").strip()
    if st.button("دخول"):
        match = users[(users['username'] == u) & (users['password'] == p)]
        if not match.empty:
            st.session_state.update({'logged_in': True, 'username': u, 'is_admin': (u == "admin"), 'last_active_time': get_local_time()})
            logs = load_data(LOG_FILE, ["الاسم", "نوع الحركة"])
            if not logs.empty:
                last = logs[logs['الاسم'] == u].tail(1)
                if not last.empty:
                    if "دخول مقر" in last.iloc[0]['نوع الحركة']: st.session_state['current_status'] = "مقر"
                    elif "دخول منزلي" in last.iloc[0]['نوع الحركة']: st.session_state['current_status'] = "منزل"
            st.rerun()
        else: st.error("خطأ")

def employee_view(username):
    update_activity()
    check_alerts_and_notify(username)
    st.header(f"أهلاً {username}")
    show_messages()
    
    tab1, tab2 = st.tabs(["🕒 الحضور والانصراف", "💬 الدردشة الفورية"])
    
    with tab1:
        settings = get_settings_cached()
        to = settings.get('timeout', 5)
        status = st.session_state['current_status']
        if status == "منزل": st.warning(f"🏠 عمل منزلي (مراقبة {to}د)")
        elif status == "مقر": st.success(f"🏢 داخل المقر")
        else: st.info("⚪ غير مسجل")
        
        place = st.radio("المكان:", ["مقر الشركة", "المنزل"], horizontal=True)
        c1, c2 = st.columns(2)
        if place == "مقر الشركة":
            if c1.button("🟢 دخول مقر", use_container_width=True):
                st.session_state['current_status'] = "مقر"; record_action(username, "دخول مقر"); st.rerun()
            if c2.button("🔴 خروج مقر", use_container_width=True):
                st.session_state['current_status'] = None; record_action(username, "خروج مقر"); st.rerun()
        else:
            if c1.button("🟢 دخول منزلي", use_container_width=True):
                st.session_state['current_status'] = "منزل"; record_action(username, "دخول منزلي"); st.rerun()
            if c2.button("🔴 خروج منزلي", use_container_width=True):
                st.session_state['current_status'] = None; record_action(username, "خروج منزلي"); st.rerun()
        
        st.divider()
        st.caption("سجل الحركات:")
        df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        if not df.empty:
            user_logs = df[df["الاسم"] == username].iloc[::-1]
            st.dataframe(style_data(user_logs), use_container_width=True)

    with tab2:
        st.subheader("مراسلة الإدارة")
        history = get_chat_history(username, "admin")
        chat_container = st.container(height=400)
        with chat_container:
            if not history.empty:
                for _, row in history.iterrows():
                    role = "user" if row['sender'] == username else "assistant"
                    with st.chat_message(role):
                        st.write(row['message']); st.caption(f"{row['time']}")
            else: st.write("ابدأ المحادثة...")
        if prompt := st.chat_input("اكتب رسالة..."):
            send_message(username, "admin", prompt); st.rerun()

def admin_view():
    update_activity()
    st.header("🛠 الأدمن")
    t1, t2, t3, t4, t5, t6 = st.tabs(["⏱ الساعات", "📝 السجل", "👥 الموظفين", "🖐️ يدوي", "⚙️ إعدادات", "💬 الدردشة"])
    
    with t1:
        if st.button("🔄 تحديث"): st.rerun()
        raw = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        res = calculate_daily_hours(raw)
        if not res.empty:
            filter_mode = st.radio("تصفية:", ["الجميع", "موظف محدد"], horizontal=True, key="h_filter")
            if filter_mode == "موظف محدد":
                emp_list = res["الاسم"].unique()
                sel_emp = st.selectbox("اختر الموظف:", emp_list, key="h_emp")
                res = res[res["الاسم"] == sel_emp]
            st.dataframe(res, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.download_button("Excel", res.to_csv(index=False).encode('utf-8'), "sum.csv")
            if c2.button("PDF"): 
                pdf = generate_pdf(res, "ملخص الساعات"); 
                if pdf: c2.download_button("PDF", pdf, "sum.pdf", "application/pdf")
        else: st.info("لا توجد بيانات.")

    with t2:
        df_logs = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        if not df_logs.empty:
            filter_mode_log = st.radio("عرض:", ["الجميع", "موظف محدد"], horizontal=True, key="l_filter")
            if filter_mode_log == "موظف محدد":
                emp_list_log = df_logs["الاسم"].unique()
                sel_emp_log = st.selectbox("اختر الموظف:", emp_list_log, key="l_emp")
                df_logs = df_logs[df_logs["الاسم"] == sel_emp_log]
            df_logs = df_logs.iloc[::-1]
            st.dataframe(style_data(df_logs), use_container_width=True)
        else: st.info("السجل فارغ.")

    with t3:
        users = load_data(USERS_FILE, ["username", "password"])
        st.dataframe(users)
        c1, c2 = st.columns(2)
        u, p = c1.text_input("اسم"), c2.text_input("سر")
        if st.button("إضافة"): 
            if u and p: save_data(pd.concat([users, pd.DataFrame([{"username": u, "password": p}])], ignore_index=True), USERS_FILE); st.success("تم"); st.rerun()

    with t4:
        st.subheader("إضافة يدوية")
        users = load_data(USERS_FILE, ["username", "password"])
        with st.form("manual"):
            sel_u = st.selectbox("موظف", users['username'])
            act = st.selectbox("حركة", ["دخول مقر", "خروج مقر", "دخول منزلي", "خروج منزلي"])
            d = st.date_input("تاريخ", get_local_time())
            t = st.time_input("وقت (ثابت 9:00)", time(9,0))
            if st.form_submit_button("حفظ"):
                row = {"الاسم": sel_u, "نوع الحركة": act, "التاريخ": d.strftime("%Y-%m-%d"), "الوقت": t.strftime("%H:%M:%S")}
                save_data(pd.concat([load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"]), pd.DataFrame([row])], ignore_index=True), LOG_FILE); st.success("تم")
        
        # --- تم نقل زر الجرس هنا ليكون ظاهراً ---
        st.divider()
        st.subheader("🔔 إرسال جرس تنبيه")
        
        users_df = load_data(USERS_FILE, ["username"])
        all_users = ["الجميع"] + users_df[users_df['username'] != 'admin']['username'].tolist()
        target_user_alert = st.selectbox("من تريد تنبيهه؟", all_users)
        
        if st.button("🔊 إرسال الجرس الآن", use_container_width=True):
            target_code = "all" if target_user_alert == "الجميع" else target_user_alert
            trigger_manual_alert(target_code)
            st.toast(f"تم إرسال الجرس لـ: {target_user_alert}", icon="📢")

    with t5:
        st.subheader("⚙️ إعدادات")
        current_settings = get_settings_cached()
        cur_timeout = int(current_settings.get('timeout', 5))
        new_t = st.number_input("دقائق خمول المنزل:", 1, 120, cur_timeout)
        if st.button("حفظ"): update_settings(timeout=new_t); st.success("تم"); st.rerun()

    with t6:
        st.subheader("📨 البريد الوارد (فوري)")
        users_df = load_data(USERS_FILE, ["username"])
        emp_list = users_df[users_df['username'] != 'admin']['username'].tolist()
        chat_df = load_data(CHAT_FILE, ["sender", "read"])
        emp_display_list = []
        for emp in emp_list:
            has_unread = not chat_df[(chat_df['sender'] == emp) & (chat_df['read'] == "False")].empty
            emp_display_list.append(f"🔴 {emp}" if has_unread else emp)
        selected_emp_str = st.selectbox("اختر الموظف:", emp_display_list)
        selected_emp = selected_emp_str.replace("🔴 ", "")
        if selected_emp:
            mark_as_read("admin", selected_emp)
            history = get_chat_history("admin", selected_emp)
            chat_container_admin = st.container(height=400)
            with chat_container_admin:
                if not history.empty:
                    for _, row in history.iterrows():
                        role = "user" if row['sender'] == "admin" else "assistant"
                        with st.chat_message(role):
                            st.write(row['message']); st.caption(f"{row['time']}")
                else: st.info("لا توجد رسائل.")
            if prompt := st.chat_input("رد على الموظف..."):
                send_message("admin", selected_emp, prompt); st.rerun()

if not st.session_state['logged_in']: login_page()
else:
    with st.sidebar:
        st.write(f"👤 {st.session_state['username']}")
        if st.button("خروج"): st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False}); st.rerun()
    if st.session_state['is_admin']: admin_view()
    else: employee_view(st.session_state['username'])
