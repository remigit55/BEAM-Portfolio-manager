# performance.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
from historical_data_fetcher import fetch_stock_history, get_all_historical_data
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique d'un ticker et un tableau des derniers cours de clôture.
    """
    st.subheader("Performance Historique")

    # Diagnostic pour str
    st.write(f"Type de str au début de display_performance_history : {type(str)}")

    # Récupération des tickers disponibles dans le portefeuille
    tickers = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers = sorted(st.session_state.df['Ticker'].dropna().unique())

    if not tickers:
        st.warning("Aucun ticker trouvé dans le portefeuille. Veuillez importer un fichier CSV via l'onglet 'Paramètres'.")
        st.selectbox("Sélectionnez un symbole boursier", options=["Aucun ticker disponible"], index=0, disabled=True)
        return

    st.write(f"Tickers disponibles : {tickers}")

    # Choix du ticker et de la période
    selected_ticker = st.selectbox("Sélectionnez un symbole boursier du portefeuille", options=tickers, index=0)
    days_range = st.slider("Nombre de jours d'historique à afficher", min_value=1, max_value=365, value=90)

    # Devises
    source_currency = "USD"
    target_currency = "EUR"
    currencies = [source_currency] * len(tickers)

    # Dates à utiliser
    start_date = datetime.now() - timedelta(days=days_range)
    end_date = (datetime.now() - BDay(1)).to_pydatetime()
    st.write(f"Période : {start_date.strftime('%Y-%m-%d')} à {end_date.strftime('%Y-%m-%d')}")

    # Graphique pour le ticker sélectionné
    try:
        data = yf.download(selected_ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        st.write(f"Données brutes pour {selected_ticker} : {data.shape}, Colonnes : {data.columns.tolist() if not data.empty else 'Vide'}")
        if not data.empty and 'Close' in data.columns:
            st.line_chart(data['Close'], use_container_width=True)
        else:
            st.warning(f"Aucune donnée disponible pour {selected_ticker} sur la période sélectionnée.")
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données pour {selected_ticker} : {type(e).__name__} - {e}")
        return

    # Tableau des derniers cours de clôture pour tous les tickers
    st.subheader("Derniers cours de clôture pour tous les tickers")
    try:
        historical_prices, _ = get_all_historical_data(tickers, currencies, start_date, end_date, target_currency)
        st.write(f"historical_prices contient {len(historical_prices)} tickers: {list(historical_prices.keys())}")
    except Exception as e:
        st.error(f"Erreur dans get_all_historical_data : {type(e).__name__} - {e}")
        return

    results = {}
    for ticker in tickers:
        df = historical_prices.get(ticker, pd.Series(dtype='float64'))
        st.write(f"Données pour {ticker} : {df.shape}, Vide : {df.empty}")
        if not df.empty:
            try:
                last_value = df.iloc[-1] if not df.isna().all() else None
                st.write(f"Dernier cours pour {ticker} : {last_value} (type: {type(last_value)})")
                results[ticker] = last_value
            except Exception as e:
                st.warning(f"Erreur lors de l'extraction du dernier cours pour {ticker} : {type(e).__name__} - {e}")
                results[ticker] = None
        else:
            st.warning(f"{ticker} : aucune donnée de clôture disponible.")
            results[ticker] = None

    st.write(f"Contenu de results : {results}")
    try:
        df_prices = pd.DataFrame.from_dict(results, orient='index', columns=["Dernier cours"])
        df_prices.index.name = "Ticker"
        st.write(f"DataFrame df_prices avant reset : {df_prices.to_dict()}")
        df_prices = df_prices.reset_index()
        st.write(f"DataFrame df_prices après reset : {df_prices.to_dict()}")
        df_prices["Dernier cours"] = df_prices["Dernier cours"].apply(lambda x: format_fr(x, decimal_places=2) if pd.notnull(x) and isinstance(x, (int, float, np.number)) else "N/A")
        st.write(f"DataFrame df_prices après formatage : {df_prices.to_dict()}")
        st.dataframe(df_prices, use_container_width=True)
    except Exception as e:
        st.error(f"Erreur lors de la création/affichage du DataFrame : {type(e).__name__} - {e}")
