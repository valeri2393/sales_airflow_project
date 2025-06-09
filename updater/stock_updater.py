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
import streamlit as st
import locale

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

# ------------------ Работа со складом ------------------
def get_latest_stock_excel():
    # тело функции не изменяем
    pass

# ------------------ Функция обновления склада ------------------
def update_stock_data():
    pass  # актуальный код обновления не требуется для визуализации


def show_stale_stock():я
    st.header("🧱 Залежавшийся складской остаток")

    try:
        locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')

    conn = sqlite3.connect("db.db")
    dates_df = pd.read_sql_query("SELECT DISTINCT report_date FROM stock_balance ORDER BY report_date DESC", conn)
    conn.close()

    dates_df['report_date'] = pd.to_datetime(dates_df['report_date'])
    formatted_labels = dates_df['report_date'].dt.strftime('%-d %B %Y').str.capitalize()
    label_to_date = dict(zip(formatted_labels, dates_df['report_date']))

    selected_label = st.selectbox("Выберите дату отчета:", list(label_to_date.keys()))
    selected_date = label_to_date[selected_label]

    st.markdown(f"📅 **Отображаются данные за дату: {selected_label}**")

    conn = sqlite3.connect("db.db")
    query = """
    SELECT article, nomenclature, warehouse, quantity, report_date
    FROM stock_balance
    WHERE quantity > 0 AND report_date = ?
    """
    df = pd.read_sql_query(query, conn, params=(selected_date.strftime('%Y-%m-%d'),))
    conn.close()

    df['report_date'] = pd.to_datetime(df['report_date'])
    current_date = df['report_date'].max()

    df_first = (
        df.groupby(['article', 'warehouse'])
        .agg({
            'report_date': 'min',
            'nomenclature': 'first',
            'quantity': 'sum'
        })
        .reset_index()
    )
    df_first['storage_months'] = ((current_date - df_first['report_date']) / pd.Timedelta(days=30)).astype(int)

    def highlight_row(row):
        return [
            'background-color: #f8d7da; color: #721c24;' if row['storage_months'] >= 9 else ''
        ] * len(row)

    df_show = df_first[['article', 'nomenclature', 'warehouse', 'quantity', 'report_date', 'storage_months']]
    styled = df_show.style.apply(highlight_row, axis=1)
    st.dataframe(styled, use_container_width=True)
