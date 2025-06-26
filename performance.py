import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from historical_data_fetcher import fetch_stock_history as fetch_stock_history_converted
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique d’un ticker convertie dans la devise cible (ex: EUR).
    """
    # Extraction des tickers depuis le portefeuille
    tickers = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers = sorted(st.session_state.df['Ticker'].dropna().unique())
    
    if not tickers:
        st.warning("Aucun ticker trouvé dans le portefeuille. Veuillez importer un fichier CSV via l'onglet 'Paramètres'.")
        return

    # Sélection du ticker et période
    selected_ticker = st.selectbox("Sélectionnez un symbole boursier", options=tickers, index=0)
    nb_days = st.slider("Nombre de jours d'historique", 1, 3650, 180)

    start_date = datetime.now() - timedelta(days=nb_days)
    end_date = datetime.now()
    target_currency = st.session_state.get("devise_cible", "EUR")

    try:
        df = fetch_stock_history_converted(selected_ticker, start_date, end_date, "USD", target_currency)
        
        if df.empty or df["Close"].isnull().all():
            st.warning(f"Aucune donnée de clôture disponible pour {selected_ticker} sur la période.")
            return

        # Conversion explicite dans la devise cible
        fig = px.line(
            df.reset_index(),
            x="Date",
            y="Close",
            title=f"{selected_ticker} – Prix converti en {target_currency}",
            labels={"Close": f"Prix ({target_currency})", "Date": "Date"}
        )
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Erreur lors de la récupération des données : {str(e)}")
