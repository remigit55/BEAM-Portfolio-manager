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
import time # Importer le module time

# Ensure str is callable, though this is usually not necessary
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

    if devise_source == devise_cible:
        return montant
    
    # Construire la clé de conversion (ex: USDCAD, EURUSD)
    taux_key = f"{devise_source}{devise_cible}"
    
    # Vérifier si le taux direct existe
    if taux_key in fx_rates:
        return montant * fx_rates[taux_key]
    
    # Vérifier si le taux inverse existe (ex: si EURUSD existe, utiliser 1/USD EUR)
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
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data # Assurez-vous que ces fonctions ont les @st.cache_data(ttl=...)
from utils import safe_escape, format_fr
from portfolio_journal import save_portfolio_snapshot, load_portfolio_journal, initialize_portfolio_journal_db # Ajout de initialize_portfolio_journal_db
from historical_data_manager import save_daily_totals, load_historical_data, initialize_historical_data_db # Ajout de save_daily_totals, load_historical_data, initialize_historical_data_db
from streamlit_autorefresh import st_autorefresh
from data_loader import load_data, save_data, load_portfolio_from_google_sheets # Importation correcte et unique

# Configuration de la page
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Configuration de l'actualisation automatique pour les données
# Le script entier sera relancé toutes les 600 secondes (60000 millisecondes)
st_autorefresh(interval=600 * 1000, key="data_refresh_auto")

# --- Initialisation des bases de données SQLite ---
initialize_portfolio_journal_db()
initialize_historical_data_db()

# --- Initialisation des session_state ---
# Assurez-vous que les clés existent toujours AVANT de tenter de charger des données.
if 'df' not in st.session_state:
    st.session_state.df = None
if 'fx_rates' not in st.session_state:
    st.session_state.fx_rates = {}
if 'last_update_time_fx' not in st.session_state:
    st.session_state.last_update_time_fx = datetime.datetime.min # Pour forcer la 1ère maj
if 'devise_cible' not in st.session_state:
    st.session_state.devise_cible = "EUR"
if 'target_allocations' not in st.session_state:
    st.session_state.target_allocations = {}

# Initialisation des objets vides pour garantir la présence des clés
if 'portfolio_journal' not in st.session_state:
    st.session_state.portfolio_journal = [] # Initialise à une liste vide
if 'df_historical_totals' not in st.session_state:
    st.session_state.df_historical_totals = pd.DataFrame() # Initialise à un DataFrame vide

# Tentative de chargement des données si les objets sont vides (première exécution)
if not st.session_state.portfolio_journal: # Vérifie si c'est vide
    try:
        loaded_journal = load_portfolio_journal()
        if loaded_journal: # Met à jour uniquement si le chargement a réussi et a retourné des données
            st.session_state.portfolio_journal = loaded_journal
    except Exception as e:
        st.error(f"Erreur lors du chargement du journal du portefeuille: {e}. Le journal reste vide.")

if st.session_state.df_historical_totals.empty: # Vérifie si c'est vide
    try:
        loaded_historical = load_historical_data()
        if not loaded_historical.empty: # Met à jour uniquement si le chargement a réussi et a retourné des données
            st.session_state.df_historical_totals = loaded_historical
    except Exception as e:
        st.error(f"Erreur lors du chargement des totaux historiques: {e}. L'historique reste vide.")

if 'df_initial_import' not in st.session_state: # Pour garder une trace du DF initialement importé
    st.session_state.df_initial_import = None
if 'last_yahoo_update_time' not in st.session_state:
    st.session_state.last_yahoo_update_time = datetime.datetime.min
if 'last_momentum_update_time' not in st.session_state:
    st.session_state.last_momentum_update_time = datetime.datetime.min
if 'target_volatility' not in st.session_state:
    st.session_state.target_volatility = 0.15 # 15% par défaut (en décimal)
if 'google_sheets_url' not in st.session_state:
    st.session_state.google_sheets_url = "" # Initialise l'URL Google Sheets

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
    if (datetime.datetime.now() - st.session_state.last_yahoo_update_time).total_seconds() < 600 and 'yahoo_data' in st.session_state:
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
    if (datetime.datetime.now() - st.session_state.last_momentum_update_time).total_seconds() < 3600 and 'momentum_data' in st.session_state:
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
    df_portfolio = st.session_state.df.copy()

    # Fusionner les prix actuels et le momentum avec le DataFrame du portefeuille
    df_portfolio['Prix Actuel'] = df_portfolio['Ticker'].map(current_prices)
    df_portfolio['Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('momentum_score', {}))
    df_portfolio['Z_Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('z_score', {}))

    # Appliquer les taux de change pour les valeurs d'acquisition et actuelles
    # Convertir 'Acquisition' à la devise cible si Devise est différente
    df_portfolio['Acquisition (Devise Cible)'] = df_portfolio.apply(
        lambda row: convertir(row['Acquisition'], row['Devise'], st.session_state.devise_cible, fx_rates)
        if row['Devise'] != st.session_state.devise_cible else row['Acquisition'], axis=1
    )

    # Calcul de la valeur actuelle unitaire et totale dans la devise cible
    df_portfolio['Valeur Actuelle Unitaire'] = df_portfolio.apply(
        lambda row: convertir(row['Prix Actuel'], row['Devise'], st.session_state.devise_cible, fx_rates)
        if row['Devise'] != st.session_state.devise_cible else row['Prix Actuel'], axis=1
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
    # Assurez-vous que 'H52' et 'Objectif_LT' sont des colonnes valides dans df_portfolio avant d'y accéder.
    # Si H52 ou Objectif_LT sont des prix absolus dans la devise d'origine, ils doivent être convertis.
    # Pour l'instant, je vais supposer qu'ils sont déjà dans la devise cible ou que leur conversion est gérée ailleurs.
    # Si 'H52' et 'Objectif_LT' sont déjà des pourcentages ou des valeurs relatives par rapport au prix actuel,
    # cette logique de conversion n'est pas nécessaire ici.
    df_portfolio['H52 (%)'] = np.where(
        (df_portfolio['Prix Actuel'].notna()) & (df_portfolio['Prix Actuel'] != 0) & (df_portfolio['H52'].notna()),
        ((df_portfolio['Prix Actuel'] - df_portfolio['H52']) / df_portfolio['Prix Actuel']) * 100,
        0
    )
    df_portfolio['LT (%)'] = np.where(
        (df_portfolio['Prix Actuel'].notna()) & (df_portfolio['Prix Actuel'] != 0) & (df_portfolio['Objectif_LT'].notna()),
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
        
        # S'assurer que H52 et Objectif_LT sont traités correctement pour les totaux.
        # Si ce sont des valeurs monétaires, summez-les après conversion.
        # Si ce sont des prix, vous devrez peut-être calculer une valeur équivalente du portefeuille
        # à ces niveaux de prix. Pour l'exemple, je vais sommer les colonnes si elles existent.
        total_h52_value = df_portfolio['H52'].sum() if 'H52' in df_portfolio.columns else 0 
        total_lt_value = df_portfolio['Objectif_LT'].sum() if 'Objectif_LT' in df_portfolio.columns else 0

        with st.spinner("Sauvegarde des totaux quotidiens du portefeuille...\nLe snapshot sera ajouté à l'historique ou mis à jour si un snapshot existe déjà pour aujourd'hui."):
            save_daily_totals(
                current_date,
                total_acquisition_value,
                total_current_value,
                total_h52_value, # Ceci doit être la somme des valeurs H52 converties si elles sont monétaires.
                total_lt_value, # Ceci doit être la somme des valeurs Objectif_LT converties si elles sont monétaires.
                st.session_state.devise_cible
            )
        st.session_state.df_historical_totals = load_historical_data() # Recharger l'historique après sauvegarde
        st.info(f"Totaux quotidiens du {current_date.strftime('%Y-%m-%d')} enregistrés.")
    else:
        print(f"DEBUG: Totaux quotidiens déjà à jour pour {current_date}.")

# --- Onglets de l'application ---
onglets = st.tabs([
    "Synthèse", "Portefeuille", "Performance",
    "OD Comptables", "Transactions", "Taux de Change", "Paramètres"
])

with onglets[0]:
    # Calcul des totaux nécessaires pour afficher_synthese_globale
    # Ces sommes doivent être effectuées sur le df_portfolio qui est dans st.session_state.df
    if st.session_state.df is not None and not st.session_state.df.empty:
        total_valeur = st.session_state.df['Acquisition (Devise Cible)'].sum()
        total_actuelle = st.session_state.df['Valeur Actuelle'].sum()
        
        # Pour H52 et LT, si ce sont des prix par titre, vous devez les convertir en valeur du portefeuille
        # à ces niveaux de prix. Si ce sont des valeurs totales déjà, utilisez-les directement.
        # Si 'H52' et 'Objectif_LT' sont les prix de chaque titre, nous devons les multiplier par la quantité
        # et les convertir à la devise cible pour obtenir des totaux significatifs.
        total_h52 = (st.session_state.df['Quantité'] * st.session_state.df.apply(
            lambda row: convertir(row['H52'], row['Devise'], st.session_state.devise_cible, st.session_state.fx_rates)
            if 'H52' in row and row['Devise'] != st.session_state.devise_cible else row.get('H52', 0), axis=1
        )).sum()
        
        total_lt = (st.session_state.df['Quantité'] * st.session_state.df.apply(
            lambda row: convertir(row['Objectif_LT'], row['Devise'], st.session_state.devise_cible, st.session_state.fx_rates)
            if 'Objectif_LT' in row and row['Devise'] != st.session_state.devise_cible else row.get('Objectif_LT', 0), axis=1
        )).sum()

        afficher_synthese_globale(
            total_valeur, # Ceci est la "total_acquisition_value"
            total_actuelle, # Ceci est la "total_current_value"
            total_h52, # Ceci est la "total_h52_value" calculée pour le portefeuille
            total_lt, # Ceci est la "total_lt_value" calculée pour le portefeuille
            st.session_state.df_historical_totals,
            st.session_state.devise_cible,
            st.session_state.target_allocations,
            st.session_state.target_volatility
        )
    else:
        st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir la synthèse.")

with onglets[1]:
    # La fonction afficher_portefeuille est bien appelée ici
    afficher_portefeuille(st.session_state.df, st.session_state.devise_cible)

    # Bouton pour enregistrer un snapshot manuel du portefeuille
    current_date = datetime.date.today()
    if st.button(f"Enregistrer le snapshot du portefeuille ({current_date.strftime('%Y-%m-%d')})", key="save_snapshot_btn"):
        with st.spinner("Enregistrement du snapshot quotidien du portefeuille...\nLe snapshot sera ajouté à l'historique ou mis à jour si un snapshot existe déjà pour aujourd'hui."):
            save_portfolio_snapshot(current_date, st.session_state.df, st.session_state.devise_cible)
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
