# performance.py
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

    tickers_in_portfolio = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers_in_portfolio = sorted(st.session_state.df['Ticker'].dropna().unique().tolist())

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE PAR BOUTONS INLINE ---

    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
    }

    if "selected_ticker_table_period" not in st.session_state:
        st.session_state.selected_ticker_table_period = "1W"

    # CSS personnalisé pour aligner les boutons horizontalement
    st.markdown("""
        <style>
        .period-buttons-container {
            display: flex;
            flex-direction: row;
            gap: 16px; /* Espacement entre les boutons en pixels (ajustez selon besoin) */
            margin-bottom: 1rem;
            align-items: center;
        }
        .period-button {
            padding: 4px 8px;
            font-size: 1rem;
            border: none;
            background-color: transparent;
            cursor: pointer;
            color: var(--text-color, #000000);
            transition: color 0.2s;
        }
        .period-button:hover {
            text-decoration: underline;
        }
        .period-button-selected {
            color: var(--secondary-color, #1f77b4);
            font-weight: bold;
            text-decoration: none;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("##### Cours de Clôture des Derniers Jours")
    st.markdown('<div class="period-buttons-container">', unsafe_allow_html=True)
    for label in period_options:
        button_class = "period-button-selected" if st.session_state.selected_ticker_table_period == label else "period-button"
        if st.button(
            label,
            key=f"period_{label}",
            help=f"Sélectionner la période {label}",
            use_container_width=False,
            type="secondary" if st.session_state.selected_ticker_table_period != label else "primary"
        ):
            st.session_state.selected_ticker_table_period = label
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td

    with st.spinner("Récupération des cours des tickers en cours..."):
        last_days_data = {}
        fetch_start_date = start_date_table - timedelta(days=10)
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            st.write(f"Traitement de {ticker}")
            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            st.write(f"Données pour {ticker} : {data.shape}, Vide : {data.empty}")
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                last_days_data[ticker] = filtered_data
            else:
                last_days_data[ticker] = pd.Series(dtype='float64')

        df_display_prices = pd.DataFrame()
        for ticker, series in last_days_data.items():
            st.write(f"Série pour {ticker} : {series.shape}, Vide : {series.empty}")
            if not series.empty:
                temp_df = pd.DataFrame(series.rename("Cours").reset_index())
                temp_df.columns = ["Date", "Cours"]
                temp_df["Ticker"] = ticker
                df_display_prices = pd.concat([df_display_prices, temp_df])

        if not df_display_prices.empty:
            st.write(f"df_display_prices : {df_display_prices.shape}, Colonnes : {df_display_prices.columns.tolist()}")
            df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours")
            st.write(f"df_pivot avant filtrage : {df_pivot.shape}, Colonnes : {df_pivot.columns.tolist()}")
            df_pivot = df_pivot.sort_index(axis=1)
            df_pivot = df_pivot.loc[:, (df_pivot.columns >= pd.Timestamp(start_date_table)) & (df_pivot.columns <= pd.Timestamp(end_date_table))]
            st.write(f"df_pivot après filtrage : {df_pivot.shape}, Colonnes : {df_pivot.columns.tolist()}")
            df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]

            # Formatage avec fonction lambda pour gérer chaque valeur
            st.dataframe(
                df_pivot.style.format(lambda x: format_fr(x, decimal_places=2) if pd.notnull(x) and isinstance(x, (int, float, np.number)) else "N/A"),
                use_container_width=True
            )
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")
