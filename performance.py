# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf
import builtins
from utils import format_fr


def display_performance_history():
    """
    Affiche automatiquement la performance historique des prix d'un ticker sélectionné dans le portefeuille.
    Version sans bouton ni test manuel.
    """
    st.subheader("Performance Historique")

    # Récupération des tickers disponibles dans le portefeuille
    tickers = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers = sorted(st.session_state.df['Ticker'].dropna().unique())

    if not tickers:
        st.warning("Aucun ticker trouvé dans le portefeuille. Veuillez importer un fichier CSV via l'onglet 'Paramètres'.")
        st.selectbox("Sélectionnez un symbole boursier", options=["Aucun ticker disponible"], index=0, disabled=True)
        return

    # Choix du ticker et de la période
    selected_ticker = st.selectbox(
        "Sélectionnez un symbole boursier du portefeuille",
        options=tickers,
        index=0
    )
    days_range = st.slider("Nombre de jours d'historique à afficher", min_value=30, max_value=3650, value=365)

    # Récupération et affichage automatique
    start_date = datetime.now() - timedelta(days=days_range)
    end_date = datetime.now()

    try:
        data = yf.download(selected_ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)

        if not data.empty and "Close" in data.columns:
            st.line_chart(data["Close"], use_container_width=True)
        else:
            st.warning(f"Aucune donnée disponible pour {selected_ticker} sur la période sélectionnée.")

    except Exception as e:
        st.error(f"Erreur lors de la récupération des données pour {selected_ticker} : {builtins.str(e)}")
        if "'str' object is not callable" in builtins.str(e):
            st.error("⚠️ La fonction native `str()` semble avoir été écrasée. Vérifiez qu’aucune variable nommée `str` n’existe dans votre code.")
