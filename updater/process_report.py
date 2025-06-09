import pandas as pd
from dadata import Dadata
from fuzzywuzzy import fuzz
from updater.mail import gmail_authenticate, get_file_by_mail_id
# from util.db import request_sql
import os
from datetime import datetime

import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "db.db")
DADATA_TOKEN = os.getenv("DADATA_TOKEN")
DADATA_SECRET = os.getenv("DADATA_SECRET")
SUBJECT = os.getenv("SUBJECT", "СТН")
MAIL_AUTH_PATH = os.getenv("MAIL_AUTH_PATH", "./data/mail_auth")

def prepare_df(df: pd.DataFrame):
    row = list(df.iloc[:, 0]).index('Клиент.Код')
    df.columns = df.iloc[row, :]
    df = df.iloc[row+1:, :]
    df.reset_index(inplace=True, drop=True)
    df.fillna(0, inplace=True)

    ind = list(df[df["Клиент.Наименование"] == 0].index)
    df["Дата"] = 0
    date_ind = list(df.columns).index("Дата")
    ind = [0] + ind
    k = 1
    for i in range(len(df)):
        try:
            if i < ind[k]:
                df.iloc[i, date_ind] = df.iloc[ind[k-1], 0]
            else:
                df.iloc[i, date_ind] = df.iloc[ind[k], 0]
                k += 1
        except BaseException:
            df.iloc[i, date_ind] = df.iloc[ind[k-1], 0]
    df.drop(df[(df["Дата"] == 0)].index, inplace=True)
    df.drop(df[(df["Клиент.Наименование"] == 0)].index, inplace=True)
    df.reset_index(inplace=True, drop=True)
    df["Год"] = df["Дата"].apply(lambda x: int(x.split('.')[2]))
    df["Месяц"] = df["Дата"].apply(lambda x: int(x.split('.')[1]))
    df["Признак"] = "Факт"
    return df

def analogue_value(search: list, dict_val: dict) -> dict:
    df_search = pd.DataFrame(search, columns=['search'])
    df_dict = pd.DataFrame.from_dict(dict_val, orient='index').reset_index()
    df_dict.columns = ['analogue', 'value']
    cross = pd.merge(df_search, df_dict, how="cross")
    cross["ratio"] = 0
    for i in range(len(cross)):
        cross.iloc[i, -1] = fuzz.token_sort_ratio(cross.iloc[i, 0], cross.iloc[i, 1])
    df_search["value"] = 0
    for i in range(len(df_search)):
        filtered_data = cross[cross["search"] == df_search.iloc[i, 0]]["ratio"]
        if not filtered_data.empty:
            value = cross.iloc[filtered_data.idxmax(), 2]
            df_search.iloc[i, -1] = value
        else:
            df_search.iloc[i, -1] = None
    return df_search.set_index('search')["value"].to_dict()

def new_clients(db_path: str, dadata: Dadata, df: pd.DataFrame):
    clients = df[CLIENT_COLS].drop_duplicates()
    clients.columns = ["code", "name", "head_name", "type", "adress"]
    db = request_sql(db_path, "SELECT code, name FROM clients", headers=True)
    clients = pd.merge(clients, db, how='left', on='code')
    clients = clients[clients["name_y"].isna()]
    if len(clients) > 0:
        clients["head_name"] = clients.apply(
            lambda x: x["head_name"] if x["head_name"] not in CLIENT_HEAD else x["name_x"], axis=1
        )
        clients.dropna(axis=1, inplace=True)
        clients["region"] = clients["adress"].apply(lambda x: None)
        client_reg = analogue_value(
            list(clients["region"]),
            pd.DataFrame(
                request_sql(db_path, "SELECT region, region FROM regions")
            ).set_index(0)[1].to_dict()
        )
        clients["region"] = clients["region"].apply(lambda x: client_reg[x])
        return clients[["code", "name_x", "head_name", "region", "type"]]
    else:
        return pd.DataFrame([])

def new_products(db_path: str, df: pd.DataFrame):
    products = df[PRODUCT_COLS].drop_duplicates()
    products.columns = ["code", "vendor_code", "name", "type", "unit"]
    db = request_sql(db_path, "SELECT * FROM products", headers=True)
    products = pd.merge(products, db, on="code", how="left")
    products = products[products["subcategory"].isna()]
    if len(products) > 0:
        products_subcat = analogue_value(
            list(products["name_x"]),
            db[["name", "subcategory"]].set_index("name")["subcategory"].to_dict()
        )
        products["subcategory"] = products["name_x"].apply(lambda x: products_subcat[x])
        products["ord"] = [0] * len(products)
        products["code_ap"] = [0] * len(products)
        return products[
            ["code", "name_x", "vendor_code_x", "code_ap", "type_x", "unit_x", "ord", "subcategory"]
        ]
    else:
        return pd.DataFrame([])

def new_sales(df: pd.DataFrame):
    monthes = list(df["Месяц"].unique())
    years = list(df["Год"].unique())
    df = df[SALES_COLS]
    df = pd.pivot_table(
        data=df,
        index=SALES_COLS[:-4],
        values=SALES_COLS[-4:],
        aggfunc='sum'
    )
    df.reset_index(inplace=True)
    df = df[SALES_COLS]
    df["Комментарий"] = '0'
    return df, years, monthes

def process_reports():
    from updater.const import DB_PATH, DADATA_TOKEN, DADATA_SECRET, SUBJECT, MAIL_AUTH_PATH
    from util.db import insert_clients, insert_products, insert_sales

    print("Аутентификация Gmail...")
    service = gmail_authenticate(MAIL_AUTH_PATH)
    print("Получение файла с почты...")
    df, subject = get_file_by_mail_id(service, SUBJECT)

    print("Обработка данных...")
    df = prepare_df(df)
    dadata = Dadata(DADATA_TOKEN, DADATA_SECRET)

    print("Получение новых клиентов...")
    clients = new_clients(DB_PATH, dadata, df)
    print("Получение новых товаров...")
    products = new_products(DB_PATH, df)
    print("Формирование продаж...")
    sales, years, monthes = new_sales(df)

    if not clients.empty:
        print("Загрузка клиентов...")
        insert_clients(DB_PATH, clients)
    if not products.empty:
        print("Загрузка продуктов...")
        insert_products(DB_PATH, products)
    if not sales.empty:
        print("Загрузка продаж...")
        insert_sales(DB_PATH, sales, years, monthes)

    print("Завершено.")


def update_db():
    process_reports()

def process_stock_excel(filepath, report_date=None):
    """Обработка Excel-файла со складскими остатками"""
    try:
        df = pd.read_excel(filepath, engine='openpyxl', header=None)  # Read without headers
        df = prepare_stock_df(df)  # Prepare the DataFrame

        # Print the columns for debugging
        print("Columns in the Excel file:", df.columns.tolist())

        # Adjust expected columns based on actual names
        expected_columns = ['Склад', 'Номенклатура', 'Артикул', 'Количество', 'Оценка']
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
