import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- 1. إعدادات المستخدمين (قاعدة بيانات بسيطة) ---
# في الواقع العملي يفضل وضع هذه البيانات في secrets، لكن هنا للتجربة
USERS = {
    "admin": "12345",    # المدير - يرى كل شيء
    "ahmed": "111",      # موظف 1
    "sara": "222",       # موظف 2
    "khaled": "333"      # موظف 3
}

# اسم ملف تخزين البيانات
FILE_NAME = 'attendance_log.csv'

# إعداد الصفحة
st.set_page_config(page_title="نظام الحضور الآمن", layout="centered")

# --- 2. دوال مساعدة ---

def load_data():
    if os.path.exists(FILE_NAME):
        return pd.read_csv(FILE_NAME)
    return pd.DataFrame(columns=["الاسم", "نوع الحركة", "التاريخ", "الوقت"])

def save_data(df):
    df.to_csv(FILE_NAME, index=False)

# --- 3. نظام تسجيل الدخول ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''

def login_page():
    st.title("🔒 تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    
    if st.button("دخول"):
        if username in USERS and USERS[username] == password:
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

def logout():
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.rerun()

# --- 4. واجهات المستخدمين ---

def employee_view(username):
    st.header(f"مرحباً، {username} 👋")
    
    # أزرار التسجيل
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟢 تسجيل دخول", use_container_width=True):
            record_action(username, "تسجيل دخول")
    with col2:
        if st.button("🔴 تسجيل خروج", use_container_width=True):
            record_action(username, "تسجيل خروج")

    st.markdown("---")
    st.subheader("سجلي الشخصي")
    
    # عرض سجل الموظف الحالي فقط
    df = load_data()
    my_data = df[df["الاسم"] == username]
    st.dataframe(my_data, use_container_width=True)

def admin_view():
    st.header("🛠 لوحة تحكم المدير")
    
    df = load_data()
    
    # خيارات الفلترة للمدير
    st.subheader("التقارير")
    filter_option = st.radio("عرض البيانات:", ["الكل", "موظف محدد"], horizontal=True)
    
    if filter_option == "موظف محدد":
        # استخراج قائمة الموظفين من البيانات
        employee_list = df["الاسم"].unique()
        selected_emp = st.selectbox("اختر الموظف:", employee_list)
        st.dataframe(df[df["الاسم"] == selected_emp], use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

    # زر لتحميل البيانات كملف Excel/CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("تحميل التقرير (CSV)", csv, "report.csv", "text/csv")

def record_action(user, action):
    df = load_data()
    now = datetime.now()
    new_record = {
        "الاسم": user,
        "نوع الحركة": action,
        "التاريخ": now.strftime("%Y-%m-%d"),
        "الوقت": now.strftime("%H:%M:%S")
    }
    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    save_data(df)
    st.success(f"تم {action} بنجاح الساعة {now.strftime('%H:%M:%S')}")

# --- 5. التشغيل الرئيسي ---

if not st.session_state['logged_in']:
    login_page()
else:
    # الشريط الجانبي لتسجيل الخروج
    with st.sidebar:
        st.write(f"المستخدم: {st.session_state['username']}")
        if st.button("تسجيل خروج"):
            logout()
    
    # توجيه المستخدم حسب صلاحيته
    if st.session_state['username'] == 'admin':
        admin_view()
    else:
        employee_view(st.session_state['username'])
