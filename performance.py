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

    # Synchroniser les taux de change avec portfolio_display.py
    if "fx_rates" not in st.session_state or st.session_state.fx_rates is None:
        devises_uniques = df_current_portfolio["Devise"].dropna().str.strip().str.upper().unique().tolist()
        devises_a_fetch = list(set([target_currency] + devises_uniques))
        st.session_state.fx_rates = {}  # Initialisation temporaire
        # Ici, on suppose que fetch_fx_rates est disponible (à importer si nécessaire)
        from data_fetcher import fetch_fx_rates  # Ajout de l'import
        st.session_state.fx_rates = fetch_fx_rates(target_currency)

    fx_rates = st.session_state.fx_rates

    tickers_in_portfolio = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers_in_portfolio = sorted(st.session_state.df['Ticker'].dropna().unique().tolist())

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE AVEC ST.RADIO (COMPOSANT NATIF STREAMLIT) ---

    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
    }
    
    # Options pour le sélecteur
    period_labels = list(period_options.keys())

    # Récupérer la période sélectionnée depuis session_state, avec "1W" comme défaut
    # S'assurer que la valeur est valide avant de chercher son index
    current_selected_label = st.session_state.get("selected_ticker_table_period_label", "1W")
    if current_selected_label not in period_labels:
        current_selected_label = "1W"  # Revenir à un défaut valide si la valeur stockée est invalide

    default_period_index = period_labels.index(current_selected_label)

    selected_label = st.radio(
        "",
        period_labels,
        index=default_period_index,
        key="selected_ticker_table_period_radio",
        horizontal=True  # Affiche les options horizontalement si l'espace le permet
    )
    
    # Mettre à jour la session_state pour stocker l'étiquette sélectionnée
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
            # Récupérer la devise associée au ticker
            ticker_devise = df_current_portfolio[df_current_portfolio["Ticker"] == ticker]["Devise"].iloc[0] \
                if ticker in df_current_portfolio["Ticker"].values else target_currency
            ticker_devise = str(ticker_devise).strip().upper()

            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                # Convertir chaque cours vers la devise cible
                converted_data = pd.Series(index=filtered_data.index, dtype=float)
                for date, price in filtered_data.items():
                    converted_price, _ = convertir(price, ticker_devise, target_currency, fx_rates)
                    converted_data[date] = converted_price if pd.notnull(converted_price) else price
                last_days_data[ticker] = converted_data
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
            
            # Afficher avec formatage
            st.dataframe(df_pivot.style.format(lambda x: format_fr(x, 2) + f" {target_currency}" if pd.notnull(x) else "", na_rep="N/A"), 
                         use_container_width=True)
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")

if __name__ == "__main__":
    display_performance_history()
