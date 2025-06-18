import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import datetime
import requests

yf_base_url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols="

st.subheader("Portefeuille")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("Aucune donnée de portefeuille n’a encore été importée.")
else:
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

    # Ajouter colonne Nom via Yahoo Finance
    if "Tickers" in df.columns:
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}

        def get_name_cached(ticker):
            if ticker in st.session_state.ticker_names_cache:
                return st.session_state.ticker_names_cache[ticker]
            try:
                response = requests.get(f"{yf_base_url}{ticker}")
                if response.ok:
                    name = response.json()['quoteResponse']['result'][0].get('shortName', 'Non trouvé')
                else:
                    name = "Erreur requête"
            except:
                name = "Erreur nom"
            st.session_state.ticker_names_cache[ticker] = name
            return name

        noms = df["Tickers"].apply(get_name_cached)
        index_ticker = df.columns.get_loc("Tickers")
        df.insert(index_ticker + 1, "Nom", noms)

    st.dataframe(df, use_container_width=True)
    st.session_state.fx_rates = fx_rates_utilisés
