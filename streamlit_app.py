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

# --- Fonction de conversion de devise ---
def convertir(montant, devise_source, devise_cible, fx_rates):
    """
    Convertit un montant d'une devise source vers une devise cible en utilisant les taux de change fournis.
    """
    if montant is None or pd.isna(montant):
        return 0.0

    if not isinstance(devise_source, str) or not isinstance(devise_cible, str):
        st.error(f"Invalid currency types: source={type(devise_source)}, cible={type(devise_cible)}")
        return montant

    if devise_source == devise_cible:
        return montant
    
    # Construire la clé de conversion (ex: USDCAD, EURUSD)
    taux_key = f"{devise_source}{devise_cible}"
    
    # Vérifier si le taux direct existe
    if taux_key in fx_rates:
        return montant * fx_rates[taux_key]
    
    # Vérifier si le taux inverse existe (ex: si EURUSD existe, utiliser 1/USDEUR)
    inverse_taux_key = f"{devise_cible}{devise_source}"
    if inverse_taux_key in fx_rates and fx_rates[inverse_taux_key] != 0:
        return montant / fx_rates[inverse_taux_key]
    
    # Si aucun taux direct ou inverse n'est trouvé, retourner le montant original avec un avertissement
    st.warning(f"Taux de change non trouvé pour {devise_source} vers {devise_cible}. Le montant n'a pas été converti.")
    return montant

# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille, afficher_synthese_globale
from performance import display_performance_history
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data
from utils import safe_escape, format_fr
from portfolio_journal import save_portfolio_snapshot, load_portfolio_journal, initialize_portfolio_journal_db
from historical_data_manager import save_daily_totals, load_historical_data, initialize_historical_data_db
from streamlit_autorefresh import st_autorefresh
from data_loader import load_data, save_data, load_portfolio_from_google_sheets

# Configuration de la page
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Configuration de l'actualisation automatique pour les données
st_autorefresh(interval=600 * 1000, key="data_refresh_auto")

# --- Initialisation des bases de données SQLite ---
initialize_portfolio_journal_db()
initialize_historical_data_db()

# --- Initialisation des session_state ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'fx_rates' not in st.session_state:
    st.session_state.fx_rates = {}
if 'last_update_time_fx' not in st.session_state:
    st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)
if 'devise_cible' not in st.session_state:
    st.session_state.devise_cible = "EUR"
if 'target_allocations' not in st.session_state:
    st.session_state.target_allocations = {}
if 'portfolio_journal' not in st.session_state:
    st.session_state.portfolio_journal = []
if 'df_historical_totals' not in st.session_state:
    st.session_state.df_historical_totals = pd.DataFrame()
if 'df_initial_import' not in st.session_state:
    st.session_state.df_initial_import = None
if 'last_yahoo_update_time' not in st.session_state:
    st.session_state.last_yahoo_update_time = datetime.datetime.now(datetime.timezone.utc)
if 'last_momentum_update_time' not in st.session_state:
    st.session_state.last_momentum_update_time = datetime.datetime.now(datetime.timezone.utc)
if 'target_volatility' not in st.session_state:
    st.session_state.target_volatility = 0.15
if 'google_sheets_url' not in st.session_state:
    st.session_state.google_sheets_url = ""
if 'initial_portfolio_loaded_from_journal' not in st.session_state:
    st.session_state.initial_portfolio_loaded_from_journal = False

# Tentative de chargement des données si les objets sont vides (première exécution)
if 'portfolio_journal' in st.session_state and not st.session_state.portfolio_journal:
    try:
        loaded_journal = load_portfolio_journal()
        if loaded_journal:
            st.session_state.portfolio_journal = loaded_journal
    except Exception as e:
        st.error(f"Erreur lors du chargement du journal du portefeuille: {e}. Le journal reste vide.")

if 'df_historical_totals' in st.session_state and st.session_state.df_historical_totals.empty:
    try:
        loaded_historical = load_historical_data()
        if not loaded_historical.empty:
            st.session_state.df_historical_totals = loaded_historical
    except Exception as e:
        st.error(f"Erreur lors du chargement des totaux historiques: {e}. L'historique reste vide.")

# --- Fonction pour charger ou recharger le portefeuille ---
def load_or_reload_portfolio(source_type, uploaded_file=None, google_sheets_url=None):
    """Charge ou recharge le portefeuille en fonction de la source."""
    df_loaded = None
    if source_type == "fichier" and uploaded_file:
        df_loaded, status = load_data(uploaded_file)
        if status != "success":
            st.error(f"Échec du chargement du fichier: {status}")
            return
    elif source_type == "google_sheets" and google_sheets_url:
        df_loaded = load_portfolio_from_google_sheets(google_sheets_url)
        if df_loaded is None:
            st.error("Échec du chargement depuis Google Sheets. Vérifiez l'URL et les permissions.")
            return

    if df_loaded is not None and not df_loaded.empty:
        # Vérifier la présence de la colonne 'Ticker'
        if 'Ticker' not in df_loaded.columns:
            ticker_col = next((col for col in df_loaded.columns if col.lower() in ['ticker', 'tickers', 'symbol']), None)
            if ticker_col:
                df_loaded.rename(columns={ticker_col: 'Ticker'}, inplace=True)
            else:
                st.error(f"Le fichier importé doit contenir une colonne 'Ticker' ou équivalente ('Tickers', 'Symbol'). Colonnes trouvées: {df_loaded.columns.tolist()}")
                st.session_state.df = pd.DataFrame()
                return
        # Nettoyage et conversion des données
        required_columns = ['Quantité', 'Acquisition', 'Objectif_LT', 'Catégorie', 'Devise']
        missing_columns = [col for col in required_columns if col not in df_loaded.columns]
        if missing_columns:
            st.warning(f"Colonnes manquantes dans les données importées: {missing_columns}. Initialisation avec des valeurs par défaut.")
            for col in missing_columns:
                if col in ['Quantité', 'Acquisition', 'Objectif_LT']:
                    df_loaded[col] = 0.0
                elif col == 'Catégorie':
                    df_loaded[col] = 'Non classé'
                elif col == 'Devise':
                    df_loaded[col] = st.session_state.devise_cible

        df_loaded['Quantité'] = pd.to_numeric(df_loaded['Quantité'], errors='coerce').fillna(0)
        df_loaded['Acquisition'] = pd.to_numeric(df_loaded['Acquisition'], errors='coerce').fillna(0)
        df_loaded['Objectif_LT'] = pd.to_numeric(df_loaded['Objectif_LT'], errors='coerce').fillna(0)
        df_loaded['Catégorie'] = df_loaded['Catégorie'].fillna('Non classé')
        df_loaded['Devise'] = df_loaded['Devise'].astype(str).fillna(st.session_state.devise_cible)

        st.session_state.df = df_loaded
        st.session_state.df_initial_import = df_loaded.copy()
        st.session_state.last_yahoo_update_time = datetime.datetime.now(datetime.timezone.utc)
        st.session_state.last_momentum_update_time = datetime.datetime.now(datetime.timezone.utc)

        st.write("DEBUG (SUCCESS): st.session_state.df successfully loaded with columns:", st.session_state.df.columns.tolist())
        st.write("DEBUG (SUCCESS): Is st.session_state.df empty?", st.session_state.df.empty)
        st.write("DEBUG: DataFrame dtypes:", st.session_state.df.dtypes.to_dict())
        st.success("Portefeuille chargé avec succès.")
        st.rerun()
    else:
        st.session_state.df = pd.DataFrame()
        st.error("DEBUG (ERROR): Failed to load portfolio data or DataFrame is empty. Check your data source.")

# --- Récupération des données Yahoo Finance (prix actuels) ---
def fetch_current_yahoo_data():
    if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty and 'Ticker' in st.session_state.df.columns:
        tickers = st.session_state.df['Ticker'].dropna().unique().tolist()
    else:
        tickers = []

    if 'yahoo_data' not in st.session_state:
        st.session_state.yahoo_data = {}

    if (datetime.datetime.now(datetime.timezone.utc) - st.session_state.last_yahoo_update_time).total_seconds() < 600 and 'yahoo_data' in st.session_state:
        print("DEBUG: Yahoo data from cache (less than 10 mins old).")
        return st.session_state.yahoo_data

    print("DEBUG: Fetching Yahoo data from source...")
    current_prices = fetch_yahoo_data(tickers)
    if not isinstance(current_prices, dict):
        st.error("Erreur: fetch_yahoo_data n'a pas retourné un dictionnaire.")
        return {}
    st.session_state.yahoo_data = current_prices
    st.session_state.last_yahoo_update_time = datetime.datetime.now(datetime.timezone.utc)
    return current_prices

# --- Récupération des données de Momentum ---
def fetch_current_momentum_data():
    if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty and 'Ticker' in st.session_state.df.columns:
        tickers = st.session_state.df['Ticker'].dropna().unique().tolist()
    else:
        tickers = []

    if 'momentum_data' not in st.session_state:
        st.session_state.momentum_data = {}

    if (datetime.datetime.now(datetime.timezone.utc) - st.session_state.last_momentum_update_time).total_seconds() < 3600 and 'momentum_data' in st.session_state:
        print("DEBUG: Momentum data from cache (less than 60 mins old).")
        return st.session_state.momentum_data

    print("DEBUG: Fetching momentum data from source...")
    momentum_data = fetch_momentum_data(tickers)
    if not isinstance(momentum_data, dict):
        st.error("Erreur: fetch_momentum_data n'a pas retourné un dictionnaire.")
        return {}
    st.session_state.momentum_data = momentum_data
    st.session_state.last_momentum_update_time = datetime.datetime.now(datetime.timezone.utc)
    return momentum_data

# --- Récupération des Taux de Change ---
def fetch_current_fx_rates():
    if 'last_update_time_fx' not in st.session_state or st.session_state.last_update_time_fx == datetime.datetime.min:
        st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)

    current_time = datetime.datetime.now(datetime.timezone.utc)
    time_diff = (current_time - st.session_state.last_update_time_fx).total_seconds()

    if time_diff > 600 or st.session_state.get("last_devise_cible_for_currency_update") != st.session_state.devise_cible:
        print("DEBUG: Fetching FX rates from source...")
        try:
            st.session_state.fx_rates = fetch_fx_rates(st.session_state.devise_cible)
            if not isinstance(st.session_state.fx_rates, dict):
                st.error("Erreur: fetch_fx_rates n'a pas retourné un dictionnaire.")
                st.session_state.fx_rates = {}
            st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)
            st.session_state.last_devise_cible_for_currency_update = st.session_state.devise_cible
            print(f"DEBUG: Taux de change mis à jour pour {st.session_state.devise_cible}")
        except Exception as e:
            st.error(f"Erreur lors de la récupération des taux de change: {e}")
            st.session_state.fx_rates = {}
    else:
        print("DEBUG: FX rates from cache (less than 10 mins old).")
    
    return st.session_state.fx_rates

# --- Chargement initial des données ---
google_sheets_url_from_state = st.session_state.get("google_sheets_url", "")

if st.session_state.df is None and google_sheets_url_from_state:
    with st.spinner("Chargement du portefeuille depuis Google Sheets..."):
        load_or_reload_portfolio("google_sheets", google_sheets_url=google_sheets_url_from_state)

if st.session_state.df is None:
    if 'portfolio_journal' in st.session_state and st.session_state.portfolio_journal and not st.session_state.get('initial_portfolio_loaded_from_journal', False):
        with st.spinner("Chargement du portefeuille depuis le dernier snapshot..."):
            latest_snapshot = st.session_state.portfolio_journal[-1]
            if not isinstance(latest_snapshot['portfolio_data'], pd.DataFrame):
                st.error("Erreur: Le snapshot du journal ne contient pas un DataFrame valide.")
            else:
                st.session_state.df = latest_snapshot['portfolio_data']
                st.session_state.devise_cible = latest_snapshot['target_currency']
                st.session_state.df_initial_import = st.session_state.df.copy()
                st.session_state.initial_portfolio_loaded_from_journal = True
                st.success(f"Portefeuille chargé depuis le snapshot du {latest_snapshot['date'].strftime('%Y-%m-%d')}.")
                st.rerun()

if st.session_state.df is None:
    st.info("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets.")

# --- Traitement des données et affichage ---
if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty and 'Ticker' in st.session_state.df.columns:
    current_prices = fetch_current_yahoo_data()
    momentum_data = fetch_current_momentum_data()
    fx_rates = fetch_current_fx_rates()
    df_portfolio = st.session_state.df.copy()

    st.write("DEBUG: Columns in df_portfolio before mapping:", df_portfolio.columns.tolist())
    st.write("DEBUG: DataFrame dtypes:", df_portfolio.dtypes.to_dict())

    df_portfolio['Prix Actuel'] = df_portfolio['Ticker'].map(current_prices)
    df_portfolio['Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('momentum_score', {}))
    df_portfolio['Z_Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('z_score', {}))

    df_portfolio['Acquisition (Devise Cible)'] = df_portfolio.apply(
        lambda row: convertir(row['Acquisition'], row['Devise'], st.session_state.devise_cible, fx_rates)
        if row['Devise'] != st.session_state.devise_cible else row['Acquisition'], axis=1
    )

    df_portfolio['Valeur Actuelle Unitaire'] = df_portfolio.apply(
        lambda row: convertir(row['Prix Actuel'], row['Devise'], st.session_state.devise_cible, fx_rates)
        if row['Devise'] != st.session_state.devise_cible else row['Prix Actuel'], axis=1
    )
    df_portfolio['Valeur Actuelle'] = df_portfolio['Quantité'] * df_portfolio['Valeur Actuelle Unitaire']

    df_portfolio['Gain/Perte Absolu'] = df_portfolio['Valeur Actuelle'] - df_portfolio['Acquisition (Devise Cible)']
    df_portfolio['Gain/Perte (%)'] = np.where(
        df_portfolio['Acquisition (Devise Cible)'] != 0,
        (df_portfolio['Gain/Perte Absolu'] / df_portfolio['Acquisition (Devise Cible)']) * 100,
        0
    )

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

    st.session_state.df = df_portfolio

    current_date = datetime.date.today()
    df_hist_totals = st.session_state.df_historical_totals

    last_recorded_date = df_hist_totals["Date"].max().date() if not df_hist_totals.empty else None

    if last_recorded_date != current_date:
        print("DEBUG: Sauvegarde des totaux quotidiens...")
        total_acquisition_value = df_portfolio['Acquisition (Devise Cible)'].sum()
        total_current_value = df_portfolio['Valeur Actuelle'].sum()
        total_h52_value = df_portfolio['H52'].sum() if 'H52' in df_portfolio.columns else 0
        total_lt_value = df_portfolio['Objectif_LT'].sum() if 'Objectif_LT' in df_portfolio.columns else 0

        with st.spinner("Sauvegarde des totaux quotidiens du portefeuille...\nLe snapshot sera ajouté à l'historique ou mis à jour si un snapshot existe déjà pour aujourd'hui."):
            save_daily_totals(
                current_date,
                total_acquisition_value,
                total_current_value,
                total_h52_value,
                total_lt_value,
                st.session_state.devise_cible
            )
        st.session_state.df_historical_totals = load_historical_data()
        st.info(f"Totaux quotidiens du {current_date.strftime('%Y-%m-%d')} enregistrés.")
    else:
        print(f"DEBUG: Totaux quotidiens déjà à jour pour {current_date}.")
else:
    st.warning("Aucune donnée de portefeuille valide ou colonne 'Ticker' manquante. Veuillez charger un fichier ou une URL Google Sheets valide.")

# Example calculations
if 'df' in st.session_state and isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty and 'Ticker' in st.session_state.df.columns:
    total_valeur = st.session_state.df['Valeur Totale'].sum() if 'Valeur Totale' in st.session_state.df.columns else 0.0
    total_actuelle = st.session_state.df['Valeur Actuelle'].sum() if 'Valeur Actuelle' in st.session_state.df.columns else 0.0
    total_h52 = st.session_state.df['Valeur H52'].sum() if 'Valeur H52' in st.session_state.df.columns else 0.0
    total_lt = st.session_state.df['Valeur LT'].sum() if 'Valeur LT' in st.session_state.df.columns else 0.0
else:
    total_valeur = 0.0
    total_actuelle = 0.0
    total_h52 = 0.0
    total_lt = 0.0

if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty:
    st.write("DEBUG: Columns in st.session_state.df:", st.session_state.df.columns.tolist())
    st.write("DEBUG: DataFrame dtypes:", st.session_state.df.dtypes.to_dict())
else:
    st.write("DEBUG: st.session_state.df is empty or not a DataFrame yet.")

# --- Onglets de l'application ---
onglets = st.tabs([
    "Synthèse", "Portefeuille", "Performance",
    "OD Comptables", "Transactions", "Taux de Change", "Paramètres"
])

if not st.session_state.df.empty:
    st.write("DEBUG: Columns in st.session_state.df:", st.session_state.df.columns.tolist())

with onglets[0]:
    afficher_synthese_globale(
        total_valeur,
        total_actuelle,
        total_h52,
        total_lt,
        st.session_state.df_historical_totals,
        st.session_state.devise_cible,
        st.session_state.target_allocations,
        st.session_state.target_volatility
    )

with onglets[1]:
    if st.session_state.df is None or st.session_state.df.empty or 'Ticker' not in st.session_state.df.columns:
        st.warning("Aucune donnée de portefeuille valide ou colonne 'Ticker' manquante pour afficher le portefeuille.")
    else:
        st.write("DEBUG: Calling afficher_portefeuille with df columns:", st.session_state.df.columns.tolist())
        st.write("DEBUG: devise_cible:", st.session_state.devise_cible)
        afficher_portefeuille(st.session_state.df, st.session_state.devise_cible)

    current_date = datetime.date.today()
    if st.button(f"Enregistrer le snapshot du portefeuille ({current_date.strftime('%Y-%m-%d')})", key="save_snapshot_btn"):
        if st.session_state.df is None or st.session_state.df.empty or 'Ticker' not in st.session_state.df.columns:
            st.error("Impossible d'enregistrer le snapshot: aucune donnée de portefeuille valide.")
        else:
            with st.spinner("Enregistrement du snapshot quotidien du portefeuille...\nLe snapshot sera ajouté à l'historique ou mis à jour si un snapshot existe déjà pour aujourd'hui."):
                save_portfolio_snapshot(current_date, st.session_state.df, st.session_state.devise_cible)
            st.session_state.portfolio_journal = load_portfolio_journal()
            st.info(f"Snapshot du portefeuille du {current_date.strftime('%Y-%m-%d')} enregistré pour l'historique.")

with onglets[2]:
    if st.session_state.df is None or st.session_state.df.empty or 'Ticker' not in st.session_state.df.columns:
        st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
    else:
        display_performance_history()

with onglets[3]:
    if st.session_state.df is None or st.session_state.df.empty or 'Ticker' not in st.session_state.df.columns:
        st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour générer les OD Comptables.")
    else:
        afficher_od_comptables()

with onglets[4]:
    if st.session_state.df is None or st.session_state.df.empty or 'Ticker' not in st.session_state.df.columns:
        st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour gérer les transactions.")
    else:
        afficher_transactions()

with onglets[5]:
    afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

with onglets[6]:
    from parametres import afficher_parametres_globaux
    afficher_parametres_globaux(load_or_reload_portfolio)

st.markdown("---")
st.caption(f"Dernière mise à jour de l'interface : {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
