# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay # Pour les jours ouvrables
import yfinance as yf
import builtins # Pour contourner l'écrasement de str()

# Import des fonctions nécessaires
from historical_data_fetcher import fetch_stock_history, get_all_historical_data
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique du portefeuille basée sur sa composition actuelle,
    et un tableau des derniers cours de clôture pour tous les tickers, avec sélection de plage de dates.
    """
    # Vérifier si le portefeuille est chargé
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        return

    df_current_portfolio = st.session_state.df.copy()
    target_currency = st.session_state.get("devise_cible", "EUR")

    # Section pour le tableau des derniers cours de clôture par ticker

    tickers_in_portfolio = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers_in_portfolio = sorted(st.session_state.df['Ticker'].dropna().unique().tolist())

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE PAR BOUTONS POUR LE TABLEAU DES COURS ---
    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),  # Environ 1 mois
        "3M": timedelta(days=90),  # Environ 3 mois
        "6M": timedelta(days=180), # Environ 6 mois
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
    }

    if 'selected_ticker_table_period' not in st.session_state:
        st.session_state.selected_ticker_table_period = "1W" # Période par défaut
  
     # Utilisation de st.markdown avec du CSS pour aligner les boutons et ajouter un espacement
    st.markdown("""
        <style>
        .button-row-container {
            display: flex;
            flex-wrap: wrap; /* Permet aux boutons de passer à la ligne si l'espace est insuffisant */
            justify-content: flex-start; /* Aligne les boutons à gauche */
            gap: 5px; /* Crée un espacement de 5px entre les boutons */
            margin-bottom: 10px; /* Ajoute un peu d'espace sous les boutons */
        }
        /* Assurez-vous que les boutons Streamlit n'ont pas de marges par défaut conflictuelles */
        div.stButton > button {
            margin: 0 !important; /* Supprime les marges par défaut des boutons Streamlit */
        }
        </style>
    """, unsafe_allow_html=True)

    # Créer les boutons à l'intérieur d'un conteneur HTML avec la classe CSS définie
    st.markdown('<div class="button-row-container">', unsafe_allow_html=True)
    for i, (label, period_td) in enumerate(period_options.items()):
        if st.button(label, key=f"period_btn_{label}"):
            st.session_state.selected_ticker_table_period = label
            st.rerun() 
    st.markdown('</div>', unsafe_allow_html=True) # Ferme le conteneur HTML

    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td

    with st.spinner("Récupération des cours des tickers en cours..."):
        last_days_data = {}
        fetch_start_date = start_date_table - timedelta(days=10) 

        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
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
