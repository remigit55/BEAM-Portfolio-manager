# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf
from historical_data_fetcher import fetch_stock_history
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique des prix d'un ticker sélectionné dans le portefeuille.
    Version épurée sans tests ni aperçus.
    """
    st.subheader("Historique d’un Ticker du Portefeuille")

    # Récupérer la liste des tickers
    tickers = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers = sorted(st.session_state.df['Ticker'].dropna().unique())
    
    if not tickers:
        st.warning("Aucun ticker trouvé dans le portefeuille. Veuillez importer un fichier CSV via l'onglet 'Paramètres'.")
        return

    selected_ticker = st.selectbox(
        "Sélectionnez un symbole boursier du portefeuille",
        options=tickers,
        index=0,
        help="Choisissez un ticker pour afficher son historique."
    )

    nb_days = st.slider("Nombre de jours d'historique à afficher", 1, 3650, 180)

    start_date = datetime.now() - timedelta(days=nb_days)
    end_date = datetime.now()

    try:
        data = yf.download(
            selected_ticker,
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            progress=False
        )

        if not data.empty:
            st.subheader(f"Graphique de clôture – {selected_ticker}")
            st.line_chart(data['Close'])
        else:
            st.warning(f"Aucune donnée disponible pour {selected_ticker} sur la période sélectionnée.")
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données : {str(e)}")
