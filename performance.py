# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import builtins

from historical_data_fetcher import fetch_stock_history
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique du portefeuille basée sur sa composition actuelle,
    et un tableau des derniers cours de clôture pour tous les tickers, avec sélection de plage de dates.
    """
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres'.")
        return

    df_current_portfolio = st.session_state.df.copy()
    target_currency = st.session_state.get("devise_cible", "EUR")

    tickers_in_portfolio = []
    if "Ticker" in df_current_portfolio.columns:
        tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist())

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE ---
    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=5*365),
        "10Y": timedelta(days=10*365),
    }

    if 'selected_ticker_table_period' not in st.session_state:
        st.session_state.selected_ticker_table_period = "1W"

    st.markdown("#### Sélection de la période d'affichage des cours")

    cols = st.columns(len(period_options))
    for col, (label, _) in zip(cols, period_options.items()):
        if col.button(label, key=f"period_btn_{label}"):
            st.session_state.selected_ticker_table_period = label
            st.rerun()

    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td

    with st.spinner("Récupération des cours des tickers..."):
        last_days_data = {}
        fetch_start_date = start_date_table - timedelta(days=10)
        business_days = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days).ffill().bfill()
                last_days_data[ticker] = filtered_data
            else:
                last_days_data[ticker] = pd.Series(dtype='float64')

        df_display_prices = pd.DataFrame()
        for ticker, series in last_days_data.items():
            if not series.empty:
                temp_df = pd.DataFrame(series.rename("Cours").reset_index())
                temp_df.columns = ["Date", "Cours"]
                temp_df["Ticker"] = ticker
                df_display_prices = pd.concat([df_display_prices, temp_df])

        if not df_display_prices.empty:
            df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours")
            df_pivot = df_pivot.sort_index(axis=1)
            df_pivot = df_pivot.loc[:, (df_pivot.columns >= pd.Timestamp(start_date_table)) & (df_pivot.columns <= pd.Timestamp(end_date_table))]
            df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]

            st.markdown("##### Cours de Clôture des Derniers Jours")
            st.dataframe(df_pivot.style.format(format_fr), use_container_width=True)
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")
