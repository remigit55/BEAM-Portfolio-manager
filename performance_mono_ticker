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
    Version simplifiée pour le débogage et l'isolation.
    """
    st.subheader("Test de Performance Historique")

    # Get tickers from portfolio
    tickers = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers = sorted(st.session_state.df['Ticker'].dropna().unique())
    
    if not tickers:
        st.warning("Aucun ticker trouvé dans le portefeuille. Veuillez importer un fichier CSV via l'onglet 'Paramètres'.")
        test_ticker = st.selectbox(
            "Sélectionnez un symbole boursier",
            options=["Aucun ticker disponible"],
            index=0,
            disabled=True
        )
        return

    test_ticker = st.selectbox(
        "Sélectionnez un symbole boursier du portefeuille",
        options=tickers,
        index=0,  # Default to first ticker
        help="Choisissez un ticker pour afficher son historique."
    )
    test_days_ago = st.slider("Nombre de jours d'historique à récupérer", 1, 3650, 30)

    if st.button("Lancer le test de connexion Yahoo Finance"):
        import datetime as dt_test
        from datetime import timedelta as td_test
        
        start_date = dt_test.datetime.now() - td_test(days=test_days_ago)
        end_date = dt_test.datetime.now()

        st.info(f"Tentative de récupération des données pour **{test_ticker}** du **{start_date.strftime('%Y-%m-%d')}** au **{end_date.strftime('%Y-%m-%d')}**...")
        
        try:
            data = yf.download(
                test_ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                progress=False
            )

            if not data.empty:
                st.success(f"✅ Données récupérées avec succès pour {test_ticker}!")
                st.write("Aperçu des données :")
                st.dataframe(data.head())
                st.write("...")
                st.dataframe(data.tail())
                st.write(f"Nombre total d'entrées : **{len(data)}**")
                st.write(f"Type de l'objet retourné : `{builtins.str(type(data))}`")
                st.write(f"L'index est un `DatetimeIndex` : `{builtins.isinstance(data.index, pd.DatetimeIndex)}`")

                st.subheader("Graphique des cours de clôture")
                st.line_chart(data['Close'])

            else:
                st.warning(f"❌ Aucune donnée récupérée pour {test_ticker} sur la période spécifiée. "
                           "Vérifiez le ticker ou la période, et votre connexion à Yahoo Finance.")
        except Exception as e:
            st.error(f"❌ Une erreur est survenue lors de la récupération des données : {builtins.str(e)}")
            if "str' object is not callable" in builtins.str(e):
                st.error("⚠️ **Confirmation :** L'erreur `str() object is not callable` persiste. Cela indique fortement "
                         "qu'une variable ou fonction nommée `str` est définie ailleurs dans votre code, "
                         "écrasant la fonction native de Python. **La recherche globale `str = ` est impérative.**")
            elif "No data found" in builtins.str(e) or "empty DataFrame" in builtins.str(e):
                st.warning("Yahoo Finance n'a pas retourné de données. Le ticker est-il valide ? La période est-elle trop courte ou dans le futur ?")
            else:
                st.error(f"Détail de l'erreur : {builtins.str(e)}")
