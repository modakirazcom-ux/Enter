import streamlit as st
import pandas as pd
from datetime import datetime
import os

# اسم ملف تخزين البيانات
FILE_NAME = 'attendance_log.csv'

# إعداد الصفحة
st.set_page_config(page_title="نظام الحضور", layout="centered")
st.title("📱 نظام تسجيل الحضور والانصراف")

# 1. تحميل البيانات القديمة إذا وجدت
if os.path.exists(FILE_NAME):
    df = pd.read_csv(FILE_NAME)
else:
    df = pd.DataFrame(columns=["الاسم", "نوع الحركة", "التاريخ", "الوقت"])

# 2. واجهة المستخدم (ما يراه الموظف)
with st.form("attendance_form"):
    name = st.selectbox("اختر اسمك:", ["أحمد محمد", "سارة علي", "خالد عمر", "ضيف"])
    action = st.radio("نوع الحركة:", ["تسجيل دخول 🟢", "تسجيل خروج 🔴"])
    submitted = st.form_submit_button("تسجيل")

    if submitted:
        # التقاط الوقت الحالي
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        # حفظ السجل
        new_record = {
            "الاسم": name,
            "نوع الحركة": action,
            "التاريخ": date_str,
            "الوقت": time_str
        }
        
        # إضافة السجل للبيانات وحفظه
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        df.to_csv(FILE_NAME, index=False)
        
        st.success(f"تم {action} للموظف {name} الساعة {time_str}")

# 3. عرض سجل الحركات (للمدير فقط - يمكن إخفاؤه لاحقاً)
st.markdown("---")
st.subheader("📋 سجل الحركات اليومي")
st.dataframe(df)
