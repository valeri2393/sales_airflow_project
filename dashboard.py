import os
import streamlit as st
import pandas as pd
import sqlite3
from dotenv import load_dotenv
from datetime import datetime
import base64
import plotly.express as px
import plotly.graph_objects as go
import numpy as np


# Загрузка .env
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "db.db")

# Настройки страницы (должен быть первым вызовом Streamlit)
st.set_page_config(
    page_title="СТН - Промежуточные итоги",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"

)# Импорт обновляющих функций (без автозапуска)
from updater import (
    update_sales_data,
    update_stock_data,
    update_production_data,
    update_purchases_data
)

# Автоматическое обновление при открытии дашборда
@st.cache_data
def auto_update():
    update_sales_data()
    update_stock_data()
    update_production_data()
    update_purchases_data()

# Вызываем один раз при старте
auto_update()

# Загрузка .env файла
load_dotenv()

# Получение переменных из .env
DB_PATH = os.getenv("DB_PATH", "db.db").replace("DB_PATH=", "")  # Убираем префикс DB_PATH=
# COVER_IMAGE = os.getenv("COVER_IMAGE", "cover.png")
BACKGROUND_IMAGE = os.getenv("BACKGROUND_IMAGE", "cover.png")

# Функция для установки фона через base64
@st.cache_data
def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# CSS стиль для прозрачной белой подложки и прозрачного хедера
HEADER_STYLE = """
<style>
.transparent-box {
    background-color: rgba(255, 255, 255, 0.8);
    padding: 1.5rem;
    border-radius: 10px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    margin-bottom: 1.5rem;
}
header[data-testid="stHeader"] {
    background: transparent;
}
</style>
"""

st.markdown(HEADER_STYLE, unsafe_allow_html=True)

# Боковое меню
menu = st.sidebar.radio(
    "Выберите раздел:",
    (
        "🏠 Главная",
        "📋 Динамика продаж",
        "📦 Складские остатки", 
        "📊 Производство",
        "🌍 Логистика",
        "Закупки"
    )
)

# Главная
if menu == "🏠 Главная":
    # Удаляю отображение изображения cover.png
    with st.container():
        st.markdown("""
        <div class="transparent-box">
            <h1>СТН: Промежуточные итоги</h1>
        </div>
        """, unsafe_allow_html=True)
    # Добавим метрики и карточки
    st.markdown("<div class='transparent-box'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("Выручка, млн руб.", "1 250", "+5%")
    col2.metric("Выпуск продукции, т.", "3 200", "+2%")
    col3.metric("Доставка", "120", "0%")
    st.markdown("""
    <div style='display: flex; gap: 1rem;'>
        <div style='flex:1; background: #f0f2f6; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.05);'>
            <h4>ДАННЫЙ РАЗДЕЛ НАХОДИТСЯ В РАЗРАБОТКЕ</h4>
    
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "📋 Динамика продаж":
    st.markdown("""
        <h1 style='text-align:center; color:#2E4053; margin-bottom:0.5em;'>📊 Динамика продаж</h1>
        <hr style='border:1px solid #eee; margin-bottom:2em;'>
    """, unsafe_allow_html=True)

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT year AS Год, month AS Месяц, type AS Тип, SUM(revenue) AS Выручка
        FROM sales
        WHERE type IN ('Факт', 'Bdg')
        GROUP BY year, month, type
    """, conn)
    conn.close()

    MONTH_NAMES_RU = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }

    if df.empty:
        st.warning("Нет данных для отображения.")
    else:
        # Заменяем типы на более понятные названия
        df['Тип'] = df['Тип'].replace({
            'Bdg': 'План'
        })
        years = sorted(df['Год'].unique(), reverse=True)
        selected_year = st.selectbox("Выберите год", years)
        df_year = df[df['Год'] == selected_year].copy()
        df_year['Месяц_назв'] = df_year['Месяц'].map(MONTH_NAMES_RU)
        # Сортировка по номеру месяца
        df_year = df_year.sort_values(by=['Месяц'])

        # Для правильного порядка на графике:
        df_year['Месяц_назв'] = pd.Categorical(
            df_year['Месяц_назв'],
            categories=[MONTH_NAMES_RU[i] for i in range(1, 13)],
            ordered=True
        )

        st.markdown(f"<h3 style='color:#34495E;'>📊 Факт и План по месяцам — {selected_year}</h3>", unsafe_allow_html=True)
        totals = df_year.groupby('Тип')['Выручка'].sum().reset_index()
        total_text = ', '.join([f"{row['Тип']}: {int(row['Выручка']):,}".replace(',', ' ') for _, row in totals.iterrows()])
        st.info(f"**Суммарно за год:** {total_text}")

        fig = px.line(
            df_year, 
            x='Месяц_назв', 
            y='Выручка', 
            color='Тип', 
            markers=True,
            title="",
            labels={'Выручка': 'Выручка (млн руб.)', 'Месяц_назв': 'Месяц'}
        )
        fig.update_traces(
            text=df_year['Выручка'].apply(lambda x: f"{int(x/1_000_000)} млн" if pd.notnull(x) else ""),
            textposition='top center',
            line=dict(width=4),
            marker=dict(size=10, line=dict(width=2, color='DarkSlateGrey'))
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend_title_text='Тип',
            font=dict(size=16, family='Arial'),
            xaxis=dict(tickangle=-45),
            yaxis=dict(title='Выручка (млн руб.)', gridcolor='rgba(200,200,200,0.2)'),
            margin=dict(l=20, r=20, t=60, b=40),
            hovermode='x unified',
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- Новый блок: выбор менеджера и таблица клиентов ---
        conn = sqlite3.connect(DB_PATH)
        df_managers = pd.read_sql_query('SELECT DISTINCT manager FROM sales WHERE manager IS NOT NULL AND manager != ""', conn)
        conn.close()
        managers = sorted(df_managers['manager'].unique())
        selected_manager = st.selectbox('Выберите менеджера для анализа клиентов:', managers)
        if selected_manager:
            # Считаем общую сумму продаж (план и факт) по выбранному менеджеру и году
            conn = sqlite3.connect(DB_PATH)
            df_total = pd.read_sql_query('''
                SELECT 
                    SUM(CASE WHEN type = "Bdg" THEN revenue ELSE 0 END) as План,
                    SUM(CASE WHEN type = "Факт" THEN revenue ELSE 0 END) as Факт
                FROM sales
                WHERE manager = ? AND year = ?
            ''', conn, params=(selected_manager, str(selected_year)))
            conn.close()
            total_plan = int(df_total.iloc[0]['План']) if not pd.isna(df_total.iloc[0]['План']) else 0
            total_fact = int(df_total.iloc[0]['Факт']) if not pd.isna(df_total.iloc[0]['Факт']) else 0
            st.markdown(f"""
                <div style='background:#f8f9fa; border-radius:10px; padding:1em 1em; margin-bottom:1em; box-shadow:0 2px 8px rgba(44,62,80,0.07);'>
                    <span style='font-size:1.1em; color:#566573;'>Сумма продаж менеджера <b>{selected_manager}</b> за {selected_year} год:</span><br>
                    <span style='font-size:1.2em; color:#117A65;'>Факт: <b>{total_fact:,} руб.</b></span><br>
                    <span style='font-size:1.2em; color:#2874A6;'>План: <b>{total_plan:,} руб.</b></span>
                </div>
            """, unsafe_allow_html=True)
            conn = sqlite3.connect(DB_PATH)
            df_clients = pd.read_sql_query(f'''
                SELECT client_code,
                       SUM(CASE WHEN type = 'Факт' THEN revenue ELSE 0 END) as Факт
                FROM sales
                WHERE manager = ? AND year = ?
                GROUP BY client_code
                HAVING Факт > 0
                ORDER BY Факт DESC
            ''', conn, params=(selected_manager, str(selected_year)))
            conn.close()
            if not df_clients.empty:
                conn = sqlite3.connect(DB_PATH)
                df_names = pd.read_sql_query('SELECT code, name FROM clients', conn)
                conn.close()
                df_clients_merged = df_clients.merge(df_names, left_on='client_code', right_on='code', how='left')
                if not df_clients_merged['name'].isnull().all():
                    df_clients_merged = df_clients_merged[['client_code', 'name', 'Факт']]
                    df_clients_merged = df_clients_merged.rename(columns={'name': 'Клиент'})
                    st.markdown(f"<b>Найдено клиентов: {len(df_clients_merged)}</b>", unsafe_allow_html=True)
                    if df_clients_merged.empty:
                        st.info("Нет клиентов с продажами по выбранному менеджеру и году.")
                    else:
                        for idx, row in df_clients_merged.iterrows():
                            expander_label = f"{row['Клиент']} — {int(row['Факт']):,} руб."
                            with st.expander(label=expander_label, expanded=False):
                                conn = sqlite3.connect(DB_PATH)
                                df_products = pd.read_sql_query(
                                    '''
                                    SELECT p.code_ap, SUM(s.revenue) as Сумма_продаж
                                    FROM sales s
                                    LEFT JOIN products p ON s.product_code = p.code
                                    WHERE s.client_code = ? AND s.manager = ? AND s.year = ?
                                    GROUP BY p.code_ap
                                    ORDER BY Сумма_продаж DESC
                                    ''',
                                    conn, params=(row['client_code'], selected_manager, str(selected_year))
                                )
                                conn.close()
                                if not df_products.empty:
                                    st.dataframe(df_products.rename(
                                        columns={'code_ap': 'Код продукции', 'Сумма_продаж': 'Сумма продаж'}
                                    ), use_container_width=True)
                                else:
                                    st.info("Нет данных по продукции для этого клиента.")
                else:
                    st.info('Нет совпадений в справочнике клиентов. Показываю только по данным sales:')
                    df_clients_simple = df_clients[['client_code', 'Факт']].copy()
                    df_clients_simple = df_clients_simple.rename(columns={'client_code': 'Клиент'})
                    st.markdown(f"<b>Найдено клиентов: {len(df_clients_simple)}</b>", unsafe_allow_html=True)
                    if df_clients_simple.empty:
                        st.info("Нет клиентов с продажами по выбранному менеджеру и году.")
                    else:
                        for idx, row in df_clients_simple.iterrows():
                            expander_label = f"{row['Клиент']} — {int(row['Факт']):,} руб."
                            with st.expander(label=expander_label, expanded=False):
                                conn = sqlite3.connect(DB_PATH)
                                df_products = pd.read_sql_query(
                                    '''
                                    SELECT p.code_ap, SUM(s.revenue) as Сумма_продаж
                                    FROM sales s
                                    LEFT JOIN products p ON s.product_code = p.code
                                    WHERE s.client_code = ? AND s.manager = ? AND s.year = ?
                                    GROUP BY p.code_ap
                                    ORDER BY Сумма_продаж DESC
                                    ''',
                                    conn, params=(row['Клиент'], selected_manager, str(selected_year))
                                )
                                conn.close()
                                if not df_products.empty:
                                    st.dataframe(df_products.rename(
                                        columns={'code_ap': 'Код продукции', 'Сумма_продаж': 'Сумма продаж'}
                                    ), use_container_width=True)
                                else:
                                    st.info("Нет данных по продукции для этого клиента.")
            else:
                st.info('Нет данных по выбранному менеджеру.')

        if set(['Факт', 'План']).issubset(df_year['Тип'].unique()):
            pivot = df_year.pivot(index='Месяц_назв', columns='Тип', values='Выручка').fillna(0)
            pivot['Отклонение'] = pivot['Факт'] - pivot['План']
            pivot['Отклонение, %'] = ((pivot['Факт'] - pivot['План']) / pivot['План'] * 100).round(1)
            st.markdown("<h4 style='color:#566573;'>Отклонение от плана по месяцам</h4>", unsafe_allow_html=True)

            def highlight(val):
                if isinstance(val, (int, float)):
                    if val > 0:
                        color = 'background-color: #d4edda; color: #155724;'  # зелёный
                    elif val < 0:
                        color = 'background-color: #f8d7da; color: #721c24;'  # красный
                    else:
                        color = ''
                    return color
                return ''

            styled = pivot[['Факт', 'План', 'Отклонение', 'Отклонение, %']].style.applymap(
                highlight, subset=['Отклонение', 'Отклонение, %']
            )
            st.dataframe(styled, use_container_width=True)

# Складские остатки
elif menu == "📦 Складские остатки":
    st.markdown("""
        <h1 style='text-align:center; color:#2E4053; margin-bottom:0.5em;'>📦 Складские остатки</h1>
        <hr style='border:1px solid #eee; margin-bottom:2em;'>
    """, unsafe_allow_html=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        dates_df = pd.read_sql_query("SELECT DISTINCT report_date FROM stock_balance ORDER BY report_date DESC", conn)
        conn.close()

        # Преобразуем дату в человекочитаемый формат
        dates_df['report_date'] = pd.to_datetime(dates_df['report_date'])
        dates_df['label'] = dates_df['report_date'].dt.strftime('%-d %B %Y').str.capitalize()
        date_mapping = dict(zip(dates_df['label'], dates_df['report_date']))

        # Список дат для selectbox
        selected_label = st.selectbox("Выберите дату отчета:", list(date_mapping.keys()))
        selected_date = date_mapping[selected_label]

        st.info(f"📅 Отображаются данные за дату: {selected_label}")

        # Теперь выполняем запрос с выбранной датой
        conn = sqlite3.connect(DB_PATH)
        df_all = pd.read_sql_query(
            """
            SELECT warehouse as Склад, nomenclature_type as Группа,
                   article as Артикул, quantity as Количество, value as Сумма
            FROM stock_balance
            WHERE report_date = ?
            """,
            conn, params=(selected_date.strftime('%Y-%m-%d'),)
        )
    finally:
        conn.close()

    total_qty_all = df_all['Количество'].sum()
    total_val_all = df_all['Сумма'].sum()
    st.markdown(f"""
        <div style="
            background-color: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        ">
            <strong>ИТОГО по всем складам:</strong>
            {total_qty_all:,.0f} шт., {total_val_all:,.0f} руб.
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<h3 style='color:#34495E;'>Итоги по складам</h3>", unsafe_allow_html=True)
    summary = (
        df_all
        .groupby('Склад')
        .agg({'Количество':'sum','Сумма':'sum'})
        .reset_index()
    )
    summary['Количество'] = summary['Количество'].map(lambda x: f"{x:,.0f}")
    summary['Сумма'] = summary['Сумма'].map(lambda x: f"{x:,.0f}")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    warehouses = ['Все склады'] + df_all['Склад'].unique().tolist()
    selected_wh = st.selectbox("Выберите склад для детализации:", warehouses)

    df = df_all if selected_wh == 'Все склады' else df_all[df_all['Склад'] == selected_wh]
    st.markdown("<h3 style='color:#34495E;'>Детализация по складу и группам товаров</h3>", unsafe_allow_html=True)

    for wh, df_wh in df.groupby('Склад'):
        wh_qty = df_wh['Количество'].sum()
        wh_val = df_wh['Сумма'].sum()
        with st.expander(f"📦 Склад: {wh} — {wh_qty:,.0f} шт., {wh_val:,.0f} руб.", expanded=False):
            groups = df_wh['Группа'].unique().tolist()
            selected_grp = st.selectbox(f"Группа на складе «{wh}»", groups, key=wh)
            df_grp = df_wh[df_wh['Группа'] == selected_grp]

            grp_qty = df_grp['Количество'].sum()
            grp_val = df_grp['Сумма'].sum()
            st.write(f"**Группа:** {selected_grp} — {grp_qty:,.0f} шт., {grp_val:,.0f} руб.")

            st.table(
                df_grp[['Артикул','Количество','Сумма']]
                  .sort_values('Артикул')
                  .reset_index(drop=True)
                  .assign(
                      Количество=lambda d: d['Количество'].map(lambda x: f"{x:,.0f}"),
                      Сумма=lambda d: d['Сумма'].map(lambda x: f"{x:,.0f}")
                  )
            )



elif menu == "📊 Производство":
    from updater.production_updater import update_production_data

    st.markdown("""
        <h1 style='text-align:center; color:#2E4053; margin-bottom:0.5em;'>📊 Исполнение производства</h1>
        <hr style='border:1px solid #eee; margin-bottom:2em;'>
    """, unsafe_allow_html=True)

    if update_production_data():
        st.success("Данные по производству обновлены")
    else:
        st.info("Нет новых данных или ошибка при обновлении")

    # Подключение к БД
    conn = sqlite3.connect(DB_PATH)
    df_prod = pd.read_sql_query("""
        SELECT article AS Артикул,
               nomenclature_desc AS Описание,
               plan AS План,
               fact AS Факт
        FROM production_exec
        WHERE LOWER(article) != 'итого'
    """, conn)
    conn.close()

    if df_prod.empty:
        st.warning("Нет данных по исполнению производства.")
    else:
        import numpy as np
        df_prod['Отклонение'] = df_prod['Факт'] - df_prod['План']
        df_prod['Отклонение, %'] = (df_prod['Отклонение'] / df_prod['План'].replace({0: np.nan}) * 100).round(1)

        total_plan = int(df_prod['План'].sum())
        total_fact = int(df_prod['Факт'].sum())
        deviation = total_fact - total_plan
        deviation_pct = (deviation / total_plan * 100) if total_plan else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Итого План", f"{total_plan:,}")
        col2.metric("Итого Факт", f"{total_fact:,}")
        col3.metric("Отклонение", f"{deviation:,}", f"{deviation_pct:.1f}%")

        st.markdown("<h3 style='color:#34495E;'>Детализация по артикулу</h3>", unsafe_allow_html=True)

        styled = (
            df_prod[['Артикул', 'Описание', 'План', 'Факт', 'Отклонение', 'Отклонение, %']]
            .sort_values('Отклонение, %', ascending=False)
            .reset_index(drop=True)
            .style.format({
                'План': '{:,.0f}',
                'Факт': '{:,.0f}',
                'Отклонение': '{:,.0f}',
                'Отклонение, %': '{:.1f}%'
            })
            .applymap(lambda v: (
                'background-color: #d4edda; color: #155724;' if v > 0 else
                'background-color: #f8d7da; color: #721c24;' if v < 0 else ''
            ) if isinstance(v, (int, float)) else '', subset=['Отклонение', 'Отклонение, %'])
        )
        st.dataframe(styled, use_container_width=True)




elif menu == "🌍 Логистика":
    st.markdown("<div class='transparent-box'>", unsafe_allow_html=True)
    st.header("Логистика")
    st.write("Отображение логистики.")
    st.markdown("</div>", unsafe_allow_html=True)


elif menu == "Закупки":
    st.markdown("<h1 style='text-align:center;'>📦 Закупки</h1>", unsafe_allow_html=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM purchases ORDER BY report_date DESC", conn)
        if df.empty:
            st.info("Нет данных по закупкам.")
        else:
            # Фильтр по дате
            available_dates = sorted(df['report_date'].unique(), reverse=True)
            selected_date = st.selectbox("Выберите дату отчета:", available_dates)
            df_filtered = df[df['report_date'] == selected_date]
            st.info(
            f"Поставщиков: {df_filtered['supplier'].nunique()}. "
            f"Сумма закупок с НДС: {df_filtered['total_with_vat'].sum():,.0f} руб."
        )


            # st.info(f"Показаны закупки за {selected_date}. Поставщиков: {df_filtered['supplier'].nunique()}")

            for supplier in df_filtered['supplier'].unique():
                supplier_df = df_filtered[df_filtered['supplier'] == supplier]
                total_sum = supplier_df['total_with_vat'].sum()
                with st.expander(f"{supplier} — {total_sum:,.0f} руб.", expanded=False):
                    st.dataframe(
                        supplier_df[["product", "quantity", "price_per_unit", "total", "total_with_vat"]]
                        .rename(columns={
                            "product": "Товар",
                            "quantity": "Кол-во",
                            "price_per_unit": "Цена",
                            "total": "Сумма",
                            "total_with_vat": "Сумма с НДС"
                        }),
                        use_container_width=True
                    )
    except Exception as e:
        st.error(f"Ошибка при загрузке закупок: {e}")
    finally:
        conn.close()