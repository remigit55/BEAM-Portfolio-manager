import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import requests

def afficher_portefeuille():

    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Formatage
    if "Quantité" in df.columns:
        df["Quantité"] = pd.to_numeric(df["Quantité"], errors="coerce")

    if "Acquisition" in df.columns:
        df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")

    if "Valeur" not in df.columns and "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]


    def formater_nombre_fr(x, decimales=2):
    if pd.isnull(x):
        return ""
    return f"{x:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", " ")
    
    # Mise en forme avec espaces pour les milliers
    df["Quantité_fmt"] = df["Quantité"].map(lambda x: formater_nombre_fr(x, decimales=0))
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: formater_nombre_fr(x, decimales=4))
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: formater_nombre_fr(x, decimales=2))

    # Construction du tableau final
    colonnes = []
    if "Tickers" in df.columns: colonnes.append("Tickers")
    if "Shortname" in df.columns: colonnes.append("Shortname")
    colonnes += ["Devise", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt"]

    df_affichage = df[colonnes]
    df_affichage.columns = ["Tickers", "Nom", "Devise", "Quantité", "Acquisition", "Valeur"]  # Renommage lisible

    # Affichage
    st.dataframe(df_affichage, use_container_width=True)
