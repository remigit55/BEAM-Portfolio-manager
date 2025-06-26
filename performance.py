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

    # Définir les options de période et leur timedelta correspondant
    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),  # Environ 1 mois
        "3M": timedelta(days=90),  # Environ 3 mois
        "6M": timedelta(days=180), # Environ 6 mois
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
    }

    # Initialiser la période sélectionnée dans le session state si elle n'est pas déjà définie
    if 'selected_ticker_table_period' not in st.session_state:
        st.session_state.selected_ticker_table_period = "1W" # Période par défaut

    st.markdown("Sélectionnez une période pour les cours des tickers :")
    cols_period_buttons = st.columns(len(period_options))
    for i, (label, period_td) in enumerate(period_options.items()):
        with cols_period_buttons[i]:
            if st.button(label, key=f"period_btn_{label}"):
                st.session_state.selected_ticker_table_period = label
                # Forcer un rerun pour que la table se mette à jour avec la nouvelle période
                st.rerun() 

    # Calculer start_date et end_date en fonction de la période sélectionnée
    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td

    # Assurez-vous que la date de début n'est pas avant une date raisonnable (ex: début de yfinance)
    # earliest_date_yfinance = datetime(1900, 1, 1).date()
    # if start_date_table < earliest_date_yfinance:
    #     start_date_table = earliest_date_yfinance

    st.info(f"Affichage des cours de clôture pour les tickers du portefeuille sur la période : {start_date_table.strftime('%d/%m/%Y')} à {end_date_table.strftime('%d/%m/%Y')}.")

    # La logique de récupération et d'affichage de la table s'exécute à chaque rerun
    with st.spinner("Récupération des cours des tickers en cours..."):
        last_days_data = {}
        # Récupère un peu plus de jours pour être sûr d'avoir suffisamment de données ouvrables
        fetch_start_date = start_date_table - timedelta(days=10) 

        # Générer les jours ouvrables pour la période sélectionnée
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                # Re-indexer sur les jours ouvrables exacts de la période sélectionnée
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                last_days_data[ticker] = filtered_data
            else:
                last_days_data[ticker] = pd.Series(dtype='float64') # Vide si pas de données

        # Création d'un DataFrame pour l'affichage
        df_display_prices = pd.DataFrame()
        for ticker, series in last_days_data.items():
            if not series.empty:
                temp_df = pd.DataFrame(series.rename("Cours").reset_index())
                temp_df.columns = ["Date", "Cours"]
                temp_df["Ticker"] = ticker
                df_display_prices = pd.concat([df_display_prices, temp_df])

        if not df_display_prices.empty:
            # Pivoter le DataFrame pour avoir les dates en colonnes
            df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours")
            # Trier les colonnes de date
            df_pivot = df_pivot.sort_index(axis=1)
            
            # Filtrer les colonnes pour n'afficher que les dates dans la période sélectionnée
            df_pivot = df_pivot.loc[:, (df_pivot.columns >= pd.Timestamp(start_date_table)) & (df_pivot.columns <= pd.Timestamp(end_date_table))]

            # Renommer les colonnes de date pour un affichage plus lisible
            df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]
            
            st.markdown("##### Cours de Clôture des Derniers Jours")
            st.dataframe(df_pivot.style.format(format_fr), use_container_width=True)
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")
