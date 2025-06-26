# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf
import builtins
from historical_data_fetcher import fetch_stock_history
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique des prix d'un ticker sélectionné dans le portefeuille.
    Version simplifiée sans aperçu de données.
    """
    st.subheader("Test de Performance Historique")

    # Récupération des tickers du portefeuille
    tickers = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers = sorted(st.session_state.df['Ticker'].dropna().unique())
    
    if not tickers:
        st.warning("Aucun ticker trouvé dans le portefeuille. Veuillez importer un fichier CSV via l'onglet 'Paramètres'.")
        st.selectbox("Sélectionnez un symbole boursier", options=["Aucun ticker disponible"], index=0, disabled=True)
        return

    test_ticker = st.selectbox(
        "Sélectionnez un symbole boursier du portefeuille",
        options=tickers,
        index=0,
        help="Choisissez un ticker pour afficher son historique."
    )

    test_days_ago = st.slider("Nombre de jours d'historique à récupérer", 1, 3650, 30)

    if st.button("Lancer le test de récupération Yahoo Finance"):
        start_date = datetime.now() - timedelta(days=test_days_ago)
        end_date = datetime.now()

        st.info(f"Récupération des données pour **{test_ticker}** du **{start_date.strftime('%Y-%m-%d')}** au **{end_date.strftime('%Y-%m-%d')}**...")

        try:
            data = yf.download(test_ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)

            if not data.empty:
                st.success(f"✅ Données récupérées pour {test_ticker}")
                st.subheader("Graphique des cours de clôture")
                st.line_chart(data['Close'])

            else:
                st.warning(f"❌ Aucune donnée récupérée pour {test_ticker}. Vérifiez le symbole et la période.")

        except Exception as e:
            st.error(f"Erreur lors de la récupération des données : {builtins.str(e)}")
            if "str' object is not callable" in builtins.str(e):
                st.error("⚠️ La fonction native `str()` semble avoir été écrasée. Vérifiez qu’aucune variable nommée `str` n’existe dans votre code.")
