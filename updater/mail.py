import base64
import io
import os
import pickle
import pandas as pd
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime

SCOPES = ['https://mail.google.com/']


def gmail_authenticate(auth_path):
    creds = None
    path_token = os.path.join(auth_path, "token.pickle")
    if os.path.exists(path_token):
        with open(path_token, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            path_cred = os.path.join(auth_path, "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(path_cred, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(path_token, "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)


def get_mail_id(service, subject):
    messages = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        q=f'subject:{subject}',
        maxResults=10
    ).execute().get('messages', [])

    for message in messages:
        headers = service.users().messages().get(
            userId='me', id=message['id']
        ).execute()['payload']['headers']

        for header in headers:
            if header['name'] == 'Subject' and subject in header['value']:
                return message['id'], header['value']
    return None


def get_file_by_mail_id(service, subject):
    result = get_mail_id(service, subject)
    if result is None:
        raise ValueError(f"Письмо с темой '{subject}' не найдено.")
    
    message_id, found_subject = result
    message = service.users().messages().get(userId='me', id=message_id).execute()
    parts = message['payload'].get('parts', [])

    for part in parts:
        if part.get('filename') and part['filename'].endswith(('.xlsx', '.xls')):
            if 'data' in part['body']:
                data = part['body']['data']
            else:
                att_id = part['body']['attachmentId']
                att = service.users().messages().attachments().get(
                    userId='me', messageId=message_id, id=att_id
                ).execute()
                data = att['data']
            file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
            df = pd.read_excel(io.BytesIO(file_data))
            return df, found_subject
    raise ValueError("Вложение Excel не найдено в письме.")


def fetch_emails():
    print("Запуск функции fetch_emails...")
    auth_path = "data/mail_auth"
    subject = "Остатки по складам"  # Измени при необходимости

    service = gmail_authenticate(auth_path)
    df, subject_found = get_file_by_mail_id(service, subject)

    output_path = "/app/latest_report.xlsx" if os.path.exists("/app") else "latest_report.xlsx"
    df.to_excel(output_path, index=False)
    print(f"Файл успешно сохранён: {output_path}, тема письма: {subject_found}")


def process_stock_excel(filepath, report_date=None):
    """Обработка Excel-файла со складскими остатками"""
    try:
        df = pd.read_excel(filepath, engine='openpyxl', header=None)  # Read without headers
        df = prepare_stock_df(df)  # Prepare the DataFrame

        # Strip whitespace from column names
        df.columns = df.columns.str.strip()

        # Print the columns for debugging
        print("Columns in the Excel file:", df.columns.tolist())

        # Adjust expected columns based on actual names
        expected_columns = ['Склад', 'Номенклатура', 'Артикул', 'Количество.3', 'Оценка.3']  # Include all relevant columns
        df = df[expected_columns]  # This line may raise the error if columns are missing

        # Добавляем дату обновления
        df['date_updated'] = datetime.now()
        if report_date:
            df['report_date'] = report_date
        else:
            df['report_date'] = datetime.now().strftime('%Y-%m-%d')

        return df
    except Exception as e:
        print(f"Ошибка при обработке Excel-файла: {e}")
        return None
