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
FONT_FILE = 'Amiri-Regular.ttf'

st.set_page_config(page_title="نظام الحضور", layout="centered")

# تحديث كل 60 ثانية
count = st_autorefresh(interval=60000, limit=None, key="fizzbuzzcounter")

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
        st.error("انتظر لحظة.. السيرفر مشغول")

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

# --- إعدادات الخمول ---
@st.cache_data
def get_timeout_minutes_cached(_dummy_trigger=None):
    if os.path.exists(SETTINGS_FILE):
        try:
            df = pd.read_csv(SETTINGS_FILE)
            return int(df.iloc[0]['timeout'])
        except: return 5
    return 5

def update_timeout_settings(minutes):
    df = pd.DataFrame([{'timeout': minutes}])
    save_data(df, SETTINGS_FILE)
    get_timeout_minutes_cached.clear()

# --- التسجيل ---
def record_action(user, action, auto=False, specific_time=None):
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    if specific_time:
        log_time = specific_time
    else:
        log_time = get_local_time()
    
    if not df.empty:
        last_entry = df[df["الاسم"] == user].tail(1)
        if not last_entry.empty:
            last_action = last_entry.iloc[0]["نوع الحركة"]
            last_time_str = last_entry.iloc[0]["الوقت"]
            if last_action == action and str(log_time.strftime("%H:%M")) in str(last_time_str):
                 if not auto:
                     st.session_state['msg_type'] = 'warning'
                     st.session_state['msg_text'] = f"⚠️ لقد قمت بتسجيل {action} للتو!"
                 return 

    new_row = {"الاسم": user, "نوع الحركة": action, "التاريخ": log_time.strftime("%Y-%m-%d"), "الوقت": log_time.strftime("%H:%M:%S")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(df, LOG_FILE)
    
    if auto:
        st.session_state['msg_type'] = 'warning'
        st.session_state['msg_text'] = f"⚠️ خروج تلقائي ({log_time.strftime('%H:%M')})"
    else:
        st.session_state['msg_type'] = 'success'
        st.session_state['msg_text'] = f"✅ تم تسجيل {action} ({log_time.strftime('%H:%M')})"

# --- الخروج التلقائي ---
def check_inactivity():
    if st.session_state.get('logged_in') and not st.session_state.get('is_admin'):
        last_active = st.session_state.get('last_active_time')
        current_status = st.session_state.get('current_status')
        if last_active:
            timeout = get_timeout_minutes_cached() * 60
            if (get_local_time() - last_active).total_seconds() > timeout:
                if current_status == "منزل":
                    user = st.session_state['username']
                    logout_time = last_active + timedelta(minutes=get_timeout_minutes_cached())
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
if not os.path.exists(SETTINGS_FILE): save_data(pd.DataFrame([{'timeout': 5}]), SETTINGS_FILE)
if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False, 'last_active_time': get_local_time(), 'current_status': None})
check_inactivity()

def show_messages():
    if 'msg_text' in st.session_state and st.session_state['msg_text']:
        if st.session_state['msg_type'] == 'success':
            st.success(st.session_state['msg_text']); st.toast(st.session_state['msg_text'], icon="✅")
        else:
            st.warning(st.session_state['msg_text']); st.toast(st.session_state['msg_text'], icon="⚠️")
        st.session_state['msg_text'] = None

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
    st.header(f"أهلاً {username}")
    show_messages()
    to = get_timeout_minutes_cached()
    st.info(f"الحالة: {st.session_state['current_status'] if st.session_state['current_status'] else 'غير مسجل'}")
    
    place = st.radio("المكان:", ["مقر الشركة", "المنزل"], horizontal=True)
    c1, c2 = st.columns(2)
    if place == "مقر الشركة":
        # تم إزالة type="primary" ليصبح الزر أبيض/حيادي
        if c1.button("🟢 دخول مقر", use_container_width=True):
            st.session_state['current_status'] = "مقر"; record_action(username, "دخول مقر"); st.rerun()
        if c2.button("🔴 خروج مقر", use_container_width=True):
            st.session_state['current_status'] = None; record_action(username, "خروج مقر"); st.rerun()
    else:
        # تم إزالة type="primary" ليصبح الزر أبيض/حيادي
        if c1.button("🟢 دخول منزلي", use_container_width=True):
            st.session_state['current_status'] = "منزل"; record_action(username, "دخول منزلي"); st.rerun()
        if c2.button("🔴 خروج منزلي", use_container_width=True):
            st.session_state['current_status'] = None; record_action(username, "خروج منزلي"); st.rerun()
            
    st.divider()
    st.caption("سجل الحركات الكامل:")
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    if not df.empty:
        user_logs = df[df["الاسم"] == username]
        user_logs = user_logs.iloc[::-1]
        st.dataframe(style_data(user_logs), use_container_width=True)

def admin_view():
    update_activity()
    st.header("🛠 الأدمن")
    t1, t2, t3, t4, t5 = st.tabs(["⏱ الساعات", "📝 السجل", "👥 الموظفين", "🖐️ يدوي", "⚙️"])
    
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

    with t5:
        st.subheader("⚙️ إعدادات")
        cur = get_timeout_minutes_cached()
        new_t = st.number_input("دقائق خمول المنزل:", 1, 120, cur)
        if st.button("حفظ"): update_timeout_settings(new_t); st.success("تم"); st.rerun()

if not st.session_state['logged_in']: login_page()
else:
    with st.sidebar:
        st.write(f"👤 {st.session_state['username']}")
        if st.button("خروج"): st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False}); st.rerun()
    if st.session_state['is_admin']: admin_view()
    else: employee_view(st.session_state['username'])
