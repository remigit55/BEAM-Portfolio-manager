# streamlit_app.py

import streamlit as st
import pandas as pd
import numpy as np
import datetime # Importation de datetime
from PIL import Image
import base64
from io import BytesIO
import os # Nécessaire pour les opérations de fichiers
import yfinance as yf


# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille, afficher_synthese_globale
# from performance import display_performance_history # Nom de la fonction mis à jour
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change, actualiser_taux_change
from parametres import afficher_parametres_globaux # La fonction qui gère tous les paramètres globaux
from portfolio_journal import save_portfolio_snapshot, load_portfolio_journal # Nouveau import
from historical_data_fetcher import fetch_stock_history # Importez fetch_stock_history
# from historical_performance_calculator import reconstruct_historical_performance # Non nécessaire ici directement
from data_loader import load_data, save_data # Nécessaire si vous avez une fonction de sauvegarde du df initial
from utils import safe_escape, format_fr # Assurez-vous que ces fonctions sont présentes

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
    # Assurez-vous que le fichier 'Logo.png.png' existe dans le même répertoire que streamlit_app.py
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
    "df": None, # Le DataFrame du portefeuille courant
    "fx_rates": {}, # Taux de change actuels
    "devise_cible": "EUR", # Devise d'affichage par défaut
    "ticker_data_cache": {}, # Cache pour les données Yahoo Finance (prix actuels, noms, etc.)
    "momentum_results_cache": {}, # Cache pour les résultats de momentum
    "sort_column": None, # Colonne de tri pour le tableau du portefeuille
    "sort_direction": "asc", # Direction de tri
    "last_devise_cible_for_fx_update": "EUR", # Pour la logique d'actualisation des taux
    "last_update_time_fx": datetime.datetime.min, # Timestamp de la dernière mise à jour des taux
    "total_valeur": None, # Total valeur d'acquisition
    "total_actuelle": None, # Total valeur actuelle
    "total_h52": None, # Total valeur H52
    "total_lt": None, # Total valeur LT
    "uploaded_file_id": None, # Pour suivre l'état du fichier chargé via l'uploader dans 'Paramètres'
    "_last_processed_file_id": None, # Pour suivre l'état du fichier traité pour les mises à jour auto
    "url_data_loaded": False # Pour marquer si les données URL ont été chargées
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
            st.session_state.last_update_time_fx = datetime.datetime.min # Forcer mise à jour des taux
            st.rerun() # Pour que les données soient disponibles immédiatement
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement initial du portefeuille depuis l'URL : {e}")
        st.session_state.url_data_loaded = True


# --- LOGIQUE D'ACTUALISATION AUTOMATIQUE DES TAUX DE CHANGE ---
current_time = datetime.datetime.now()
# Les taux sont actualisés si:
# 1. C'est le premier chargement (datetime.min)
# 2. Le fichier (uploaded_file_id ou URL) a changé
# 3. La devise cible a changé
# 4. Plus de 60 secondes se sont écoulées depuis la dernière mise à jour
if (st.session_state.last_update_time_fx == datetime.datetime.min) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)) or \
   (st.session_state.get("devise_cible") != st.session_state.get("last_devise_cible_for_fx_update", None)) or \
   ((current_time - st.session_state.last_update_time_fx).total_seconds() >= 60):

    devise_cible_to_use = st.session_state.get("devise_cible", "EUR")
    
    devises_uniques = []
    if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
        devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
    
    with st.spinner(f"Mise à jour automatique des taux de change pour {devise_cible_to_use}..."):
        st.session_state.fx_rates = actualiser_taux_change(devise_cible_to_use, devises_uniques)
        st.session_state.last_update_time_fx = datetime.datetime.now()
        st.session_state.last_devise_cible_for_fx_update = devise_cible_to_use
    
    if st.session_state.get("uploaded_file_id") is not None:
        st.session_state._last_processed_file_id = st.session_state.uploaded_file_id







# --- NOUVELLE FONCTION DE TEST GLDG (à ajouter n'importe où hors de main()) ---
def display_gldg_test_standalone():
    st.subheader("📊 Test de Récupération des Données Historiques GLDG (Standalone)")
    st.write("Ce test est directement intégré dans `streamlit_app.py` pour isoler le problème de `str()`.")

    today = datetime.datetime.now() # Utilisez datetime.datetime pour être explicite
    default_start_date_gldg = today - datetime.timedelta(days=30)
    
    start_date_gldg = st.date_input(
        "Date de début (GLDG)",
        value=default_start_date_gldg.date(), # .date() pour obtenir seulement la date
        min_value=datetime.datetime(1990, 1, 1).date(),
        max_value=today.date(),
        key="start_date_gldg_test_standalone" # Clé unique pour éviter les conflits
    )
    end_date_gldg = st.date_input(
        "Date de fin (GLDG)",
        value=today.date(),
        min_value=datetime.datetime(1990, 1, 1).date(),
        max_value=today.date(),
        key="end_date_gldg_test_standalone" # Clé unique
    )

    if st.button("Récupérer les données GLDG (Standalone)"):
        st.info(f"Tentative de récupération des données pour GLDG du {start_date_gldg.strftime('%Y-%m-%d')} au {end_date_gldg.strftime('%Y-%m-%d')}...")
        
        try:
            # Convertir les objets date en datetime.datetime pour fetch_stock_history
            start_dt_gldg = datetime.datetime.combine(start_date_gldg, datetime.datetime.min.time())
            end_dt_gldg = datetime.datetime.combine(end_date_gldg, datetime.datetime.max.time())
            
            historical_prices = fetch_stock_history("GLDG", start_dt_gldg, end_dt_gldg)

            if not historical_prices.empty:
                st.success(f"✅ Données récupérées avec succès pour GLDG!")
                st.write("Aperçu des données (5 premières lignes) :")
                st.dataframe(historical_prices.head(), use_container_width=True)
                st.write("...")
                st.write("Aperçu des données (5 dernières lignes) :")
                st.dataframe(historical_prices.tail(), use_container_width=True)
                st.write(f"Nombre total de jours : **{len(historical_prices)}**")
                # Utilisation de builtins.str et builtins.isinstance pour plus de robustesse
                st.write(f"Type de l'objet retourné : `{builtins.str(type(historical_prices))}`")
                st.write(f"L'index est un `DatetimeIndex` : `{builtins.isinstance(historical_prices.index, pd.DatetimeIndex)}`")

                st.subheader("Graphique des cours de clôture GLDG")
                st.line_chart(historical_prices)

            else:
                st.warning(f"❌ Aucune donnée récupérée pour GLDG sur la période spécifiée. "
                           "Vérifiez le ticker ou la période, et votre connexion à Yahoo Finance.")
        except Exception as e:
            st.error(f"❌ Une erreur est survenue lors de la récupération des données : {builtins.str(e)}")
            if "str' object is not callable" in builtins.str(e):
                st.error("⚠️ **Confirmation :** L'erreur `str() object is not callable` persiste. Cela indique fortement "
                         "qu'une variable ou fonction nommée `str` est définie ailleurs dans votre code, "
                         "écrasant la fonction native de Python. **La recherche globale `str = ` est impérative.**")
            elif "No data found" in builtins.str(e) or "empty DataFrame" in builtins.str(e):
                 st.warning("Yahoo Finance n'a pas retourné de données. Le ticker est-il valide ? La période est-elle trop courte ou dans le futur ?")
            else:
                st.error(f"Détail de l'erreur : {builtins.str(e)}")













# --- Structure de l'application principale ---
def main():
    """
    Gère la logique principale de l'application Streamlit, y compris la navigation par onglets.
    """
    # Initialisation des états de session si nécessaire (si non déjà fait au début du script)
    if "df" not in st.session_state:
        st.session_state.df = None
    if "fx_rates" not in st.session_state:
        st.session_state.fx_rates = {} # Initialisez avec un dictionnaire vide
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR" # Devise cible par défaut

    # Initialisation des totaux à None si non déjà fait
    if "total_valeur" not in st.session_state:
        st.session_state.total_valeur = None
        st.session_state.total_actuelle = None
        st.session_state.total_h52 = None
        st.session_state.total_lt = None


    # Onglets horizontaux pour la navigation principale
    # AJOUTEZ UN NOUVEL ONGLET POUR LE TEST GLDG
    onglets = st.tabs([
        "Synthèse",
        "Portefeuille",
        "Performance", # Cet onglet sera pour le test GLDG
        "OD Comptables",
        "Transactions",
        "Taux de change",
        "Paramètres",
        "Test GLDG" # NOUVEL ONGLET POUR LE TEST
    ])

    # Onglet : Synthèse
    with onglets[0]:
        afficher_synthese_globale(
            st.session_state.total_valeur,
            st.session_state.total_actuelle,
            st.session_state.total_h52,
            st.session_state.total_lt
        )

    # Onglet : Portefeuille
    with onglets[1]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets.")
        else:
            total_valeur, total_actuelle, total_h52, total_lt = afficher_portefeuille()
            st.session_state.total_valeur = total_valeur
            st.session_state.total_actuelle = total_actuelle
            st.session_state.total_h52 = total_h52
            st.session_state.total_lt = total_lt

            # --- Enregistrement du snapshot du portefeuille pour le journal historique ---
            current_date = datetime.date.today()
            devise_cible = st.session_state.get("devise_cible", "EUR")
            
            journal_entries = load_portfolio_journal()
            journal_dates = [entry['date'] for entry in journal_entries]

            if st.session_state.df is not None and not st.session_state.df.empty and current_date not in journal_dates:
                with st.spinner("Enregistrement du snapshot quotidien du portefeuille..."):
                    save_portfolio_snapshot(current_date, st.session_state.df, devise_cible)
                st.info(f"Snapshot du portefeuille du {current_date.strftime('%Y-%m-%d')} enregistré pour l'historique.")
            # --- Fin de l'enregistrement du snapshot ---

    # Onglet : Performance (Cet onglet peut continuer à appeler display_performance_history
    # si vous souhaitez le conserver pour la performance globale APRES AVOIR RESOLU LE PROBLEME STR())
    # Pour l'instant, on va utiliser le DERNIER onglet pour le test GLDG
    with onglets[2]: # C'est votre onglet "Performance" original
        # Vous pouvez le laisser tel quel si vous le souhaitez, mais assurez-vous que performance.py
        # est correctement corrigé pour le problème de str().
        # Si vous voulez le désactiver temporairement pour le test, vous pouvez mettre:
        st.info("L'onglet 'Performance' est temporairement désactivé pour le débogage du test GLDG.")
        st.warning("Pour un test direct de GLDG, allez à l'onglet 'Test GLDG'.")
        # Si vous voulez qu'il appelle display_performance_history() APRES la correction de str():
        # if st.session_state.df is None:
        #     st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        # else:
        #     display_performance_history() # Appel de la fonction de performance.py (assurez-vous de réactiver son import en haut)
            
    # Onglet : OD Comptables
    with onglets[3]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour générer les OD Comptables.")
        else:
            afficher_od_comptables()
            
    # Onglet : Transactions
    with onglets[4]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour gérer les transactions.")
        else:
            afficher_transactions()
            
    # Onglet : Taux de change
    with onglets[5]:
        st.subheader("Taux de Change Actuels")
        st.info("Les taux sont automatiquement mis à jour à chaque chargement de fichier, changement de devise cible, ou toutes les 60 secondes.")
        if st.button("Actualiser les taux manuellement", key="manual_fx_refresh_btn_tab"):
            with st.spinner("Mise à jour manuelle des taux de change..."):
                devise_cible_for_manual_update = st.session_state.get("devise_cible", "EUR")
                devises_uniques = []
                if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                    devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
                
                st.session_state.fx_rates = actualiser_taux_change(devise_cible_for_manual_update, devises_uniques)
                st.session_state.last_update_time_fx = datetime.datetime.now()
                st.session_state.last_devise_cible_for_fx_update = devise_cible_for_manual_update
                st.success(f"Taux de change actualisés pour {devise_cible_for_manual_update}.")
                st.rerun()

        afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

    # Onglet : Paramètres
    with onglets[6]:
        afficher_parametres_globaux()
    
    # NOUVEL ONGLET : Test GLDG (c'est l'index 7 car il y a 7 onglets avant lui)
    with onglets[7]:
        display_gldg_test_standalone() # Appel de la fonction de test GLDG directement

# Ne modifiez pas cette ligne
if __name__ == "__main__":
    main()

