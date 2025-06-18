# transactions.py
import streamlit as st
import pandas as pd
import datetime
import requests
import time

st.header("Transactions comparables")

if "df" not in st.session_state or st.session_state.df is None:
    st.warning("Veuillez importer un fichier portefeuille dans l'onglet Paramètres.")
    st.stop()

# Vérifie que les colonnes nécessaires sont bien là
df = st.session_state.df.copy()
if not {"Tickers", "Quantité"}.issubset(df.columns):
    st.error("Le fichier importé doit contenir les colonnes 'Tickers' et 'Quantité'.")
    st.stop()

st.info("Récupération des cours historiques sur Yahoo Finance (peut prendre quelques secondes)...")

def fetch_history(ticker, interval="1d", range_days="6mo"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_days}"
    try:
        r = requests.get(url)
        if not r.ok:
            return None
        data = r.json()
        timestamps = data["chart"]["result"][0]["timestamp"]
        prices = data["chart"]["result"][0]["indicators"]["adjclose"][0]["adjclose"]
        return pd.DataFrame({"Date": pd.to_datetime(timestamps, unit="s"), ticker: prices}).set_index("Date")
    except:
        return None

# Récupère les historiques de tous les tickers
portefeuille = df[["Tickers", "Quantité"]].dropna()
ticker_list = portefeuille["Tickers"].unique()
hist_dict = {}

for t in ticker_list:
    with st.spinner(f"Téléchargement : {t}"):
        hist = fetch_history(t)
        if hist is not None:
            hist_dict[t] = hist
        time.sleep(0.5)  # Respect des limites d'API

if not hist_dict:
    st.error("Aucun historique de cours n'a pu être récupéré.")
    st.stop()

# Fusionne les historiques par date
df_merged = pd.concat(hist_dict.values(), axis=1).dropna(how="all")

# Calcule la valeur du portefeuille par jour
for t in portefeuille["Tickers"]:
    qty = portefeuille.loc[portefeuille["Tickers"] == t, "Quantité"].values[0]
    df_merged[t] = df_merged[t] * qty

df_merged["Total"] = df_merged.sum(axis=1)
st.line_chart(df_merged["Total"], use_container_width=True)
st.dataframe(df_merged.tail(), use_container_width=True)
