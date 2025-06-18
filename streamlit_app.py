# streamlit_app.py
import streamlit as st
import pandas as pd
import datetime
import requests
from forex_python.converter import CurrencyRates

# Configuration de la page (à mettre en tout début)
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Thème personnalisé
PRIMARY_COLOR = "#363636"
SECONDARY_COLOR = "#E8E8E8"
ACCENT_COLOR = "#A49B6D"

st.markdown(f"""
    <style>
        body {{
            background-color: {SECONDARY_COLOR};
            color: {PRIMARY_COLOR};
        }}
        .stApp {{
            font-family: 'Arial', sans-serif;
        }}
        .stDataFrame td, .stDataFrame th {{
            text-align: right !important;
        }}
        .st-emotion-cache-18ni7ap {{
            background-color: {ACCENT_COLOR};
            padding: 10px;
            border-radius: 0 0 10px 10px;
            margin-bottom: 25px;
        }}
        .st-emotion-cache-1v0mbdj, .st-emotion-cache-1avcm0n {{
            display: none;
        }}
    </style>
""", unsafe_allow_html=True)

# Titre principal
st.title("BEAM Portfolio Manager")

# Initialisation des variables session
if "df" not in st.session_state:
    st.session_state.df = None
if "fx_rates" not in st.session_state:
    st.session_state.fx_rates = {}
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR"
if "ticker_names_cache" not in st.session_state:
    st.session_state.ticker_names_cache = {}

# Importation des modules fonctionnels
from portefeuille import afficher_portefeuille
from performance import afficher_performance
from transactions import afficher_transactions
from taux_change import afficher_taux_change
from parametres import afficher_parametres

# Onglets horizontaux
onglets = st.tabs([
    "Portefeuille", 
    "Performance", 
    "OD Comptables", 
    "Transactions", 
    "Taux de change", 
    "Paramètres"
])

# Onglet : Portefeuille
with onglets[0]:
    afficher_portefeuille()

# Onglet : Performance
with onglets[1]:
    afficher_performance()

# Onglet : OD Comptables
with onglets[2]:
    st.subheader("📋 OD Comptables")
    if "od" in st.session_state:
        st.dataframe(st.session_state.od, use_container_width=True)
    else:
        st.info("Aucune OD comptable enregistrée.")

# Onglet : Transactions
with onglets[3]:
    afficher_transactions()

# Onglet : Taux de change
with onglets[4]:
    afficher_taux_change()

# Onglet : Paramètres
with onglets[5]:
    afficher_parametres()
