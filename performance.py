# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import builtins
from historical_data_fetcher import fetch_stock_history, get_all_historical_data
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique d'un ticker et un tableau des derniers cours de clôture.
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

    # Devises (par défaut pour la conversion, ajustez selon vos besoins)
    source_currency = "USD"  # Devise des données boursières
    target_currency = "EUR"  # Devise cible
    currencies = [source_currency] * len(tickers)  # Suppose que tous les tickers sont en USD, ajustez si nécessaire

    # Dates à utiliser
    start_date = datetime.now() - timedelta(days=days_range)
    end_date = (datetime.now() - BDay(0)).to_pydatetime()  # Dernier jour ouvré
    st.write(f"Période : {start_date.strftime('%Y-%m-%d')} à {end_date.strftime('%Y-%m-%d')}")  # Diagnostic

    # Graphique pour le ticker sélectionné
    try:
        data = fetch_stock_history(selected_ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        if not data.empty:
            st.line_chart(data, use_container_width=True)
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
            df = fetch_stock_history(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            st.write(f"Données pour {ticker} : {df.shape}")  # Diagnostic
            if not df.empty and not df.dropna().empty:
                last_value = df.dropna().iloc[-1]
                results[ticker] = last_value
            else:
                st.warning(f"{ticker} : aucune donnée de clôture disponible.")
                results[ticker] = None
        except Exception as e:
            st.warning(f"{ticker} : erreur de récupération ({builtins.str(e)})")
            results[ticker] = None

    # Vérification du contenu de results
    st.write(f"Contenu de results : {results}")  # Diagnostic
    df_prices = pd.DataFrame.from_dict(results, orient='index', columns=["Dernier cours"])
    df_prices.index.name = "Ticker"
    df_prices = df_prices.reset_index()
    df_prices["Dernier cours"] = df_prices["Dernier cours"].apply(lambda x: format_fr(x) if pd.notnull(x) else "N/A")

    # Vérification du DataFrame final
    st.write(f"DataFrame df_prices : {df_prices}")  # Diagnostic
    st.dataframe(df_prices, use_container_width=True)

    # Test de connexion Yahoo Finance (section de débogage)
    if st.button("Lancer le test de connexion Yahoo Finance"):
        try:
            data = yf.download(
                selected_ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                progress=False
            )
            if not data.empty:
                st.success(f"✅ Données récupérées avec succès pour {selected_ticker}!")
                st.write("Aperçu des données :")
                st.dataframe(data.head())
                st.write("...")
                st.dataframe(data.tail())
                st.write(f"Nombre total d'entrées : **{len(data)}**")
            else:
                st.warning(f"❌ Aucune donnée récupérée pour {selected_ticker} sur la période spécifiée.")
        except Exception as e:
            st.error(f"❌ Une erreur est survenue lors de la récupération des données : {builtins.str(e)}")
