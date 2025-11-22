import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

# --- إعدادات الملفات ---
LOG_FILE = 'attendance_log.csv'
USERS_FILE = 'users.csv'
FONT_FILE = 'Amiri-Regular.ttf'

st.set_page_config(page_title="نظام الحضور الاحترافي", layout="centered")

# --- دوال التعامل مع البيانات ---

def load_data(file_path, columns):
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path, dtype=str)
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

# --- محرك حساب الساعات ---
def calculate_daily_hours(df_logs):
    if df_logs.empty:
        return pd.DataFrame()

    # دمج التاريخ والوقت
    df_logs['DateTime'] = pd.to_datetime(df_logs['التاريخ'] + ' ' + df_logs['الوقت'], errors='coerce')
    
    # ترتيب السجلات زمنياً بدقة
    df_logs = df_logs.sort_values(by=['الاسم', 'DateTime'])

    summary_data = []
    grouped = df_logs.groupby(['الاسم', 'التاريخ'])

    for (name, date), group in grouped:
        office_seconds = 0
        home_seconds = 0
        records = group.to_dict('records')
        
        last_in_office = None
        last_in_home = None

        for record in records:
            action = record['نوع الحركة']
            time_stamp = record['DateTime']
            
            if pd.isna(time_stamp): continue

            # منطق المقر
            if "دخول مقر" in action:
                last_in_office = time_stamp
            elif "خروج مقر" in action and last_in_office:
                duration = (time_stamp - last_in_office).total_seconds()
                if duration > 0: office_seconds += duration
                last_in_office = None

            # منطق المنزل
            elif "دخول منزلي" in action:
                last_in_home = time_stamp
            elif "خروج منزلي" in action and last_in_home:
                duration = (time_stamp - last_in_home).total_seconds()
                if duration > 0: home_seconds += duration
                last_in_home = None

        def format_duration(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours:02d}:{minutes:02d}"

        total_seconds = office_seconds + home_seconds
        
        if total_seconds > 0:
            summary_data.append({
                "الاسم": name,
                "التاريخ": date,
                "ساعات المقر": format_duration(office_seconds),
                "ساعات المنزل": format_duration(home_seconds),
                "الإجمالي اليومي": format_duration(total_seconds)
            })

    return pd.DataFrame(summary_data)

# --- دوال PDF ---
def make_text_arabic(text):
    if not isinstance(text, str): text = str(text)
    return get_display(arabic_reshaper.reshape(text))

def generate_pdf(dataframe, title="تقرير"):
    if not os.path.exists(FONT_FILE):
        st.error(f"ملف الخط {FONT_FILE} غير موجود!")
        return None
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("Amiri", style="", fname=FONT_FILE)
        pdf.set_font("Amiri", size=12)
        
        pdf.set_font("Amiri", size=16)
        pdf.cell(0, 10, make_text_arabic(title), ln=True, align='C')
        pdf.ln(5)

        pdf.set_font("Amiri", size=10)
        line_height = 10
        col_width = 35
        
        headers = dataframe.columns.tolist()[::-1]
        for header in headers:
            pdf.cell(col_width, line_height, make_text_arabic(header), border=1, align='C')
        pdf.ln(line_height)

        for _, row in dataframe.iterrows():
            row_data = row.tolist()[::-1]
            for item in row_data:
                pdf.cell(col_width, line_height, make_text_arabic(str(item)), border=1, align='C')
            pdf.ln(line_height)
            
        return bytes(pdf.output())
    except Exception as e:
        st.error(f"خطأ PDF: {e}")
        return None

# --- إعداد النظام ---
if not os.path.exists(USERS_FILE):
    default_users = pd.DataFrame([{"username": "admin", "password": "123"}])
    save_data(default_users, USERS_FILE)

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False})

# --- الصفحات ---

def login_page():
    st.title("🔒 تسجيل الدخول")
    users_df = load_data(USERS_FILE, ["username", "password"])
    user = st.text_input("اسم المستخدم").strip()
    password = st.text_input("كلمة المرور", type="password").strip()
    if st.button("دخول"):
        match = users_df[(users_df['username'] == user) & (users_df['password'] == password)]
        if not match.empty:
            st.session_state.update({'logged_in': True, 'username': user, 'is_admin': (user == "admin")})
            st.rerun()
        else:
            st.error("بيانات خاطئة")

def employee_view(username):
    st.header(f"أهلاً بك، {username} 👋")
    
    st.subheader("📍 تحديد مكان العمل")
    work_type = st.radio("أين تعمل الآن؟", ["مقر الشركة 🏢", "من المنزل 🏠"], horizontal=True)
    
    col1, col2 = st.columns(2)
    
    if work_type == "مقر الشركة 🏢":
        in_label, out_label = "دخول مقر", "خروج مقر"
        btn_color = "primary"
    else:
        in_label, out_label = "دخول منزلي", "خروج منزلي"
        btn_color = "secondary"

    with col1:
        if st.button(f"🟢 تسجيل {in_label}", use_container_width=True, type=btn_color):
            record_action(username, in_label)
    with col2:
        if st.button(f"🔴 تسجيل {out_label}", use_container_width=True):
            record_action(username, out_label)

    st.markdown("---")
    st.caption("سجلك اليوم:")
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    if not df.empty:
        today = datetime.now().strftime("%Y-%m-%d")
        my_logs = df[(df["الاسم"] == username) & (df["التاريخ"] == today)]
        st.dataframe(my_logs.tail(5), use_container_width=True)

def admin_view():
    st.header("🛠 لوحة المدير")
    
    tab1, tab2, tab3, tab4 = st.tabs(["⏱ حساب الساعات", "📝 السجل الخام", "👥 الموظفين", "🖐️ تسجيل يدوي"])
    
    # 1. حساب الساعات
    with tab1:
        st.subheader("ملخص ساعات العمل")
        if st.button("🔄 تحديث البيانات"): st.rerun()
        
        df_raw = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        if not df_raw.empty:
            df_sum = calculate_daily_hours(df_raw)
            if not df_sum.empty:
                st.dataframe(df_sum, use_container_width=True)
                c1, c2 = st.columns(2)
                c1.download_button("📥 Excel", df_sum.to_csv(index=False).encode('utf-8'), "summary.csv")
                if c2.button("📄 PDF"):
                    pdf = generate_pdf(df_sum, "ملخص الساعات")
                    if pdf: c2.download_button("تحميل PDF", pdf, "summary.pdf", "application/pdf")
            else:
                st.info("لا توجد ساعات مكتملة (دخول + خروج).")
        else:
            st.warning("لا توجد بيانات.")

    # 2. السجل الخام
    with tab2:
        df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        st.dataframe(df, use_container_width=True)

    # 3. الموظفين
    with tab3:
        users_df = load_data(USERS_FILE, ["username", "password"])
        st.dataframe(users_df)
        c1, c2 = st.columns(2)
        new_u, new_p = c1.text_input("اسم"), c2.text_input("سر")
        if st.button("إضافة موظف"):
             if new_u and new_p:
                new_row = pd.DataFrame([{"username": new_u, "password": new_p}])
                users_df = pd.concat([users_df, new_row], ignore_index=True)
                save_data(users_df, USERS_FILE)
                st.success("تم")
                st.rerun()

    # 4. تسجيل يدوي (تم الإصلاح النهائي)
    with tab4:
        st.subheader("إضافة حركة يدوية")
        st.info("حدد الوقت يدوياً. الوقت الافتراضي هو 09:00 للتأكد من أنك اخترت الوقت الصحيح.")
        
        users_df = load_data(USERS_FILE, ["username", "password"])
        users_list = users_df['username'].tolist()
        
        # استخدام Form يمنع التحديث التلقائي للقيم
        with st.form("manual_entry_form"):
            col_a, col_b = st.columns(2)
            selected_emp = col_a.selectbox("اختر الموظف", users_list)
            action_type = col_b.selectbox("نوع الحركة", ["خروج مقر", "دخول مقر", "خروج منزلي", "دخول منزلي"])
            
            col_c, col_d = st.columns(2)
            manual_date = col_c.date_input("التاريخ", datetime.now())
            
            # ⚠️ التغيير هنا: وقت ثابت (9 صباحاً) وليس الوقت الحالي، لإجبارك على تغييره
            fixed_time = time(9, 0) 
            manual_time = col_d.time_input("الوقت المحدد", value=fixed_time)
            
            submitted = st.form_submit_button("➕ حفظ الحركة")
            
            if submitted:
                date_str = manual_date.strftime("%Y-%m-%d")
                time_str = manual_time.strftime("%H:%M:%S") # يأخذ الوقت من الصندوق حصراً
                
                df_log = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
                new_record = {
                    "الاسم": selected_emp,
                    "نوع الحركة": action_type,
                    "التاريخ": date_str,
                    "الوقت": time_str
                }
                df_log = pd.concat([df_log, pd.DataFrame([new_record])], ignore_index=True)
                save_data(df_log, LOG_FILE)
                
                st.success(f"✅ تم الحفظ بنجاح: {selected_emp} | {action_type} | الساعة {time_str}")

def record_action(user, action):
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    now = datetime.now()
    new_row = {"الاسم": user, "نوع الحركة": action, "التاريخ": now.strftime("%Y-%m-%d"), "الوقت": now.strftime("%H:%M:%S")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(df, LOG_FILE)
    st.success(f"تم تسجيل {action}")

# --- التشغيل ---
if not st.session_state['logged_in']:
    login_page()
else:
    with st.sidebar:
        st.write(f"👤 {st.session_state['username']}")
        if st.button("خروج"): 
            st.session_state.update({'logged_in': False, 'username': '', 'is_admin': False})
            st.rerun()
            
    if st.session_state['is_admin']:
        admin_view()
    else:
        employee_view(st.session_state['username'])
