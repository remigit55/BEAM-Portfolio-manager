# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay  # Pour les jours ouvrables
import yfinance as yf
import builtins  # Pour contourner l'écrasement de str()

# Import des fonctions nécessaires
from historical_data_fetcher import fetch_stock_history, get_all_historical_data
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr
from portfolio_display import convertir  # Importer la fonction de conversion

# Fonction de test temporaire pour fetch_fx_rates
def fetch_fx_rates_dummy(target_currency):
    """Fonction temporaire pour tester avec des taux fixes."""
    return {"USD": 0.8532999753952026, "EUR": 1.0, "GBP": 1.1700999736785889,
            "CAD": 0.6233999729156494, "AUD": 0.5570999979972839,
            "HKD": 0.10864999890327454, "CNY": 0.11892999708652496,
            "SGD": 0.6685199737548828}  # Taux basés sur vos logs

def display_performance_history():
    """
    Affiche la performance historique du portefeuille basée sur sa composition actuelle,
    et un tableau des derniers cours de clôture pour tous les tickers, avec sélection de plage de dates.
    """
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        return

    df_current_portfolio = st.session_state.df.copy()
    target_currency = st.session_state.get("devise_cible", "EUR")

    # Initialisation des taux de change avec une valeur par défaut pour tester
    if "fx_rates" not in st.session_state or st.session_state.fx_rates is None:
        st.write("Initialisation des taux de change (mode test)...")
        st.session_state.fx_rates = fetch_fx_rates_dummy(target_currency)
        st.write("Taux de change chargés :", st.session_state.fx_rates)

    fx_rates = st.session_state.fx_rates

    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE AVEC ST.RADIO ---
    period_options = {"1W": timedelta(weeks=1), "1M": timedelta(days=30), "3M": timedelta(days=90),
                      "6M": timedelta(days=180), "1Y": timedelta(days=365), "5Y": timedelta(days=365 * 5),
                      "10Y": timedelta(days=365 * 10)}
    period_labels = list(period_options.keys())
    current_selected_label = st.session_state.get("selected_ticker_table_period_label", "1W")
    if current_selected_label not in period_labels:
        current_selected_label = "1W"
    default_period_index = period_labels.index(current_selected_label)

    selected_label = st.radio("", period_labels, index=default_period_index,
                             key="selected_ticker_table_period_radio", horizontal=True)
    st.session_state.selected_ticker_table_period_label = selected_label
    selected_period_td = period_options[selected_label]

    # --- FIN SÉLECTION DE PÉRIODE ---

    end_date_table = datetime.now().date()
    start_date_table = end_date_table - selected_period_td

    with st.spinner("Récupération des cours des tickers en cours..."):
        last_days_data = {}
        fetch_start_date = start_date_table - timedelta(days=10)
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            ticker_devise = target_currency
            if "Devise" in df_current_portfolio.columns and ticker in df_current_portfolio["Ticker"].values:
                ticker_devise_row = df_current_portfolio[df_current_portfolio["Ticker"] == ticker]["Devise"]
                if not ticker_devise_row.empty and pd.notnull(ticker_devise_row.iloc[0]):
                    ticker_devise = str(ticker_devise_row.iloc[0]).strip().upper()
            st.write(f"Ticker: {ticker}, Devise: {ticker_devise}")

            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                converted_data = pd.Series(index=filtered_data.index, dtype=float)
                for date, price in filtered_data.items():
                    converted_price, fx_rate = convertir(price, ticker_devise, target_currency, fx_rates)
                    if pd.isna(converted_price) or pd.isna(fx_rate):
                        st.warning(f"Conversion échouée pour {ticker} le {date.strftime('%Y-%m-%d')}: taux manquant pour {ticker_devise}. Utilisation de la valeur originale: {price}")
                        converted_data[date] = price
                    else:
                        converted_data[date] = converted_price
                    st.write(f"Date: {date}, Prix original: {price}, Prix converti: {converted_price}, Taux: {fx_rate}")
                last_days_data[ticker] = converted_data
            else:
                last_days_data[ticker] = pd.Series(dtype='float64')

        # Construction de df_display_prices
        df_display_prices = pd.DataFrame()
        for ticker, series in last_days_data.items():
            if not series.empty:
                temp_df = pd.DataFrame({"Date": series.index, "Cours": series.values})
                temp_df["Ticker"] = ticker
                df_display_prices = pd.concat([df_display_prices, temp_df], ignore_index=True)
                st.write(f"Données converties pour {ticker}:", temp_df)

        if not df_display_prices.empty:
            df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours", dropna=False)
            df_pivot = df_pivot.sort_index(axis=1)
            df_pivot = df_pivot.loc[:, (df_pivot.columns >= pd.Timestamp(start_date_table)) & (df_pivot.columns <= pd.Timestamp(end_date_table))]

            df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]
            st.write("DataFrame pivot avant formatage :", df_pivot)  # Débogage
            st.dataframe(df_pivot.style.format(lambda x: f"{format_fr(x, 2)} {target_currency}" if pd.notnull(x) else "N/A"),
                         use_container_width=True)
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")

if __name__ == "__main__":
    display_performance_history()
