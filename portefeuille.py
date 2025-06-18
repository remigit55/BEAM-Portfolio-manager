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

    # Conversion des colonnes numériques (virgules françaises → points anglais si besoin)
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "").str.replace(",", ".")
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcul Valeur
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage à la française
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", " ")

    df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0)) if "Quantité" in df.columns else ""
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4)) if "Acquisition" in df.columns else ""
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2)) if "Valeur" in df.columns else ""

    # Colonnes à afficher (ordre souhaité)
    colonnes_affichage = []
    for col in df.columns:
        if col == "Tickers":
            colonnes_affichage.append("Tickers")
        elif col == "Quantité_fmt":
            colonnes_affichage.append("Quantité_fmt")
        elif col == "Acquisition_fmt":
            colonnes_affichage.append("Acquisition_fmt")
        elif col == "Valeur_fmt":
            colonnes_affichage.append("Valeur_fmt")
        elif col not in ["Quantité", "Acquisition", "Valeur"]:
            colonnes_affichage.append(col)

    df_affichage = df[colonnes_affichage].rename(columns={
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

    # Alignement à droite
    st.markdown("""
        <style>
            .stDataFrame td {
                text-align: right !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Sécuriser le cast string (évite erreurs PyArrow)
    for col in ["Quantité", "Acquisition", "Valeur"]:
        if col in df_affichage.columns:
            df_affichage[col] = df_affichage[col].astype(str)
    
    st.markdown("""
        <style>
            /* Aligner tout le contenu des cellules à droite */
            .st-emotion-cache-1xw8zd0 .element-container .stDataFrame td {
                text-align: right !important;
            }
            /* Aligner aussi les en-têtes si souhaité */
            .st-emotion-cache-1xw8zd0 .element-container .stDataFrame th {
                text-align: right !important;
            }
        </style>
    """, unsafe_allow_html=True)

    
    st.dataframe(df_affichage, use_container_width=True)
