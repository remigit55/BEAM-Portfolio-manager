# streamlit_app.py
import streamlit as st
import pandas as pd
import datetime
import requests
from PIL import Image

# Configuration de la page
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
            margin-top: -35px;
        }}
        section.main > div:nth-child(1) {{
            margin-top: -55px;
        }}
    </style>
""", unsafe_allow_html=True)

# Titre avec logo
col1, col2 = st.columns([1, 6])
with col1:
    try:
        logo = Image.open("logo.png")
        st.image(logo, width=48)
    except Exception:
        st.markdown("⚠️ Logo non trouvé.")
with col2:
    st.markdown("<h1 style='font-size: 36px; margin-bottom: 5px;'>BEAM Portfolio Manager</h1>", unsafe_allow_html=True)

# Initialisation session_state
if "df" not in st.session_state:
    st.session_state.df = None
if "fx_rates" not in st.session_state:
    st.session_state.fx_rates = {}
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR"
if "ticker_names_cache" not in st.session_state:
    st.session_state.ticker_names_cache = {}

# Importation des modules
from portefeuille import afficher_portefeuille
from performance import afficher_performance
from transactions import afficher_transactions
from taux_change import afficher_taux_change
from parametres import afficher_parametres
from od_comptables import afficher_od_comptables

# Onglets
onglets = st.tabs([
    "Portefeuille", 
    "Performance", 
    "OD Comptables", 
    "Transactions", 
    "Taux de change", 
    "Paramètres"
])

with onglets[0]:
    afficher_portefeuille()

with onglets[1]:
    afficher_performance()

with onglets[2]:
    afficher_od_comptables()

with onglets[3]:
    afficher_transactions()

with onglets[4]:
    afficher_taux_change()

with onglets[5]:
    afficher_parametres()
