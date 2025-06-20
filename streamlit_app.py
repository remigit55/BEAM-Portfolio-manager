# streamlit_app.py

import streamlit as st
import pandas as pd
import datetime
from PIL import Image
import base64
from io import BytesIO
import os # Nécessaire pour historical_data_manager

# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille, afficher_synthese_globale
from performance import display_performance_history # Renommé pour correspondre à notre implémentation
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change, actualiser_taux_change
from parametres import afficher_parametres_globaux # La fonction qui gère tous les paramètres globaux
from historical_data_manager import save_daily_totals, load_historical_data # Nouveau pour l'historique

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
        .st-emotion-cache-vk33gh {{ /* Ou .st-emotion-cache-1f06xpt / .st-emotion-cache-18ni7ap */
            display: none !important;
        }}
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
except FileNotFoundError: # Capturer l'erreur spécifique si le fichier n'est pas trouvé
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
    "devise_cible": "EUR", # Valeur par défaut
    "ticker_names_cache": {}, # Cache pour les noms de tickers (utilisé dans portfolio_display)
    "sort_column": None, # Colonne de tri pour le tableau du portefeuille
    "sort_direction": "asc", # Direction de tri
    "momentum_results": {}, # Cache pour les résultats de momentum
    "last_devise_cible_for_fx_update": "EUR", # Garder pour la logique de rafraîchissement des taux
    "last_update_time_fx": datetime.datetime.min, # Timestamp de la dernière mise à jour des taux
    "total_valeur": None, # Total valeur d'acquisition
    "total_actuelle": None, # Total valeur actuelle
    "total_h52": None, # Total valeur H52
    "total_lt": None, # Total valeur LT
    "uploaded_file_id": None, # Pour suivre l'état du fichier chargé (depuis les paramètres)
    "_last_processed_file_id": None, # Pour suivre l'état du fichier traité
    "url_data_loaded": False # Nouveau: pour marquer si les données URL ont été chargées
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- Chargement initial des données depuis Google Sheets URL si df est vide ---
# Cette logique ne s'exécute qu'une fois au début de la session si le DF n'est pas déjà chargé
if st.session_state.df is None and not st.session_state.url_data_loaded:
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    try:
        with st.spinner("Chargement initial du portefeuille depuis Google Sheets..."):
            df_initial = pd.read_csv(csv_url)
            st.session_state.df = df_initial
            st.session_state.url_data_loaded = True # Marquer comme chargé
            # Utiliser un ID spécifique pour le chargement URL pour éviter le conflit avec le file uploader
            st.session_state.uploaded_file_id = "initial_url_load" 
            st.session_state._last_processed_file_id = "initial_url_load"
            st.success("Portefeuille chargé depuis Google Sheets.")
            # Forcer une mise à jour des taux après le chargement initial
            st.session_state.last_update_time_fx = datetime.datetime.min # Remet le timer à zéro pour forcer l'update
            st.rerun() # Recharger pour que les données soient disponibles pour les autres onglets
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement initial du portefeuille depuis l'URL : {e}")
        st.session_state.url_data_loaded = True # Marquer pour ne pas essayer de charger en boucle si échec


# --- LOGIQUE D'ACTUALISATION AUTOMATIQUE DES TAUX DE CHANGE ---
current_time = datetime.datetime.now()
# Les taux sont actualisés si:
# 1. C'est le premier chargement (datetime.min)
# 2. Le fichier (uploaded_file_id ou URL) a changé (pour s'assurer que les devises sont à jour)
# 3. La devise cible a changé (l'utilisateur a sélectionné une autre devise)
# 4. Plus de 60 secondes se sont écoulées depuis la dernière mise à jour automatique
if (st.session_state.last_update_time_fx == datetime.datetime.min) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)) or \
   (st.session_state.get("devise_cible") != st.session_state.get("last_devise_cible_for_fx_update", None)) or \
   ((current_time - st.session_state.last_update_time_fx).total_seconds() >= 60):

    devise_cible_to_use = st.session_state.get("devise_cible", "EUR")
    
    devises_uniques = []
    if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
        devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
    
    # Appel à la fonction d'actualisation des taux de `taux_change.py`
    st.session_state.fx_rates = actualiser_taux_change(devise_cible_to_use, devises_uniques)
    st.session_state.last_update_time_fx = datetime.datetime.now()
    st.session_state.last_devise_cible_for_fx_update = devise_cible_to_use
    
    # Mettre à jour _last_processed_file_id uniquement si un fichier ou une URL a été chargé
    # Ceci évite de refetcher les taux si l'application est juste relancée sans nouveau fichier
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

            # --- Enregistrement des totaux quotidiens pour l'onglet Performance ---
            current_date = datetime.date.today() # Utiliser datetime.date pour la comparaison
            devise_cible = st.session_state.get("devise_cible", "EUR")

            history_df = load_historical_data()
            # Convertir la colonne 'Date' du DataFrame historique en objets datetime.date pour une comparaison correcte
            history_dates = history_df['Date'].dt.date.tolist() if not history_df.empty else []

            # Sauvegarder uniquement si les totaux sont valides et la date du jour n'est pas déjà enregistrée
            if (total_valeur is not None and pd.notna(total_valeur) and
                total_actuelle is not None and pd.notna(total_actuelle) and
                current_date not in history_dates):
                
                save_daily_totals(current_date, total_valeur, total_actuelle, total_h52, total_lt, devise_cible)
                st.info(f"Totaux du {current_date.strftime('%Y-%m-%d')} sauvegardés pour l'historique.")
            # --- Fin de l'enregistrement ---

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
    
if __name__ == "__main__":
    main()
