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
from portfolio_journal import save_portfolio_snapshot, load_portfolio_journal, initialize_portfolio_journal_db # Ajout de initialize_portfolio_journal_db
from historical_data_manager import save_daily_totals, load_historical_data, initialize_historical_data_db # Ajout de save_daily_totals, load_historical_data, initialize_historical_data_db
from streamlit_autorefresh import st_autorefresh
from data_loader import load_data, save_data, load_portfolio_from_google_sheets # Importation correcte et unique
import time # Importer le module time

# Configuration de la page
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Configuration de l'actualisation automatique pour les données
# Le script entier sera relancé toutes les 600 secondes (60000 millisecondes)
# N'oubliez pas que cela relance TOUTE l'application Streamlit.
st_autorefresh(interval=600 * 1000, key="data_refresh_auto")

# --- Initialisation des bases de données SQLite ---
# Cette fonction est appelée une seule fois au début pour créer les tables si elles n'existent pas.
initialize_portfolio_journal_db()
initialize_historical_data_db()


# Initialisation des variables d'état de session si elles n'existent pas
# Assurez-vous que toutes les clés nécessaires existent avant utilisation
if "df" not in st.session_state:
    st.session_state.df = None
if "df_transactions" not in st.session_state:
    st.session_state.df_transactions = pd.DataFrame(columns=['Date', 'Type', 'Ticker', 'Quantité', 'Prix', 'Devise', 'Frais', 'Notes'])
if "fx_rates" not in st.session_state:
    st.session_state.fx_rates = {}
if "last_update_time_fx" not in st.session_state:
    st.session_state.last_update_time_fx = datetime.datetime.min
if "last_yfinance_update" not in st.session_state:
    st.session_state.last_yfinance_update = datetime.datetime.min
if "data_source_type" not in st.session_state:
    st.session_state.data_source_type = "file" # Valeur par défaut
if "google_sheets_url" not in st.session_state:
    st.session_state.google_sheets_url = ""
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR" # Initialisation avec une valeur par défaut
if "target_allocations" not in st.session_state:
    st.session_state.target_allocations = {} # Initialise les allocations cibles (si non déjà faites)
if "target_volatility" not in st.session_state:
    st.session_state.target_volatility = 0.15 # 15% par défaut (en décimal)

# --- Fonction pour charger ou recharger le portefeuille ---
def load_or_reload_portfolio(source_type, uploaded_file=None, google_sheets_url=None):
    """Charge ou recharge le portefeuille en fonction de la source."""
    df_loaded = None
    if source_type == "fichier" and uploaded_file:
        df_loaded, _ = load_data(uploaded_file)
    elif source_type == "google_sheets" and google_sheets_url:
        df_loaded = load_portfolio_from_google_sheets(google_sheets_url)

    if df_loaded is not None:
        # Nettoyage et conversion des données après chargement
        if 'Ticker' not in df_loaded.columns:
            st.error("Le fichier importé doit contenir une colonne 'Ticker'.")
            return
        df_loaded['Quantité'] = pd.to_numeric(df_loaded['Quantité'], errors='coerce').fillna(0)
        df_loaded['Acquisition'] = pd.to_numeric(df_loaded['Acquisition'], errors='coerce').fillna(0)
        df_loaded['Objectif_LT'] = pd.to_numeric(df_loaded['Objectif_LT'], errors='coerce').fillna(0)
        df_loaded['Catégorie'] = df_loaded['Catégorie'].fillna('Non classé')
        df_loaded['Devise'] = df_loaded['Devise'].fillna(st.session_state.devise_cible) # Devise par défaut

        st.session_state.df = df_loaded
        st.session_state.df_initial_import = df_loaded.copy() # Garder une copie de l'original

        # Forcer une mise à jour des prix et momentum après un chargement/changement de fichier
        st.session_state.last_yahoo_update_time = datetime.datetime.min 
        st.session_state.last_momentum_update_time = datetime.datetime.min

        st.success("Portefeuille chargé avec succès.")
        st.rerun() # Pour rafraîchir l'interface avec le nouveau DF
    else:
        st.warning("Impossible de charger le portefeuille. Veuillez vérifier la source.")
        st.session_state.df = None


# --- Récupération des données Yahoo Finance (prix actuels) ---
def fetch_current_yahoo_data():
    tickers = st.session_state.df['Ticker'].dropna().unique().tolist() if st.session_state.df is not None else []

    # Vérifier si la dernière mise à jour est trop récente (moins de 10 minutes)
    if (datetime.datetime.now() - st.session_state.last_yahoo_update_time).total_seconds() < 600 and st.session_state.yahoo_data:
        print("DEBUG: Yahoo data from cache (less than 10 mins old).")
        return st.session_state.yahoo_data

    print("DEBUG: Fetching Yahoo data from source...")
    current_prices = fetch_yahoo_data(tickers)
    st.session_state.yahoo_data = current_prices
    st.session_state.last_yahoo_update_time = datetime.datetime.now()
    return current_prices

# --- Récupération des données de Momentum ---
def fetch_current_momentum_data():
    tickers = st.session_state.df['Ticker'].dropna().unique().tolist() if st.session_state.df is not None else []

    # Vérifier si la dernière mise à jour est trop récente (moins de 60 minutes)
    if (datetime.datetime.now() - st.session_state.last_momentum_update_time).total_seconds() < 3600 and st.session_state.momentum_data:
        print("DEBUG: Momentum data from cache (less than 60 mins old).")
        return st.session_state.momentum_data

    print("DEBUG: Fetching momentum data from source...")
    momentum_data = fetch_momentum_data(tickers)
    st.session_state.momentum_data = momentum_data
    st.session_state.last_momentum_update_time = datetime.datetime.now()
    return momentum_data


# --- Récupération des Taux de Change ---
def fetch_current_fx_rates():
    if (datetime.datetime.now() - st.session_state.last_update_time_fx).total_seconds() > 600 or \
    st.session_state.get("last_devise_cible_for_currency_update") != st.session_state.devise_cible:
        print("DEBUG: Fetching FX rates from source...")
        try:
            st.session_state.fx_rates = fetch_fx_rates(st.session_state.devise_cible)
            st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)
            st.session_state.last_devise_cible_for_currency_update = st.session_state.devise_cible
            print(f"DEBUG: Taux de change mis à jour pour {st.session_state.devise_cible}")
        except Exception as e:
            st.error(f"Erreur lors de la récupération des taux de change: {e}")
            st.session_state.fx_rates = {} # Assurez-vous que fx_rates est un dict vide en cas d'erreur
    else:
        print("DEBUG: FX rates from cache (less than 10 mins old).")
    return st.session_state.fx_rates


# --- Chargement initial des données ---
# Récupérer l'URL de Google Sheets depuis session_state si elle existe
google_sheets_url_from_state = st.session_state.get("google_sheets_url", "")

# Tenter de charger depuis Google Sheets en premier si l'URL est configurée
if st.session_state.df is None and google_sheets_url_from_state:
    with st.spinner("Chargement du portefeuille depuis Google Sheets..."):
        load_or_reload_portfolio("google_sheets", google_sheets_url=google_sheets_url_from_state)
        # Pas besoin de rerun ici, load_or_reload_portfolio le fait déjà

# Si st.session_state.df n'est toujours pas défini après les tentatives de chargement
if st.session_state.df is None:
    # Tenter de charger le dernier snapshot du journal si existant et pas déjà chargé
    if st.session_state.portfolio_journal and not st.session_state.get('initial_portfolio_loaded_from_journal', False):
        with st.spinner("Chargement du portefeuille depuis le dernier snapshot..."):
            latest_snapshot = st.session_state.portfolio_journal[-1] # Le dernier snapshot est le plus récent
            st.session_state.df = latest_snapshot['portfolio_data']
            st.session_state.devise_cible = latest_snapshot['target_currency']
            st.session_state.df_initial_import = st.session_state.df.copy()
            st.session_state.initial_portfolio_loaded_from_journal = True # Marquer comme chargé pour éviter rechargement constant
            st.success(f"Portefeuille chargé depuis le snapshot du {latest_snapshot['date'].strftime('%Y-%m-%d')}.")
            st.rerun() # Pour rafraîchir l'interface

# Si après tout ça, df est toujours None, afficher un message d'information
if st.session_state.df is None:
    st.info("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets.")


# --- Traitement des données et affichage ---
if st.session_state.df is not None:
    # Récupérer les données actualisées
    current_prices = fetch_current_yahoo_data()
    momentum_data = fetch_current_momentum_data()
    fx_rates = fetch_current_fx_rates()
    devise_cible = st.session_state.devise_cible
    df_portfolio = st.session_state.df.copy()

    # Fusionner les prix actuels et le momentum avec le DataFrame du portefeuille
    df_portfolio['Prix Actuel'] = df_portfolio['Ticker'].map(current_prices)
    df_portfolio['Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('momentum_score', {}))
    df_portfolio['Z_Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('z_score', {}))

    # Appliquer les taux de change pour les valeurs d'acquisition et actuelles
    # Convertir 'Acquisition' à la devise cible si Devise est différente
    df_portfolio['Acquisition (Devise Cible)'] = df_portfolio.apply(
        lambda row: convertir(row['Acquisition'], row['Devise'], devise_cible, fx_rates)
        if row['Devise'] != devise_cible else row['Acquisition'], axis=1
    )

    # Calcul de la valeur actuelle unitaire et totale dans la devise cible
    df_portfolio['Valeur Actuelle Unitaire'] = df_portfolio.apply(
        lambda row: convertir(row['Prix Actuel'], row['Devise'], devise_cible, fx_rates)
        if row['Devise'] != devise_cible else row['Prix Actuel'], axis=1
    )
    df_portfolio['Valeur Actuelle'] = df_portfolio['Quantité'] * df_portfolio['Valeur Actuelle Unitaire']

    # Calculs de performance
    df_portfolio['Gain/Perte Absolu'] = df_portfolio['Valeur Actuelle'] - df_portfolio['Acquisition (Devise Cible)']
    df_portfolio['Gain/Perte (%)'] = np.where(
        df_portfolio['Acquisition (Devise Cible)'] != 0,
        (df_portfolio['Gain/Perte Absolu'] / df_portfolio['Acquisition (Devise Cible)']) * 100,
        0
    )

    # Calcul de la H52 et LT
    df_portfolio['H52 (%)'] = np.where(
        df_portfolio['Prix Actuel'] != 0,
        ((df_portfolio['Prix Actuel'] - df_portfolio['H52']) / df_portfolio['Prix Actuel']) * 100,
        0
    )
    df_portfolio['LT (%)'] = np.where(
        df_portfolio['Prix Actuel'] != 0,
        ((df_portfolio['Prix Actuel'] - df_portfolio['Objectif_LT']) / df_portfolio['Prix Actuel']) * 100,
        0
    )

    # Mettre à jour le DataFrame de session
    st.session_state.df = df_portfolio

    # --- Calcul et sauvegarde des totaux quotidiens (une fois par jour) ---
    current_date = datetime.date.today()
    # Charger l'historique pour vérifier la dernière date
    df_hist_totals = st.session_state.df_historical_totals # C'est déjà un DataFrame

    last_recorded_date = df_hist_totals["Date"].max().date() if not df_hist_totals.empty else None

    # Vérifier si la sauvegarde pour aujourd'hui est nécessaire
    if last_recorded_date != current_date:
        print("DEBUG: Sauvegarde des totaux quotidiens...")
        total_acquisition_value = df_portfolio['Acquisition (Devise Cible)'].sum()
        total_current_value = df_portfolio['Valeur Actuelle'].sum()
        total_h52_value = df_portfolio['H52'].sum() if 'H52' in df_portfolio.columns else 0 # Assuming H52 will be calculated elsewhere
        total_lt_value = df_portfolio['Objectif_LT'].sum() if 'Objectif_LT' in df_portfolio.columns else 0 # Assuming LT will be calculated elsewhere

        with st.spinner("Sauvegarde des totaux quotidiens du portefeuille..."):
            save_daily_totals(
                current_date, 
                total_acquisition_value, 
                total_current_value, 
                total_h52_value, 
                total_lt_value, 
                devise_cible
            )
        st.session_state.df_historical_totals = load_historical_data() # Recharger l'historique après sauvegarde
        st.info(f"Totaux quotidiens du {current_date.strftime('%Y-%m-%d')} enregistrés.")
    else:
        print(f"DEBUG: Totaux quotidiens déjà à jour pour {current_date}.")


# --- Onglets de l'application ---
onglets = st.tabs([
    "📊 Synthèse Globale", "📈 Portefeuille Détaillé", "🚀 Performance Historique",
    "🧾 OD Comptables", "🔄 Transactions", "💱 Taux de Change", "⚙️ Paramètres"
])

with onglets[0]:
    afficher_synthese_globale(
        st.session_state.df,
        st.session_state.df_historical_totals,
        devise_cible,
        st.session_state.target_allocations,
        st.session_state.target_volatility
    )

with onglets[1]:
    afficher_portefeuille(st.session_state.df, devise_cible)

    # Bouton pour enregistrer un snapshot manuel du portefeuille
    current_date = datetime.date.today()
    if st.button(f"Enregistrer le snapshot du portefeuille ({current_date.strftime('%Y-%m-%d')})", key="save_snapshot_btn"):
        with st.spinner("Enregistrement du snapshot quotidien du portefeuille...\nLe snapshot sera ajouté à l'historique ou mis à jour si un snapshot existe déjà pour aujourd'hui."):
            save_portfolio_snapshot(current_date, st.session_state.df, devise_cible)
        st.session_state.portfolio_journal = load_portfolio_journal() # Recharger le journal après sauvegarde
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
    afficher_parametres_globaux(load_or_reload_portfolio) # Passe la fonction de chargement/rechargement

st.markdown("---")
st.caption(f"Dernière mise à jour de l'interface : {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
