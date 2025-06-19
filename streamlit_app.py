import streamlit as st
import pandas as pd
import datetime
import requests
from PIL import Image
import base64
from io import BytesIO

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
            margin-top: -55px;
        }}
        section.main > div:nth-child(1) {{
            margin-top: -55px;
        }}
    </style>
""", unsafe_allow_html=True)

# Chargement du logo
try:
    logo = Image.open("Logo.png.png")
    buffer = BytesIO()
    logo.save(buffer, format="PNG")
    logo_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
except Exception:
    logo_base64 = ""

st.markdown(
    f"""
    <div style="display: flex; align-items: center; margin: -30px 0 10px 0;">
        <img src="data:image/png;base64,{logo_base64}" style="height: 42px; margin-right: 12px;" />
        <h1 style="font-size: 30px; margin: 0; padding: 0;">BEAM Portfolio Manager</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# Initialisation des variables de session
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
from taux_change import afficher_taux_change, actualiser_taux_change
from parametres import afficher_parametres
from od_comptables import afficher_od_comptables

# Initialisation automatique des données au démarrage
csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
if st.session_state.df is None:
    try:
        with st.spinner("Chargement initial des données du portefeuille..."):
            df = pd.read_csv(csv_url)
            st.session_state.df = df
            st.success("Données initiales importées avec succès.")
        # Charger les taux de change immédiatement après
        if "Devise" in df.columns:
            devises_uniques = sorted(set(df["Devise"].dropna().unique()))
            with st.spinner("Chargement initial des taux de change..."):
                st.session_state.fx_rates = actualiser_taux_change(st.session_state.devise_cible, devises_uniques)
                if st.session_state.fx_rates:
                    st.success(f"Taux de change initialisés pour {st.session_state.devise_cible}.")
                else:
                    st.warning("Impossible de charger les taux de change initiaux.")
    except Exception as e:
        st.error(f"Erreur lors du chargement initial : {e}")

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
    afficher_od_comptables()

# Onglet : Transactions
with onglets[3]:
    afficher_transactions()

# Onglet : Taux de change
with onglets[4]:
    afficher_taux_change()

# Onglet : Paramètres
with onglets[5]:
    afficher_parametres()
