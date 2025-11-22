import streamlit as st
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

# --- إعدادات الملفات ---
LOG_FILE = 'attendance_log.csv'
USERS_FILE = 'users.csv'
FONT_FILE = 'Amiri-Regular.ttf'  # اسم ملف الخط الذي رفعته

st.set_page_config(page_title="نظام الحضور الذكي", layout="centered")

# --- دوال PDF ودوال البيانات ---

def load_data(file_path, columns):
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path, dtype=str)
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

# دالة خاصة لإصلاح النص العربي في PDF
def make_text_arabic(text):
    reshaped_text = arabic_reshaper.reshape(text) # يشبك الحروف
    bidi_text = get_display(reshaped_text)        # يصلح اتجاه الكتابة
    return bidi_text

def generate_pdf(dataframe):
    pdf = FPDF()
    pdf.add_page()
    
    # التأكد من وجود الخط
    if not os.path.exists(FONT_FILE):
        st.error(f"ملف الخط {FONT_FILE} غير موجود! الرجاء رفعه إلى GitHub.")
        return None

    # إضافة الخط العربي
    pdf.add_font('Amiri', '', FONT_FILE, uni=True)
    pdf.set_font('Amiri', '', 12)

    # عنوان التقرير
    pdf.set_font('Amiri', '', 18)
    pdf.cell(200, 10, make_text_arabic("تقرير الحضور والانصراف"), ln=True, align='C')
    pdf.ln(10)

    # إعداد الجدول
    pdf.set_font('Amiri', '', 12)
    line_height = 10
    col_width = 45 # عرض العمود

    # العناوين (الهيدر)
    headers = dataframe.columns.tolist()
    # نعكس الترتيب لأن العربية تبدأ من اليمين
    headers.reverse() 
    
    for header in headers:
        pdf.cell(col_width, line_height, make_text_arabic(header), border=1, align='C')
    pdf.ln(line_height)

    # البيانات
    for index, row in dataframe.iterrows():
        row_data = row.tolist()
        row_data.reverse() # نعكس البيانات أيضاً لتوافق العناوين
        for item in row_data:
            item_str = str(item)
            pdf.cell(col_width, line_height, make_text_arabic(item_str), border=1, align='C')
        pdf.ln(line_height)

    return pdf.output(dest='S').encode('latin-1')

# إنشاء ملف المستخدمين الافتراضي
if not os.path.exists(USERS_FILE):
    default_users = pd.DataFrame([{"username": "admin", "password": "123"}])
    save_data(default_users, USERS_FILE)

# --- نظام الجلسة ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.session_state['is_admin'] = False

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

def admin_view():
    st.header("🛠 لوحة المدير")
    tab1, tab2 = st.tabs(["📊 التقارير", "👥 الموظفين"])
    
    with tab1:
        df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        
        # خيارات الفلترة
        filter_opt = st.radio("عرض:", ["الكل", "موظف"], horizontal=True)
        if filter_opt == "موظف" and not df.empty:
            emp = st.selectbox("الموظف:", df["الاسم"].unique())
            df = df[df["الاسم"] == emp]
        
        st.dataframe(df, use_container_width=True)
        
        # --- أزرار التحميل ---
        col_d1, col_d2 = st.columns(2)
        
        # 1. تحميل CSV
        with col_d1:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 تحميل Excel/CSV", csv, "report.csv", "text/csv")
        
        # 2. تحميل PDF (الجديد)
        with col_d2:
            if st.button("تجهيز ملف PDF"):
                if not df.empty:
                    pdf_bytes = generate_pdf(df)
                    if pdf_bytes:
                        st.download_button("📄 تحميل PDF", pdf_bytes, "report.pdf", "application/pdf")
                else:
                    st.warning("لا توجد بيانات للطباعة")

    with tab2:
        users_df = load_data(USERS_FILE, ["username", "password"])
        st.dataframe(users_df)
        # (يمكنك إضافة كود الإضافة والحذف هنا كما كان سابقاً)

def employee_view(username):
    st.header(f"أهلاً {username}")
    c1, c2 = st.columns(2)
    if c1.button("🟢 دخول"): record_action(username, "دخول")
    if c2.button("🔴 خروج"): record_action(username, "خروج")
    
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    st.dataframe(df[df["الاسم"] == username])

def record_action(user, action):
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    now = datetime.now()
    new_row = {"الاسم": user, "نوع الحركة": action, "التاريخ": now.strftime("%Y-%m-%d"), "الوقت": now.strftime("%H:%M:%S")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(df, LOG_FILE)
    st.success("تم التسجيل!")

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
