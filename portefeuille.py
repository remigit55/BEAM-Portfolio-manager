import streamlit as st
import pandas as pd

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Nettoyage des colonnes numériques
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
                .astype(float)
            )

    # Calcul de la colonne Valeur
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage style français : 1 234,56
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")

    df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    if "Tickers" in df.columns:
        df["Ticker"] = df["Tickers"]

    colonnes = ["Ticker", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt"]
    if "Devise" in df.columns:
        colonnes.append("Devise")

    df_affichage = df[colonnes].rename(columns={
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

   
