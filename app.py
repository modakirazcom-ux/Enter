import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- إعدادات الملفات ---
LOG_FILE = 'attendance_log.csv'
USERS_FILE = 'users.csv'

# إعداد الصفحة
st.set_page_config(page_title="نظام الحضور الذكي", layout="centered")

# --- 1. دوال التعامل مع البيانات (موظفين + حضور) ---

def load_data(file_path, columns):
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path, dtype=str) # نقرأ كل شيء كنصوص لمنع مشاكل الأرقام
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

# إنشاء ملف المستخدمين الافتراضي إذا لم يكن موجوداً
if not os.path.exists(USERS_FILE):
    # ننشئ المدير الافتراضي
    default_users = pd.DataFrame([{"username": "admin", "password": "123"}])
    save_data(default_users, USERS_FILE)

# --- 2. نظام تسجيل الدخول ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.session_state['is_admin'] = False

def login_page():
    st.title("🔒 تسجيل الدخول")
    
    users_df = load_data(USERS_FILE, ["username", "password"])
    
    username_input = st.text_input("اسم المستخدم").strip()
    password_input = st.text_input("كلمة المرور", type="password").strip()
    
    if st.button("دخول"):
        # البحث عن المستخدم
        user_match = users_df[
            (users_df['username'] == username_input) & 
            (users_df['password'] == password_input)
        ]
        
        if not user_match.empty:
            st.session_state['logged_in'] = True
            st.session_state['username'] = username_input
            # تحديد هل هو أدمن أم لا
            st.session_state['is_admin'] = (username_input == "admin")
            st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

def logout():
    st.session_state['logged_in'] = False
    st.session_state['username'] = ''
    st.session_state['is_admin'] = False
    st.rerun()

# --- 3. واجهة الموظف ---

def employee_view(username):
    st.header(f"مرحباً، {username} 👋")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟢 تسجيل دخول", use_container_width=True):
            record_action(username, "تسجيل دخول")
    with col2:
        if st.button("🔴 تسجيل خروج", use_container_width=True):
            record_action(username, "تسجيل خروج")

    st.markdown("---")
    st.subheader("سجلي الشخصي")
    
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    if not df.empty:
        my_data = df[df["الاسم"] == username]
        st.dataframe(my_data, use_container_width=True)

def record_action(user, action):
    df = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
    now = datetime.now()
    new_record = {
        "الاسم": user,
        "نوع الحركة": action,
        "التاريخ": now.strftime("%Y-%m-%d"),
        "الوقت": now.strftime("%H:%M:%S")
    }
    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    save_data(df, LOG_FILE)
    st.success(f"تم {action} بنجاح الساعة {now.strftime('%H:%M:%S')}")

# --- 4. واجهة المدير (لوحة التحكم الكاملة) ---

def admin_view():
    st.header("🛠 لوحة تحكم المدير")
    
    # تقسيم اللوحة إلى تبويبات لترتيب العمل
    tab1, tab2 = st.tabs(["📊 تقارير الحضور", "busts_in_silhouette: إدارة الموظفين"])
    
    # --- تبويب 1: التقارير ---
    with tab1:
        df_logs = load_data(LOG_FILE, ["الاسم", "نوع الحركة", "التاريخ", "الوقت"])
        
        filter_option = st.radio("عرض البيانات:", ["الكل", "موظف محدد"], horizontal=True)
        
        if filter_option == "موظف محدد":
            if not df_logs.empty:
                employee_list = df_logs["الاسم"].unique()
                selected_emp = st.selectbox("اختر الموظف:", employee_list)
                st.dataframe(df_logs[df_logs["الاسم"] == selected_emp], use_container_width=True)
            else:
                st.info("لا توجد سجلات بعد")
        else:
            st.dataframe(df_logs, use_container_width=True)
            
        # زر تحميل التقرير
        csv = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button("تحميل التقرير (CSV)", csv, "attendance_report.csv", "text/csv")

    # --- تبويب 2: إدارة الموظفين (إضافة وحذف) ---
    with tab2:
        st.subheader("قائمة المستخدمين الحالية")
        users_df = load_data(USERS_FILE, ["username", "password"])
        # نعرض الجدول لكن نخفي كلمات السر للحماية (اختياري)
        st.dataframe(users_df, use_container_width=True)
        
        st.markdown("---")
        
        # نموذج إضافة موظف جديد
        col_add1, col_add2 = st.columns(2)
        with col_add1:
            new_user = st.text_input("اسم المستخدم الجديد")
        with col_add2:
            new_pass = st.text_input("كلمة المرور للمستخدم الجديد")
            
        if st.button("إضافة موظف"):
            if new_user and new_pass:
                if new_user in users_df['username'].values:
                    st.error("هذا الاسم موجود مسبقاً!")
                else:
                    new_row = pd.DataFrame([{"username": new_user, "password": new_pass}])
                    users_df = pd.concat([users_df, new_row], ignore_index=True)
                    save_data(users_df, USERS_FILE)
                    st.success(f"تم إضافة {new_user} بنجاح! اضغط Rerun لتحديث القائمة")
            else:
                st.warning("الرجاء ملء الاسم وكلمة المرور")

        st.markdown("---")
        
        # نموذج حذف موظف
        st.subheader("حذف موظف")
        users_list = users_df['username'].tolist()
        # إزالة الأدمن من قائمة الحذف لمنع الكوارث
        if "admin" in users_list:
            users_list.remove("admin")
            
        user_to_delete = st.selectbox("اختر موظفاً لحذفه:", users_list)
        
        if st.button("حذف الموظف المحدد"):
            if user_to_delete:
                users_df = users_df[users_df['username'] != user_to_delete]
                save_data(users_df, USERS_FILE)
                st.success(f"تم حذف {user_to_delete}. اضغط Rerun لتحديث القائمة")
                st.rerun()

# --- 5. التشغيل الرئيسي ---

if not st.session_state['logged_in']:
    login_page()
else:
    with st.sidebar:
        st.write(f"👤 المستخدم: {st.session_state['username']}")
        if st.button("تسجيل خروج"):
            logout()
    
    if st.session_state['is_admin']:
        admin_view()
    else:
        employee_view(st.session_state['username'])
