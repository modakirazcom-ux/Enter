import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
from streamlit_autorefresh import st_autorefresh

# --- إعدادات الملفات ---
LOG_FILE = 'attendance_log.csv'
USERS_FILE = 'users.csv'
SETTINGS_FILE = 'settings.csv'
FONT_FILE = 'Amiri-Regular.ttf'

st.set_page_config(page_title="نظام الحضور المرن", layout="centered")

# تعديل 1: التحديث كل 60 ثانية (60000 ملي ثانية) لتخفيف الضغط
count = st_autorefresh(interval=60000, limit=None, key="fizzbuzzcounter")

# --- دوال التعامل مع البيانات ---

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
        st.error("السيرفر مشغول، حاول مرة أخرى خلال ثوانٍ.")

# --- دوال الإعدادات (تحسين: استخدام الكاش) ---
# تعديل 2: نستخدم cache_data لمنع فتح الملف بشكل متكرر
@st.cache_data
def get_timeout_minutes_cached(_dummy_trigger=None):
    if os.path.exists(SETTINGS_FILE):
        try:
            df = pd.read_csv(SETTINGS_FILE)
            return int(df.iloc[0]['timeout'])
        except:
            return 5
    else:
        return 5

def update_timeout_settings(minutes):
    df = pd.DataFrame([{'timeout': minutes}])
    save_data(df, SETTINGS_FILE)
    # مسح الكاش عند التحديث ليأخذ القيمة الجديدة
    get_timeout_minutes_cached.clear()

# --- دالة التسجيل ---
def record_action(user, action, auto=False, specific_time=None):
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    
    if specific_time:
        log_time = specific_time
    else:
        log_time = datetime.now()
    
    if not df.empty:
        last_entry = df[df["الاسم"] == user].tail(1)
        if not last_entry.empty and last_entry.iloc[0]["نوع الحركة"] == action:
             return 

    new_row = {
        "الاسم": user, 
        "نوع الحركة": action, 
        "التاريخ": log_time.strftime("%Y-%m-%d"), 
        "الوقت": log_time.strftime("%H:%M:%S")
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(df, LOG_FILE)
    
    if auto:
        st.warning(f"⚠️ تم تسجيل {action} تلقائياً (وقت الخروج المحسوب: {log_time.strftime('%H:%M')})")
    else:
        st.success(f"تم تسجيل {action}")

# --- منطق الخروج التلقائي المرن ---
def check_inactivity():
    if st.session_state.get('logged_in') and not st.session_state.get('is_admin'):
        last_active = st.session_state.get('last_active_time')
        current_status = st.session_state.get('current_status')
        
        if last_active:
            # استخدام الدالة المحسنة
            timeout_minutes = get_timeout_minutes_cached()
            timeout_seconds = timeout_minutes * 60
            
            time_diff = datetime.now() - last_active
            
            if time_diff.total_seconds() > timeout_seconds:
                if current_status == "منزل":
                    user = st.session_state['username']
                    correct_logout_time = last_active + timedelta(minutes=timeout_minutes)
                    
                    record_action(user, "خروج منزلي", auto=True, specific_time=correct_logout_time)
                    
                    st.session_state['logged_in'] = False
                    st.session_state['username'] = ''
                    st.session_state['current_status'] = None
                    st.rerun()

def update_activity():
    st.session_state['last_active_time'] = datetime.now()

# --- حساب الساعات ---
def calculate_daily_hours(df_logs):
    if df_logs.empty: return pd.DataFrame()
    df_logs['DateTime'] = pd.to_datetime(df_logs['التاريخ'] + ' ' + df_logs['الوقت'], errors='coerce')
    df_logs = df_logs.sort_values(by=['الاسم', 'DateTime'])
    summary_data = []
    grouped = df_logs.groupby(['الاسم', 'التاريخ'])

    for (name, date), group in grouped:
        office_seconds = 0; home_seconds = 0
        records = group.to_dict('records')
        last_in_office = None; last_in_home = None

        for record in records:
            action = record['نوع الحركة']
            ts = record['DateTime']
            if pd.isna(ts): continue

            if "دخول مقر" in action: last_in_office = ts
            elif "خروج مقر" in action and last_in_office:
                d = (ts - last_in_office).total_seconds()
                if d > 0: office_seconds += d
                last_in_office = None
            elif "دخول منزلي" in action: last_in_home = ts
            elif "خروج منزلي" in action and last_in_home:
                d = (ts - last_in_home).total_seconds()
                if d > 0: home_seconds += d
                last_in_home = None

        def fmt(s): return f"{int(s//3600):02d}:{int((s%3600)//60):02d}"
        total = office_seconds + home_seconds
        if total > 0:
            summary_data.append({
                "الاسم": name, "التاريخ": date,
                "ساعات المقر": fmt(office_seconds), "ساعات المنزل": fmt(home_seconds),
                "الإجمالي": fmt(total)
            })
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
        pdf.add_font("Amiri", style="", fname=FONT_FILE)
        pdf.set_font("Amiri", size=12)
        pdf.set_font("Amiri", size=16)
        pdf.cell(0, 10, make_text_arabic(title), ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Amiri", size=10)
        line_height = 10; col_width = 35
        headers = dataframe.columns.tolist()[::-1]
        for header in headers: pdf.cell(col_width, line_height, make_text_arabic(header), border=1, align='C')
        pdf.ln(line_height)
        for _, row in dataframe.iterrows():
            row_data = row.tolist()[::-1]
            for item in row_data: pdf.cell(col_width, line_height, make_text_arabic(str(item)), border=1, align='C')
            pdf.ln(line_height)
        return bytes(pdf.output())
    except: return None

# --- Init ---
if not os.path.exists(USERS_FILE):
    save_data(pd.DataFrame([{"username": "admin", "password": "123"}]), USERS_FILE)

# التأكد من وجود ملف الإعدادات
if not os.path.exists(SETTINGS_FILE):
    save_data(pd.DataFrame([{'timeout': 5}]), SETTINGS_FILE)

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False, 'last_active_time': datetime.now(), 'current_status': None})

check_inactivity()

# --- Pages ---
def login_page():
    st.title("🔒 تسجيل الدخول")
    users_df = load_data(USERS_FILE, ["username", "password"])
    u = st.text_input("المستخدم").strip()
    p = st.text_input("كلمة المرور", type="password").strip()
    if st.button("دخول"):
        match = users_df[(users_df['username'] == u) & (users_df['password'] == p)]
        if not match.empty:
            st.session_state.update({'logged_in': True, 'username': u, 'is_admin': (u == "admin"), 'last_active_time': datetime.now()})
            
            logs = load_data(LOG_FILE, ["الاسم", "نوع الحركة"])
            if not logs.empty:
                last = logs[logs['الاسم'] == u].tail(1)
                if not last.empty:
                    act = last.iloc[0]['نوع الحركة']
                    if "دخول مقر" in act: st.session_state['current_status'] = "مقر"
                    elif "دخول منزلي" in act: st.session_state['current_status'] = "منزل"
            st.rerun()
        else: st.error("خطأ")

def employee_view(username):
    update_activity()
    st.header(f"أهلاً {username}")
    
    current_timeout = get_timeout_minutes_cached()
    
    status_msg = "غير مسجل دخول حالياً"
    if st.session_state['current_status'] == "مقر": status_msg = "🏢 أنت الآن: داخل المقر (العداد مفتوح)"
    elif st.session_state['current_status'] == "منزل": status_msg = f"🏠 أنت الآن: عمل منزلي (يفصل بعد {current_timeout} دقائق خمول)"
    
    st.info(status_msg)
    
    st.subheader("تحديد المكان")
    place = st.radio("المكان:", ["مقر الشركة", "المنزل"], horizontal=True)
    
    c1, c2 = st.columns(2)
    if place == "مقر الشركة":
        if c1.button("🟢 دخول مقر", type="primary", use_container_width=True):
            st.session_state['current_status'] = "مقر"
            record_action(username, "دخول مقر")
            st.rerun()
        if c2.button("🔴 خروج مقر", use_container_width=True):
            st.session_state['current_status'] = None
            record_action(username, "خروج مقر")
            st.rerun()
    else:
        if c1.button("🟢 دخول منزلي", type="primary", use_container_width=True):
            st.session_state['current_status'] = "منزل"
            record_action(username, "دخول منزلي")
            st.rerun()
        if c2.button("🔴 خروج منزلي", use_container_width=True):
            st.session_state['current_status'] = None
            record_action(username, "خروج منزلي")
            st.rerun()
            
    st.markdown("---")
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    if not df.empty:
        st.dataframe(df[(df["الاسم"] == username)].tail(3), use_container_width=True)

def admin_view():
    update_activity()
    st.header("🛠 الأدمن")
    
    t1, t2, t3, t4, t5 = st.tabs(["الساعات", "السجل", "الموظفين", "يدوي", "⚙️ الإعدادات"])
    
    with t1:
        if st.button("تحديث"): st.rerun()
        raw = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        res = calculate_daily_hours(raw)
        if not res.empty:
            st.dataframe(res, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.download_button("Excel", res.to_csv(index=False).encode('utf-8'), "sum.csv")
            if c2.button("PDF"): 
                pdf = generate_pdf(res, "ملخص"); 
                if pdf: c2.download_button("PDF", pdf, "sum.pdf", "application/pdf")
        else: st.info("لا بيانات")

    with t2: st.dataframe(load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"]), use_container_width=True)
    
    with t3:
        users = load_data(USERS_FILE, ["username", "password"])
        st.dataframe(users)
        c1, c2 = st.columns(2)
        u, p = c1.text_input("اسم"), c2.text_input("سر")
        if st.button("إضافة"):
            if u and p:
                save_data(pd.concat([users, pd.DataFrame([{"username": u, "password": p}])], ignore_index=True), USERS_FILE)
                st.success("تم"); st.rerun()

    with t4:
        st.subheader("إضافة يدوية")
        users = load_data(USERS_FILE, ["username", "password"])
        with st.form("manual"):
            sel_u = st.selectbox("موظف", users['username'])
            act = st.selectbox("حركة", ["دخول مقر", "خروج مقر", "دخول منزلي", "خروج منزلي"])
            d = st.date_input("تاريخ", datetime.now())
            t = st.time_input("وقت (ثابت 9:00)", time(9,0))
            if st.form_submit_button("حفظ"):
                row = {"الاسم": sel_u, "نوع الحركة": act, "التاريخ": d.strftime("%Y-%m-%d"), "الوقت": t.strftime("%H:%M:%S")}
                logs = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
                save_data(pd.concat([logs, pd.DataFrame([row])], ignore_index=True), LOG_FILE)
                st.success("تم")

    with t5:
        st.subheader("⚙️ إعدادات النظام")
        st.info("مدة الخمول المسموحة للموظف المنزلي (دقائق).")
        
        current_val = get_timeout_minutes_cached()
        
        new_timeout = st.number_input("دقائق الخمول:", min_value=1, max_value=120, value=current_val)
        
        if st.button("💾 حفظ الإعدادات"):
            update_timeout_settings(new_timeout)
            st.success(f"تم الحفظ: {new_timeout} دقائق.")
            st.rerun()

if not st.session_state['logged_in']:
    login_page()
else:
    with st.sidebar:
        st.write(f"👤 {st.session_state['username']}")
        if st.button("خروج"): 
            st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False})
            st.rerun()
    if st.session_state['is_admin']: admin_view()
    else: employee_view(st.session_state['username'])
