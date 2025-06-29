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
# N'oubliez pas que cela relance TOUTE l'application Streamlit.
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
# Assurez-vous que toutes les variables sont initialisées AVANT d'être utilisées.
for key, default in {
    "df": None,
    "google_sheets_url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8Ie4F5fk5-a7kA7QVFhRV1e4zTBELo8pXuW0t2J13nCFr4z_rP0hqbAyg/pub?gid=1844300862&single=true&output=csv", # Initialisation de l'URL par défaut
    "url_data_loaded": False,
    "fx_rates": None,
    "devise_cible": "EUR",
    "ticker_data_cache": {},
    "momentum_results_cache": {},
    "sort_column": None,
    "sort_direction": "asc",
    "last_devise_cible_for_fx_update": "EUR",
    # Initialise last_update_time_fx avec une date ancienne et timezone-aware (UTC)
    "last_update_time_fx": datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc),
    "total_valeur": None,
    "total_actuelle": None,
    "total_h52": None,
    "total_lt": None,
    "uploaded_file_id": None,
    "_last_processed_file_id": None,
    "last_yfinance_update": None, # La valeur sera définie dans portfolio_display.py
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

# --- NOUVEAU BLOC DE VÉRIFICATION DE LA COHÉRENCE DE last_update_time_fx ---
# Cela garantit que last_update_time_fx est TOUJOURS un datetime timezone-aware
# avant d'être utilisé dans les comparaisons de temps.
if not isinstance(st.session_state.last_update_time_fx, datetime.datetime) or \
   st.session_state.last_update_time_fx.tzinfo is None:
    st.session_state.last_update_time_fx = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
# --- FIN NOUVEAU BLOC ---


# Chargement initial des données depuis Google Sheets
# Cette logique ne devrait s'exécuter qu'une seule fois au tout début ou après un "Clear Cache"
if st.session_state.df is None and not st.session_state.url_data_loaded:
    with st.spinner("Chargement initial du portefeuille depuis Google Sheets..."):
        # Utilisation de la fonction load_portfolio_from_google_sheets de data_loader.py
        df_initial = load_portfolio_from_google_sheets(st.session_state.google_sheets_url)
        if df_initial is not None:
            st.session_state.df = df_initial
            st.session_state.url_data_loaded = True
            st.session_state.uploaded_file_id = "initial_url_load"
            st.session_state._last_processed_file_id = "initial_url_load"
            # Laisser last_update_time_fx à sa valeur initiale (très ancienne) pour forcer une 1ère MAJ des FX
            st.rerun() # Pour rafraîchir l'application avec les données chargées
        else:
            # Si le chargement initial a échoué, marquer comme tenté pour ne pas recharger en boucle
            st.session_state.url_data_loaded = True

# --- Logique d'Actualisation des Taux de Change ---
# Cette section s'exécutera à chaque relancement du script (par st_autorefresh ou interaction utilisateur)
current_time_utc = datetime.datetime.now(datetime.timezone.utc)

# Condition pour déclencher la mise à jour des taux de change
# La logique est: mettre à jour si c'est la 1ère fois, si un nouveau fichier a été uploadé,
# ou si plus de 60 secondes se sont écoulées depuis la dernière mise à jour.
if st.session_state.last_update_time_fx is None or \
   st.session_state.last_update_time_fx == datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None) and st.session_state.get("uploaded_file_id") is not None) or \
   ((current_time_utc - st.session_state.last_update_time_fx).total_seconds() >= 60):

    devise_cible_to_use = st.session_state.get("devise_cible", "EUR")

    with st.spinner(f"Mise à jour automatique des devises pour {devise_cible_to_use}..."):
        try:
            # Appel à fetch_fx_rates qui est décoré avec @st.cache_data(ttl=60)
            st.session_state.fx_rates = fetch_fx_rates(devise_cible_to_use)
            # Met à jour l'horodatage en UTC APRÈS la récupération réussie
            st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)
            st.session_state.last_devise_cible_for_currency_update = devise_cible_to_use
            # st.success("Taux de change mis à jour automatiquement.") # Peut être trop verbeux pour une actualisation toutes les minutes
        except Exception as e:
            st.error(f"Erreur lors de la mise à jour automatique des taux de change : {e}")

    # Met à jour l'ID du dernier fichier traité pour éviter de recharger les FX inutilement
    # si le même fichier est re-sélectionné sans changement réel
    if st.session_state.get("uploaded_file_id") is not None:
        st.session_state._last_processed_file_id = st.session_state.uploaded_file_id
# --- Fin Logique d'Actualisation des Taux de Change ---


# Fonction principale de l'application
def main():
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
        # Le bouton d'actualisation manuelle est maintenant géré dans afficher_tableau_taux_change
        afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

    with onglets[6]:
        from parametres import afficher_parametres_globaux
        afficher_parametres_globaux()
    
    st.markdown("---")

if __name__ == "__main__":
    main()
