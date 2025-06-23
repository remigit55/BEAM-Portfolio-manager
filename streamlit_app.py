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

# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille, afficher_synthese_globale
from performance import display_performance_history
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change
from data_fetcher import fetch_fx_rates  # Updated import
from parametres import afficher_parametres_globaux
from portfolio_journal import save_portfolio_snapshot, load_portfolio_journal
from historical_data_fetcher import fetch_stock_history
from data_loader import load_data, save_data
from utils import safe_escape, format_fr

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
        /* Supprimer la sidebar */
        /*
        .st-emotion-cache-vk33gh {{
            display: none !important;
        }}
        .st-emotion-cache-1f06xpt {{
            display: none !important;
        }}
        .st-emotion-cache-18ni7ap {{
            display: none !important;
        }}
        */
        /* Ajuster le contenu principal pour qu'il prenne toute la largeur si la sidebar est masquée */
        section.main {{
            padding-right: 1rem; /* ou ajustez si nécessaire */
        }}
        /* Ajuster l'en-tête dupliqué si la sidebar est masquée */
        .st-emotion-cache-18ni7ap {{
            background-color: {ACCENT_COLOR};
            padding: 10px;
            border-radius: 0 0 10px 10px;
            margin-bottom: 25px;
            margin-top: -55px; /* Garder si nécessaire pour alignement avec le logo */
        }}
        section.main > div:nth-child(1) {{
            margin-top: -55px; /* Garder si nécessaire */
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
    "fx_rates": {},
    "devise_cible": "EUR",
    "ticker_data_cache": {},
    "momentum_results_cache": {},
    "sort_column": None,
    "sort_direction": "asc",
    "last_devise_cible_for_fx_update": "EUR",
    "last_update_time_fx": datetime.datetime.min,
    "total_valeur": None,
    "total_actuelle": None,
    "total_h52": None,
    "total_lt": None,
    "uploaded_file_id": None,
    "_last_processed_file_id": None,
    "url_data_loaded": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- Chargement initial des données depuis Google Sheets URL si df est vide ---
if st.session_state.df is None and not st.session_state.url_data_loaded:
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    try:
        with st.spinner("Chargement initial du portefeuille depuis Google Sheets..."):
            df_initial = pd.read_csv(csv_url)
            st.session_state.df = df_initial
            st.session_state.url_data_loaded = True
            st.session_state.uploaded_file_id = "initial_url_load"
            st.session_state._last_processed_file_id = "initial_url_load"
            st.success("Portefeuille chargé depuis Google Sheets.")
            st.session_state.last_update_time_fx = datetime.datetime.min
            st.rerun()
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement initial du portefeuille depuis l'URL : {e}")
        st.session_state.url_data_loaded = True

# --- LOGIQUE D'ACTUALISATION AUTOMATIQUE DES TAUX DE CHANGE ---
current_time = datetime.datetime.now()
if (st.session_state.last_update_time_fx == datetime.datetime.min) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)) or \
   (st.session_state.get("devise_cible") != st.session_state.get("last_devise_cible_for_fx_update", None)) or \
   ((current_time - st.session_state.last_update_time_fx).total_seconds() >= 60):

    devise_cible_to_use = st.session_state.get("devise_cible", "EUR")
    
    devises_uniques = []
    if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
        devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
    
    with st.spinner(f"Mise à jour automatique des taux de change pour {devise_cible_to_use}..."):
        st.session_state.fx_rates = fetch_fx_rates(devise_cible_to_use)
        st.session_state.last_update_time_fx = datetime.datetime.now()
        st.session_state.last_devise_cible_for_fx_update = devise_cible_to_use
    
    if st.session_state.get("uploaded_file_id") is not None:
        st.session_state._last_processed_file_id = st.session_state.uploaded_file_id

# --- Structure de l'application principale ---
def main():
    """
    Gère la logique principale de l'application Streamlit, y compris la navigation par onglets.
    """
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
        st.markdown("#### Taux de Change Actuels")
        st.info("Les taux sont automatiquement mis à jour à chaque chargement de fichier, changement de devise cible, ou toutes les 60 secondes.")
        if st.button("Actualiser les taux manuellement", key="manual_fx_refresh_btn_tab"):
            with st.spinner("Mise à jour manuelle des taux de change..."):
                devise_cible_for_manual_update = st.session_state.get("devise_cible", "EUR")
                devises_uniques = []
                if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                    devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
                
                st.session_state.fx_rates = fetch_fx_rates(devise_cible_for_manual_update)
                st.session_state.last_update_time_fx = datetime.datetime.now()
                st.session_state.last_devise_cible_for_fx_update = devise_cible_for_manual_update
                st.success(f"Taux de change actualisés pour {devise_cible_for_manual_update}.")
                st.rerun()

        afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

    with onglets[6]:
        afficher_parametres_globaux()    
    
    st.markdown("---")

if __name__ == "__main__":
    main()
