import os
import pandas as pd
import sqlite3
from datetime import datetime
import imaplib
import email
from email.header import decode_header
import re
from dotenv import load_dotenv
import numpy as np
from openpyxl import load_workbook

# Загрузка переменных окружения
load_dotenv()

# ------------------ Почтовые утилиты ------------------
def get_email_credentials():
    user = os.getenv("EMAIL_USER")
    pwd  = os.getenv("EMAIL_PASSWORD")
    srv  = os.getenv("EMAIL_SERVER", "imap.gmail.com")
    missing = [v for v in ("EMAIL_USER","EMAIL_PASSWORD","EMAIL_SERVER") if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Не найдены переменные окружения: {', '.join(missing)}.")
    return user, pwd, srv

def connect_to_email():
    user, pwd, srv = get_email_credentials()
    mail = imaplib.IMAP4_SSL(srv)
    mail.login(user, pwd)
    return mail

# # ------------------ Обновление данных по продажам ------------------
def update_sales_data():
    db_path = r"C:\\Users\\user\\Desktop\\Проекты\\projects\\sales_airflow_project\\db.db"

    mail = connect_to_email()
    mail.select('inbox')
    since = (datetime.now() - pd.Timedelta(days=5)).strftime("%d-%b-%Y")
    _, msgs = mail.search(None, 'SINCE', since)
    if not msgs[0]:
        print("📭 Нет писем с данными о продажах.")
        return False

    for eid in msgs[0].split()[::-1]:
        _, data = mail.fetch(eid, '(RFC822)')
        msg = email.message_from_bytes(data[0][1])
        subj, enc = decode_header(msg.get('Subject', ''))[0]
        if isinstance(subj, bytes):
            subj = subj.decode(enc or 'utf-8')
        if 'продажи стн' not in subj.lower():
            continue

        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            filename = part.get_filename()
            if not filename:
                continue
            fn, enc2 = decode_header(filename)[0]
            if isinstance(fn, bytes):
                fn = fn.decode(enc2 or 'utf-8')
            if fn.lower().endswith(('.xls', '.xlsx')):
                os.makedirs('temp', exist_ok=True)
                path = os.path.join('temp', 'sales_latest.xlsx')
                with open(path, 'wb') as f:
                    f.write(part.get_payload(decode=True))

                try:
                    df = pd.read_excel(path)
                    df.columns = [c.strip().lower().replace(' ', '_').replace(',', '') for c in df.columns]

                    rename_map = {
                        'Клиент.Код': 'client_code',
                        'Клиент.Основной менеджер': 'manager',
                        'Номенклатура.Код': 'product_code',
                        'Номенклатура.Наименование': 'product_name',
                        'Выручка': 'revenue'
                    }
                    df.rename(columns=rename_map, inplace=True)

                    df['year'] = datetime.now().year
                    df['month'] = datetime.now().month
                    df['type'] = 'Факт'

                    conn = sqlite3.connect(db_path)
                    conn.execute('''CREATE TABLE IF NOT EXISTS sales (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        year INTEGER,
                        month INTEGER,
                        type TEXT,
                        client_code TEXT,
                        manager TEXT,
                        product_code TEXT,
                        product_name TEXT,
                        revenue REAL
                    )''')

                    expected_cols = ['year', 'month', 'type', 'client_code', 'manager', 'product_code', 'product_name', 'revenue']
                    df = df[[col for col in expected_cols if col in df.columns]]

                    df.to_sql('sales', conn, if_exists='append', index=False)
                    conn.commit()
                    conn.close()

                    os.remove(path)
                    print("✅ Продажи успешно обновлены.")
                    return True
                except Exception as e:
                    print(f"❌ Ошибка при обработке файла продаж: {e}")
                    return False

    print("❌ Файл с продажами не найден среди последних писем.")
    return False