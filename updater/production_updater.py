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

# ------------------ Работа с производством ------------------
def get_latest_prod_excel():
    mail = connect_to_email()
    mail.select('inbox')
    since=(datetime.now()-pd.Timedelta(days=14)).strftime("%d-%b-%Y")
    _,msgs=mail.search(None,'SINCE',since)
    if not msgs[0]: return None
    for eid in msgs[0].split()[::-1]:
        _,data=mail.fetch(eid,'(RFC822)')
        msg=email.message_from_bytes(data[0][1])
        subj,enc=decode_header(msg.get('Subject',''))[0]
        if isinstance(subj,bytes): subj=subj.decode(enc or 'utf-8')
        if 'исполнение производства' in subj.lower():
            for part in msg.walk():
                if part.get_content_maintype()=='multipart': continue
                if not part.get('Content-Disposition'): continue
                filename = part.get_filename()
                if not filename: continue
                fn, enc2 = decode_header(filename)[0]
                if isinstance(fn,bytes): fn = fn.decode(enc2 or 'utf-8')
                if fn.lower().endswith(('.xls','.xlsx')):
                    os.makedirs('temp',exist_ok=True)
                    path=os.path.join('temp',fn)
                    with open(path,'wb') as f: f.write(part.get_payload(decode=True))
                    return path
    return None


def process_prod_excel(path):
    # Читаем Excel с учетом трехстрочного заголовка
    df_raw = pd.read_excel(path, header=[0,1,2])

    # Плоский список имен колонок: объединяем все уровни в строку
    new_cols = []
    for cols in df_raw.columns:
        parts = [str(c).strip() for c in cols if not pd.isna(c) and str(c).strip()]
        new_cols.append(' '.join(parts))
    df_raw.columns = new_cols

    # Определяем колонки: ищем по вхождению
    art_col = next((c for c in df_raw.columns if 'Артикул' in c), None)
    desc_col = next((c for c in df_raw.columns if 'Номенклатура' in c and 'Характеристика' in c), None)
    plan_col = next((c for c in df_raw.columns if 'План' in c), None)
    fact_col = next((c for c in df_raw.columns if 'Факт' in c), None)

    missing = [col_name for col_name, var in [
        ('Артикул', art_col), 
        ('Описание', desc_col), 
        ('План', plan_col), 
        ('Факт', fact_col)
    ] if var is None]
    if missing:
        raise ValueError(f"Не найдены колонки: {missing}")

    # Отбираем нужные с учётом найденных имён
    df = df_raw[[art_col, desc_col, plan_col, fact_col]].copy()
    df.rename(columns={
        art_col: 'article',
        desc_col: 'nomenclature_desc',
        plan_col: 'plan',
        fact_col: 'fact'
    }, inplace=True)

    # Удаляем строку "Итого"
    df = df[~df['article'].astype(str).str.strip().str.lower().eq("итого")]

    # Приведение к числам
    df['plan'] = pd.to_numeric(df['plan'], errors='coerce').fillna(0)
    df['fact'] = pd.to_numeric(df['fact'], errors='coerce').fillna(0)
    df['date_updated'] = datetime.now()
    return df


def update_production_data():
    # Пытаемся найти и сохранить файл исполнения производства
    path = get_latest_prod_excel()
    print(f"Production file path: {path}")
    if not path:
        print("Не найдено писем с исполнением производства")
        return False
    # Обработка файла
    df = process_prod_excel(path)
    # Обновление базы данных
    conn = sqlite3.connect('db.db')
    # Создаем или очищаем таблицу
    conn.execute('DROP TABLE IF EXISTS production_exec')
    conn.execute('''
        CREATE TABLE production_exec(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article TEXT,
            nomenclature_desc TEXT,
            plan REAL,
            fact REAL,
            date_updated TIMESTAMP
        )
    ''')
    df_to_save = df[['article','nomenclature_desc','plan','fact','date_updated']]
    df_to_save.to_sql('production_exec', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()
    # Удаляем временный файл
    try:
        os.remove(path)
    except Exception as e:
        print(f"Не удалось удалить временный файл: {e}")
    print("Production table has been updated.")
    return True
