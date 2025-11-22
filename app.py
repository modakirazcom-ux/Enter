import streamlit as st
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import io # مكتبة جديدة للتعامل مع الملفات

# --- إعدادات الملفات ---
LOG_FILE = 'attendance_log.csv'
USERS_FILE = 'users.csv'
FONT_FILE = 'Amiri-Regular.ttf'

st.set_page_config(page_title="نظام الحضور الذكي", layout="centered")

# --- دوال البيانات ---

def load_data(file_path, columns):
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path, dtype=str)
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

# --- دوال PDF المحدثة (fpdf2) ---

def make_text_arabic(text):
    if not isinstance(text, str):
        text = str(text)
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def generate_pdf(dataframe):
    # التأكد من وجود الخط
    if not os.path.exists(FONT_FILE):
        st.error(f"ملف الخط {FONT_FILE} غير موجود! تأكد من رفعه لـ GitHub.")
        return None

    try:
        pdf = FPDF()
        pdf.add_page()
        
        # إضافة الخط (الطريقة الجديدة في fpdf2)
        pdf.add_font("Amiri", style="", fname=FONT_FILE)
        pdf.set_font("Amiri", size=12)

        # العنوان
        pdf.set_font("Amiri", size=18)
        pdf.cell(0, 10, make_text_arabic("تقرير الحضور والانصراف"), ln=True, align='C')
        pdf.ln(10)

        # إعداد الجدول
        pdf.set_font("Amiri", size=12)
        line_height = 10
        col_width = 45

        # العناوين
        headers = dataframe.columns.tolist()
        headers.reverse() # عكس الترتيب للعربية
        
        for header in headers:
            pdf.cell(col_width, line_height, make_text_arabic(header), border=1, align='C')
        pdf.ln(line_height)

        # البيانات
        for index, row in dataframe.iterrows():
            row_data = row.tolist()
            row_data.reverse()
            for item in row_data:
                # تنظيف النص من أي مشاكل
                text_item = str(item) if item is not None else "-"
                pdf.cell(col_width, line_height, make_text_arabic(text_item), border=1, align='C')
            pdf.ln(line_height)

        # إخراج الملف كـ bytes (متوافق مع fpdf2)
        return bytes(pdf.output())
        
    except Exception as e:
        st.error(f"حدث خطأ أثناء إنشاء PDF: {e}")
        return None

# --- إعداد النظام (كما كان سابقاً) ---

if not os.path.exists(USERS_FILE):
    default_users = pd.DataFrame([{"username": "admin", "password": "123"}])
    save_data(default_users, USERS_FILE)

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
        
        # زر التحديث اليدوي (لحل مشاكل تأخر البيانات)
        if st.button("🔄 تحديث البيانات"):
            st.rerun()

        filter_opt = st.radio("عرض:", ["الكل", "موظف"], horizontal=True)
        if filter_opt == "موظف" and not df.empty:
            emp = st.selectbox("الموظف:", df["الاسم"].unique())
            df = df[df["الاسم"] == emp]
        
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 تحميل Excel/CSV", csv, "report.csv", "text/csv", use_container_width=True)
            
        with col2:
            # زر PDF المحسن
            if st.button("📄 تجهيز PDF", use_container_width=True):
                if not df.empty:
                    pdf_data = generate_pdf(df)
                    if pdf_data:
                        st.download_button("تحميل ملف PDF الآن", pdf_data, "report.pdf", "application/pdf", use_container_width=True)
                else:
                    st.warning("لا توجد بيانات")

    with tab2:
        users_df = load_data(USERS_FILE, ["username", "password"])
        st.dataframe(users_df, use_container_width=True)
        
        st.subheader("إضافة موظف جديد")
        c1, c2 = st.columns(2)
        new_u = c1.text_input("الاسم")
        new_p = c2.text_input("كلمة السر")
        if st.button("إضافة"):
             if new_u and new_p:
                new_row = pd.DataFrame([{"username": new_u, "password": new_p}])
                users_df = pd.concat([users_df, new_row], ignore_index=True)
                save_data(users_df, USERS_FILE)
                st.success("تم!")
                st.rerun()

def employee_view(username):
    st.header(f"أهلاً {username}")
    c1, c2 = st.columns(2)
    if c1.button("🟢 دخول", use_container_width=True): record_action(username, "دخول")
    if c2.button("🔴 خروج", use_container_width=True): record_action(username, "خروج")
    
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    if not df.empty:
        st.dataframe(df[df["الاسم"] == username], use_container_width=True)

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
