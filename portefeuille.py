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

    # Conversion des colonnes numériques (brutes) en float
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "").str.replace(",", ".")
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Calcul de la valeur
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage à la française
    def format_fr(x, dec=2):
        try:
            return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", " ")
        except:
            return ""

    if "Quantité" in df.columns:
        df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    if "Acquisition" in df.columns:
        df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    if "Valeur" in df.columns:
        df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Colonnes d'affichage finales
    colonnes_affichage = []
    for col in df.columns:
        if col == "Quantité":
            continue
        elif col == "Acquisition":
            colonnes_affichage.append("Acquisition_fmt")
        elif col == "Valeur":
            colonnes_affichage.append("Valeur_fmt")
        elif col in ["Quantité_fmt", "Acquisition_fmt", "Valeur_fmt"]:
            colonnes_affichage.append(col)
        else:
            colonnes_affichage.append(col)

    # Renommer les colonnes affichées
    df_affichage = df[colonnes_affichage].rename(columns={
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

    # Alignement à droite via CSS
    st.markdown("""
        <style>
            .stDataFrame td {
                text-align: right !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Cast des colonnes formatées en str (pour éviter erreurs PyArrow/Streamlit)
    for col in ["Quantité", "Acquisition", "Valeur"]:
        if col in df_affichage.columns:
            df_affichage[col] = df_affichage[col].astype(str)

    st.dataframe(df_affichage, use_container_width=True)
