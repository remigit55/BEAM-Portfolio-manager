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

    df["Valeur"] = pd.to_numeric(df["Quantité"], errors="coerce") * pd.to_numeric(df["Acquisition"], errors="coerce")
    df["Taux FX"] = df["Devise"].apply(lambda d: get_fx_rate(d, devise_cible))
    df["Taux FX Num"] = pd.to_numeric(df["Taux FX"], errors="coerce").fillna(0.0)
    df["Valeur"] = pd.to_numeric(df["Valeur"], errors="coerce").fillna(0.0)
    df["Valeur (devise cible)"] = df["Valeur"].astype(float) * df["Taux FX Num"].astype(float)

    df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")
    df["Acquisition"] = df["Acquisition"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
    df["Taux FX"] = df["Taux FX Num"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
    df["Valeur"] = df["Valeur"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
    df["Valeur (devise cible)"] = df["Valeur (devise cible)"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")

    # Ajouter colonne Nom + Dernier cours via Yahoo Finance (endpoint v8/chart)
    if "Tickers" in df.columns:
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}
        if "ticker_prices_cache" not in st.session_state:
            st.session_state.ticker_prices_cache = {}

        def get_name_and_price(ticker):
            if ticker in st.session_state.ticker_names_cache and ticker in st.session_state.ticker_prices_cache:
                return st.session_state.ticker_names_cache[ticker], st.session_state.ticker_prices_cache[ticker]
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
                response = requests.get(url)
                if response.ok:
                    data = response.json()
                    meta = data["chart"]["result"][0]["meta"]
                    name = meta.get("symbol", ticker)
                    last_price = meta.get("regularMarketPrice", None)
                else:
                    name = "Erreur requête"
                    last_price = None
            except:
                name = "Erreur nom"
                last_price = None
            st.session_state.ticker_names_cache[ticker] = name
            st.session_state.ticker_prices_cache[ticker] = last_price
            return name, last_price

        noms = []
        cours = []
        for t in df["Tickers"]:
            nom, prix = get_name_and_price(t)
            noms.append(nom)
            cours.append(prix)

        index_ticker = df.columns.get_loc("Tickers")
        df.insert(index_ticker + 1, "Nom", noms)
        df.insert(index_ticker + 2, "Dernier cours", cours)

    st.dataframe(df, use_container_width=True)
    st.session_state.fx_rates = fx_rates_utilisés
