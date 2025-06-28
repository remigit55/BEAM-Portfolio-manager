import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import builtins

from historical_data_fetcher import fetch_stock_history, get_all_historical_data
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr
from portfolio_display import convertir

def fetch_historical_fx_rates(target_currency, start_date, end_date):
    """Récupère les taux de change historiques via yfinance."""
    base_currencies = ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP"]
    fx_rates = {}
    for base in base_currencies:
        # Utiliser des paires disponibles sur yfinance (e.g., HKD=X pour HKD/USD)
        pair = f"{base}USD=X" if base != "USD" else f"USD{target_currency}=X"
        try:
            fx_data = yf.download(pair, start=start_date - timedelta(days=10), end=end_date, interval="1d")
            if not fx_data.empty:
                # Renommer la colonne Close avec la paire de devises
                fx_rates[f"{base}USD"] = fx_data["Close"]
                if base == "USD" and target_currency != "USD":
                    # Récupérer le taux USD vers la devise cible (e.g., USDEUR=X)
                    target_pair = f"USD{target_currency}=X"
                    target_data = yf.download(target_pair, start=start_date - timedelta(days=10), end=end_date, interval="1d")
                    if not target_data.empty:
                        fx_rates[f"USD{target_currency}"] = target_data["Close"]
        except Exception as e:
            st.warning(f"Échec du téléchargement des taux pour {pair}: {e}")
    # Combiner en un DataFrame, avec remplissage par 1.0 si manquant
    df_fx = pd.DataFrame(fx_rates)
    if df_fx.empty:
        st.warning("Aucun taux de change récupéré. Utilisation de taux par défaut (1.0).")
        df_fx = pd.DataFrame(index=pd.date_range(start=start_date, end=end_date), columns=[f"{c}{target_currency}" for c in base_currencies], data=1.0)
    else:
        # Aligner les index et interpoler les valeurs manquantes
        df_fx = df_fx.reindex(pd.date_range(start=start_date - timedelta(days=10), end=end_date)).interpolate().ffill().bfill()
    return df_fx

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

    if "fx_rates" not in st.session_state or st.session_state.fx_rates is None:
        st.write("Récupération des taux de change historiques...")
        end_date_table = datetime.now().date()
        start_date_table = end_date_table - timedelta(days=365 * 10)  # Période max pour tester
        st.session_state.fx_rates = fetch_historical_fx_rates(target_currency, start_date_table, end_date_table)
        if st.session_state.fx_rates is None:
            st.session_state.fx_rates = pd.DataFrame()  # Fallback vide

    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

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
                    date_str = date.date()
                    fx_rates = st.session_state.fx_rates
                    if not fx_rates.empty:
                        fx_rate = fx_rates[f"{ticker_devise}USD"].get(date_str, None)
                        if fx_rate is not None and ticker_devise != target_currency and f"USD{target_currency}" in fx_rates.columns:
                            target_rate = fx_rates[f"USD{target_currency}"].get(date_str, 1.0)
                            fx_rate = fx_rate * (1 / target_rate) if target_rate != 0 else 1.0  # Conversion inverse si besoin
                        elif fx_rate is None:
                            fx_rate = 1.0
                    else:
                        fx_rate = 1.0
                    converted_price, _ = convertir(price, ticker_devise, target_currency, {ticker_devise: fx_rate})
                    converted_data[date] = converted_price
                    st.write(f"Date: {date_str}, Prix original: {price}, Prix converti: {converted_price}, Taux: {fx_rate}")
                last_days_data[ticker] = converted_data
            else:
                last_days_data[ticker] = pd.Series(dtype='float64')

        df_display_prices = pd.DataFrame()
        for ticker, series in last_days_data.items():
            if not series.empty:
                temp_df = pd.DataFrame({
                    "Date": series.index,
                    "Cours": series.values,
                    "Ticker": ticker
                })
                df_display_prices = pd.concat([df_display_prices, temp_df], ignore_index=True)
                st.write(f"Données converties pour {ticker}:", temp_df)

        if not df_display_prices.empty:
            df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours", dropna=False)
            df_pivot = df_pivot.sort_index(axis=1)
            df_pivot = df_pivot.loc[:, (df_pivot.columns >= pd.Timestamp(start_date_table)) & (df_pivot.columns <= pd.Timestamp(end_date_table))]

            df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]
            st.write("DataFrame pivot avant formatage:", df_pivot)
            st.dataframe(df_pivot.style.format(lambda x: f"{format_fr(x, 2)} {target_currency}" if pd.notnull(x) else "N/A"),
                         use_container_width=True)
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")

if __name__ == "__main__":
    display_performance_history()
