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

    # Tableau des derniers cours de clôture pour tous les tickers
    st.subheader("Derniers cours de clôture pour tous les tickers")

    results = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
            if not df.empty and "Close" in df.columns:
                last_value = df["Close"].dropna().iloc[-1]
                results[ticker] = last_value
            else:
                st.warning(f"{ticker} : aucune donnée de clôture disponible.")
                results[ticker] = None
        except Exception as e:
            st.warning(f"{ticker} : erreur de récupération ({builtins.str(e)})")
            results[ticker] = None

    df_prices = pd.DataFrame.from_dict(results, orient='index', columns=["Dernier cours"])
    df_prices.index.name = "Ticker"
    df_prices = df_prices.reset_index()
    df_prices["Dernier cours"] = df_prices["Dernier cours"].apply(lambda x: format_fr(x) if pd.notnull(x) else "N/A")

    st.dataframe(df_prices, use_container_width=True)


for ticker in tickers:
    try:
        df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        st.write(f"Données pour {ticker} : {df.shape}")  # Affiche la taille du DataFrame
        if not df.empty and "Close" in df.columns:
            last_value = df["Close"].dropna().iloc[-1]
            results[ticker] = last_value
        else:
            st.warning(f"{ticker} : aucune donnée de clôture disponible.")
            results[ticker] = None
    except Exception as e:
        st.warning(f"{ticker} : erreur de récupération ({builtins.str(e)})")
        results[ticker] = None
