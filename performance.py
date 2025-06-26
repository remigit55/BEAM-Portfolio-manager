# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import builtins
from utils import format_fr


def display_performance_history():
    """
    Affiche automatiquement la performance historique d'un ticker, puis un tableau récapitulatif des derniers cours.
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
    selected_ticker = st.selectbox("Sélectionnez un symbole boursier du portefeuille", options=tickers, index=0)
    days_range = st.slider("Nombre de jours d'historique à afficher", min_value=30, max_value=3650, value=365)

    # Dates à utiliser
    start_date = datetime.now() - timedelta(days=days_range)
    end_date = (datetime.now() - BDay(0)).to_pydatetime()  # Dernier jour ouvré

    # Graphique pour le ticker sélectionné
    try:
        data = yf.download(selected_ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)

        if not data.empty and "Close" in data.columns:
            st.line_chart(data["Close"], use_container_width=True)
        else:
            st.warning(f"Aucune donnée disponible pour {selected_ticker} sur la période sélectionnée.")
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données pour {selected_ticker} : {builtins.str(e)}")
        return

    # Construction du tableau récapitulatif des derniers cours convertis
    rows = []
    
    for ticker in tickers:
        # Devise source : extraite du dataframe si possible
        source_currency = "USD"
        if "Devise" in st.session_state.df.columns:
            source_currency_row = st.session_state.df[st.session_state.df["Ticker"] == ticker]
            if not source_currency_row.empty and pd.notna(source_currency_row["Devise"].iloc[0]):
                source_currency = source_currency_row["Devise"].iloc[0]
    
        df_ticker = fetch_stock_history_converted(ticker, start_date, end_date, source_currency, target_currency)
        if not df_ticker.empty and "Close" in df_ticker.columns:
            last_close = df_ticker["Close"].iloc[-1]
            rows.append({"Ticker": ticker, "Devise": source_currency, f"Close ({target_currency})": round(last_close, 2)})
    
    # Affichage du tableau s'il y a des données
    if rows:
        df_prices = pd.DataFrame(rows)
        st.markdown("### Derniers cours convertis")
        st.dataframe(df_prices)
    else:
        st.info("Aucune donnée de prix disponible pour les tickers sélectionnés.")
