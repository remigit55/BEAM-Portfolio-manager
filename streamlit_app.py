# streamlit_app.py

import streamlit as st
import pandas as pd
import numpy as np
import datetime
from PIL import Image
import base64
from io import BytesIO
import os
import yfinance as yf
import pytz
import builtins

if not callable(str):
    str = builtins.str
    builtins.str = str
    
print(f"Type de str dans streamlit_app.py : {type(builtins.str)}")

# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille, afficher_synthese_globale
from performance import display_performance_history
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data # Assurez-vous que ces fonctions ont les @st.cache_data(ttl=...)
from utils import safe_escape, format_fr
from portfolio_journal import save_portfolio_snapshot, load_portfolio_journal
from streamlit_autorefresh import st_autorefresh
from data_loader import load_data, save_data, load_portfolio_from_google_sheets # Importation correcte et unique

# Configuration de la page
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Configuration de l'actualisation automatique pour les données
# Le script entier sera relancé toutes les 600 secondes (60000 millisecondes)
st_autorefresh(interval=600 * 1000, key="data_refresh_timer")

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
        section.main {{
            padding-right: 1rem;
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
except FileNotFoundError:
    st.warning("Logo.png.png non trouvé. Assurez-vous qu'il est dans le même répertoire que streamlit_app.py.")
    logo_base64 = ""
except Exception as e:
    st.warning(f"Erreur lors du chargement du logo : {e}")
    logo_base64 = ""

st.markdown(
    f"""
    <div style="display: flex; align-items: center; margin-top: -10px; margin-bottom: 20px;">
        <img src="data:image/png;base64,{logo_base64}" style="height: 55px; margin-right: 12px;" />
        <h1 style="font-size: 32px; margin: 0; line-height: 55px;">BEAM Portfolio Manager</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# Initialisation des variables de session
for key, default in {
    "df": None,
    "google_sheets_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8Ie4F5fk5-a7kA7QVFhRV1e4zTBELo8pXuW0t2J13nCFr4z_rP0hqbAyg/pub?gid=1844300862&single=true&output=csv", # Initialisation de l'URL par défaut
    "url_data_loaded": False,
    "fx_rates": None,
    "devise_cible": "EUR", # Valeur par défaut avant détection
    "ticker_data_cache": {},
    "momentum_results_cache": {},
    "sort_column": None,
    "sort_direction": "asc",
    "last_devise_cible_for_fx_update": "EUR",
    "last_update_time_fx": datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc),
    "total_valeur": None,
    "total_actuelle": None,
    "total_h52": None,
    "total_lt": None,
    "uploaded_file_id": None,
    "_last_processed_file_id": None,
    "last_yfinance_update": None, 
    "target_allocations": {
        "Minières": 0.41,
        "Asie": 0.25,
        "Energie": 0.25,
        "Matériaux": 0.01,
        "Devises": 0.08,
        "Crypto": 0.00,
        "Autre": 0.00
    }
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Vérification de la cohérence de last_update_time_fx
if not isinstance(st.session_state.last_update_time_fx, datetime.datetime) or \
   st.session_state.last_update_time_fx.tzinfo is None:
    st.session_state.last_update_time_fx = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)


# Chargement initial des données depuis Google Sheets
if st.session_state.df is None and not st.session_state.url_data_loaded:
    with st.spinner("Chargement initial du portefeuille depuis Google Sheets..."):
        dtype_spec_for_loader = {
            "Quantité": str,
            "Acquisition": str,
            "Objectif_LT": str,
            "H": str 
        }
        df_initial = load_portfolio_from_google_sheets(st.session_state.google_sheets_url, dtype_spec=dtype_spec_for_loader)
        if df_initial is not None:
            st.session_state.df = df_initial
            st.session_state.url_data_loaded = True
            st.session_state.uploaded_file_id = "initial_url_load"
            st.session_state._last_processed_file_id = "initial_url_load"

            # Détecter la devise cible à partir du DataFrame chargé
            if "Devise" in st.session_state.df.columns and not st.session_state.df["Devise"].empty:
                # Prend la devise la plus fréquente comme devise cible
                st.session_state.devise_cible = st.session_state.df["Devise"].dropna().str.strip().str.upper().mode()[0]
            else:
                st.session_state.devise_cible = "EUR" # Fallback si colonne devise manquante

            st.rerun() 
        else:
            st.session_state.url_data_loaded = True

# Logique d'Actualisation des Taux de Change
current_time_utc = datetime.datetime.now(datetime.timezone.utc)

if st.session_state.last_update_time_fx is None or \
   st.session_state.last_update_time_fx == datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None) and st.session_state.get("uploaded_file_id") is not None) or \
   ((current_time_utc - st.session_state.last_update_time_fx).total_seconds() >= 60):

    devise_cible_to_use = st.session_state.get("devise_cible", "EUR")

    with st.spinner(f"Mise à jour automatique des devises pour {devise_cible_to_use}..."):
        try:
            st.session_state.fx_rates = fetch_fx_rates(devise_cible_to_use)
            st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)
            st.session_state.last_devise_cible_for_currency_update = devise_cible_to_use
        except Exception as e:
            st.error(f"Erreur lors de la mise à jour automatique des taux de change : {e}")

    if st.session_state.get("uploaded_file_id") is not None:
        st.session_state._last_processed_file_id = st.session_state.uploaded_file_id

# Fonction principale de l'application
def main():
    st.sidebar.title("Paramètres")

    # Affichage de la devise cible détectée (plus de sélection manuelle)
    st.sidebar.subheader("Devise de Conversion")
    st.sidebar.info(f"Devise de référence du portefeuille : **{st.session_state.get('devise_cible', 'EUR')}**")

    # Gestion du fichier
    st.sidebar.subheader("Importer Portefeuille")
    uploaded_file = st.sidebar.file_uploader("Importer un fichier Excel ou CSV", type=["xlsx", "xls", "csv"])

    if uploaded_file is not None:
        try:
            dtype_spec = {
                "Quantité": str,
                "Acquisition": str,
                "Objectif_LT": str,
                "H": str 
            }

            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, sep=';', decimal=',', dtype=dtype_spec)
            else:
                df = pd.read_excel(uploaded_file, dtype=dtype_spec)
            
            st.session_state.df = df
            st.success("Fichier importé avec succès !")
            st.session_state.ticker_data_cache = {}
            st.session_state.momentum_results_cache = {}
            st.session_state.fx_rates = None 
            st.session_state.uploaded_file_id = uploaded_file.id 
            st.session_state._last_processed_file_id = uploaded_file.id

            # Détecter la devise cible à partir du DataFrame chargé
            if "Devise" in st.session_state.df.columns and not st.session_state.df["Devise"].empty:
                st.session_state.devise_cible = st.session_state.df["Devise"].dropna().str.strip().str.upper().mode()[0]
            else:
                st.session_state.devise_cible = "EUR" # Fallback

            st.rerun() 
            
        except Exception as e:
            st.error(f"Erreur lors de l'importation du fichier : {e}")
            st.session_state.df = None 
    
    # Bouton de rafraîchissement des données
    if st.sidebar.button("Rafraîchir les données externes"):
        st.session_state.ticker_data_cache = {}
        st.session_state.momentum_results_cache = {}
        st.session_state.fx_rates = None 
        st.experimental_rerun() 

    st.sidebar.info(f"Dernière mise à jour Yahoo Finance: {st.session_state.get('last_yfinance_update', 'Jamais')}")

    # Onglets principaux
    onglets = st.tabs([
        "Synthèse",
        "Portefeuille",
        "Performance",
        "OD Comptables",
        "Transactions",
        "Taux de change",
        "Paramètres"
    ])

    with onglets[0]:
        afficher_synthese_globale(
            st.session_state.total_valeur,
            st.session_state.total_actuelle,
            st.session_state.total_h52,
            st.session_state.total_lt
        )

    with onglets[1]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets.")
        else:
            total_valeur, total_actuelle, total_h52, total_lt = afficher_portefeuille()
            st.session_state.total_valeur = total_valeur
            st.session_state.total_actuelle = total_actuelle
            st.session_state.total_h52 = total_h52
            st.session_state.total_lt = total_lt

            current_date = datetime.date.today()
            devise_cible = st.session_state.get("devise_cible", "EUR")

            journal_entries = load_portfolio_journal()
            journal_dates = [entry['date'] for entry in journal_entries]

            if st.session_state.df is not None and not st.session_state.df.empty and current_date not in journal_dates:
                with st.spinner("Enregistrement du snapshot quotidien du portefeuille..."):
                    save_portfolio_snapshot(current_date, st.session_state.df, devise_cible)
                st.info(f"Snapshot du portefeuille du {current_date.strftime('%Y-%m-%d')} enregistré pour l'historique.")

    with onglets[2]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        else:
            display_performance_history()

    with onglets[3]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour générer les OD Comptables.")
        else:
            afficher_od_comptables()

    with onglets[4]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour gérer les transactions.")
        else:
            afficher_transactions()

    with onglets[5]:
        afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

    with onglets[6]:
        from parametres import afficher_parametres_globaux
        afficher_parametres_globaux()
    
    st.markdown("---")

if __name__ == "__main__":
    main()
