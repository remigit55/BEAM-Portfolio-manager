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
from performance import display_performance_history # Nom de la fonction mis à jour
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


# --- Structure de l'application principale ---
def main():
    """
    Gère la logique principale de l'application Streamlit, y compris la navigation par onglets.
    """
    # Onglets horizontaux pour la navigation principale
    onglets = st.tabs([
        "Synthèse",
        "Portefeuille",
        "Performance",
        "OD Comptables",
        "Transactions",
        "Taux de change",
        "Paramètres"
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
            # La fonction afficher_portefeuille retourne les totaux calculés
            total_valeur, total_actuelle, total_h52, total_lt = afficher_portefeuille()
            # Mettre à jour les totaux dans session_state pour qu'ils soient accessibles à la synthèse
            st.session_state.total_valeur = total_valeur
            st.session_state.total_actuelle = total_actuelle
            st.session_state.total_h52 = total_h52
            st.session_state.total_lt = total_lt

            # --- Enregistrement du snapshot du portefeuille pour le journal historique ---
            current_date = datetime.date.today()
            devise_cible = st.session_state.get("devise_cible", "EUR")
            
            # Charger le journal pour vérifier la dernière date enregistrée
            journal_entries = load_portfolio_journal()
            journal_dates = [entry['date'] for entry in journal_entries]

            # Sauvegarder si le df n'est pas vide et si la date du jour n'est pas déjà enregistrée
            if st.session_state.df is not None and not st.session_state.df.empty and current_date not in journal_dates:
                with st.spinner("Enregistrement du snapshot quotidien du portefeuille..."):
                    save_portfolio_snapshot(current_date, st.session_state.df, devise_cible)
                st.info(f"Snapshot du portefeuille du {current_date.strftime('%Y-%m-%d')} enregistré pour l'historique.")
            # --- Fin de l'enregistrement du snapshot ---

    # Onglet : Performance
    with onglets[2]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        else:
            display_performance_history() # Appel de la fonction de performance.py
            
    # Onglet : OD Comptables
    with onglets[3]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour générer les OD Comptables.")
        else:
            afficher_od_comptables() # Appel de la fonction de od_comptables.py
            
    # Onglet : Transactions
    with onglets[4]:
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour gérer les transactions.")
        else:
            afficher_transactions() # Appel de la fonction de transactions.py
            
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
                st.session_state.last_update_time_fx = datetime.datetime.now() # Met à jour le timestamp
                st.session_state.last_devise_cible_for_fx_update = devise_cible_for_manual_update
                st.success(f"Taux de change actualisés pour {devise_cible_for_manual_update}.")
                st.rerun() # Re-exécuter pour afficher les nouveaux taux

        afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

    # Onglet : Paramètres
    with onglets[6]:
        # Cette fonction doit gérer le téléchargement de fichier et la sélection de la devise cible
        # et mettre à jour st.session_state.df, st.session_state.uploaded_file_id et st.session_state.devise_cible
        afficher_parametres_globaux() 

   
    st.markdown("---")

    
    st.subheader("🛠️ Outil de Test Yahoo Finance (temporaire)")
    st.write("Utilisez cet outil pour vérifier la connectivité de l'application à Yahoo Finance.")

    test_ticker = st.text_input("Entrez un symbole boursier pour le test (ex: MSFT, AAPL, GLDG)", value="GLDG")
    test_days_ago = st.slider("Nombre de jours d'historique à récupérer", 1, 365, 30)

    if st.button("Lancer le test de connexion Yahoo Finance"):
        import datetime as dt_test
        from datetime import timedelta as td_test
        
        start_date = dt_test.datetime.now() - td_test(days=test_days_ago)
        end_date = dt_test.datetime.now()

        st.info(f"Tentative de récupération des données pour **{test_ticker}** du **{start_date.strftime('%Y-%m-%d')}** au **{end_date.strftime('%Y-%m-%d')}**...")
        
        import builtins 

        try:
            # L'appel à yf.download est maintenant valide car yf est importé au début du fichier
            data = yf.download(test_ticker, 
                               start=start_date.strftime('%Y-%m-%d'), 
                               end=end_date.strftime('%Y-%m-%d'), 
                               progress=False)

            if not data.empty:
                st.success(f"✅ Données récupérées avec succès pour {test_ticker}!")
                st.write("Aperçu des données :")
                st.dataframe(data.head())
                st.write("...")
                st.dataframe(data.tail())
                st.write(f"Nombre total d'entrées : **{len(data)}**")
                st.write(f"Type de l'objet retourné : `{builtins.str(type(data))}`")
                st.write(f"L'index est un `DatetimeIndex` : `{builtins.isinstance(data.index, pd.DatetimeIndex)}`")

                st.subheader("Graphique des cours de clôture")
                st.line_chart(data['Close'])

            else:
                st.warning(f"❌ Aucune donnée récupérée pour {test_ticker} sur la période spécifiée. "
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
    
    if __name__ == "__main__":
    main()
