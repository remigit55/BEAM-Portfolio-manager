# portefeuille.py

import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import requests

def afficher_portefeuille():

    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()
    cr = CurrencyRates()
    fx_rates_utilisés = {}
    devise_cible = st.session_state.devise_cible if "devise_cible" in st.session_state else "EUR"

    def get_fx_rate(devise_origine, devise_cible):
        if devise_origine == devise_cible:
            return 1.0
        try:
            rate = cr.get_rate(devise_origine, devise_cible)
            fx_rates_utilisés[f"{devise_origine} → {devise_cible}"] = rate
            return rate
        except:
            fx_rates_utilisés[f"{devise_origine} → {devise_cible}"] = "Erreur"
            return None

    # Nettoyage et conversions
    df["Tickers"] = df["Tickers"].astype(str).str.strip()
    df["Quantité"] = pd.to_numeric(df["Quantité"], errors="coerce").fillna(0)
    df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce").fillna(0)
    df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Récupération du nom via Yahoo Finance (endpoint v8/chart → field: shortName)
    if "Tickers" in df.columns:
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}

        def get_shortname(ticker):
            if ticker in st.session_state.ticker_names_cache:
                return st.session_state.ticker_names_cache[ticker]
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
                response = requests.get(url)
                if response.ok:
                    data = response.json()
                    name = data["chart"]["result"][0]["meta"].get("shortName", ticker)
                else:
                    name = "Erreur requête"
            except:
                name = "Erreur nom"
            st.session_state.ticker_names_cache[ticker] = name
            return name

        shortnames = df["Tickers"].apply(get_shortname)
        index_ticker = df.columns.get_loc("Tickers")
        df.insert(index_ticker + 1, "Shortname", shortnames)

    # Colonnes finales affichées
    colonnes_finales = ["Tickers", "Shortname", "Devise", "Quantité", "Acquisition", "Valeur"]
    df = df[[col for col in colonnes_finales if col in df.columns]]

    st.dataframe(df, use_container_width=True)
    st.session_state.fx_rates = fx_rates_utilisés
