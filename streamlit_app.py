# streamlit_app.py

import streamlit as st
import pandas as pd
import numpy as np
import datetime # Importation de datetime
from PIL import Image
import base64
from io import BytesIO
import os # Nécessaire pour les opérations de fichiers

# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille, afficher_synthese_globale
from performance import display_performance_history # Nom de la fonction mis à jour
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change, actualiser_taux_change
from parametres import afficher_parametres_globaux # La fonction qui gère tous les paramètres globaux
from portfolio_journal import save_portfolio_snapshot, load_portfolio_journal # Nouveau import
# from historical_data_fetcher import get_all_historical_data # Non nécessaire ici directement
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
        .stButton>button {{
            background-color: {ACCENT_COLOR};
            color: white;
            border-radius: 5px;
            border: none;
            padding: 8px 16px;
        }}
        .stButton>button:hover {{
            background-color: #8C845B;
        }}
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {{
            font-size: 1.2rem;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 24px;
        }}
        .stTabs [data-baseweb="tab"] {{
            height: 50px;
            white-space: pre-wrap;
            background-color: {SECONDARY_COLOR};
            border-radius: 4px 4px 0 0;
            gap: 10px;
            padding-top: 10px;
            padding-bottom: 10px;
            font-weight: bold;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: {PRIMARY_COLOR};
            color: white;
        }}
        .stMetric {{
            background-color: #f0f2f6; /* Light gray background for metrics */
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stMetric label {{
            color: {PRIMARY_COLOR};
            font-weight: bold;
        }}
        .stMetric .css-1g6x58x-StMetricValue {{ /* Targeting the metric value specifically */
            color: {ACCENT_COLOR}; /* Make the metric values stand out */
        }}
    </style>
""", unsafe_allow_html=True)

# Initialisation des variables d'état si elles n'existent pas
if "df" not in st.session_state:
    st.session_state.df = None
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR"
if "last_update_time_fx" not in st.session_state:
    st.session_state.last_update_time_fx = datetime.datetime.min # Force update on first run
if "fx_rates" not in st.session_state:
    st.session_state.fx_rates = {}
if "last_devise_cible_for_fx_update" not in st.session_state:
    st.session_state.last_devise_cible_for_fx_update = ""
if "uploaded_file_id" not in st.session_state:
    st.session_state.uploaded_file_id = None # Pour détecter si un nouveau fichier a été uploadé

# Fonction utilitaire pour encoder une image en base64
@st.cache_data(ttl=3600)
def get_image_as_base64(file_path):
    with open(file_path, "rb") as f:
        image_bytes = f.read()
        encoded_string = base64.b64encode(image_bytes).decode()
    return encoded_string

# Définition du chemin de l'image (assurez-vous que l'image est dans le même répertoire ou spécifiez le chemin complet)
logo_path = os.path.join(os.path.dirname(__file__), "beam_logo.png")

# Tente de charger et d'afficher le logo
try:
    # Utiliser PIL pour ouvrir l'image et la convertir en PNG si elle ne l'est pas
    with Image.open(logo_path) as img:
        # Créer un tampon en mémoire pour sauvegarder l'image en PNG
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
    
    st.markdown(
        f"""
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 20px;">
            <img src="data:image/png;base64,{img_str}" alt="BEAM Logo" style="max-height: 100px;">
        </div>
        """,
        unsafe_allow_html=True
    )
except FileNotFoundError:
    st.warning(f"Le fichier logo '{logo_path}' n'a pas été trouvé. Veuillez vérifier le chemin.")
except Exception as e:
    st.error(f"Erreur lors du chargement ou de l'affichage du logo : {e}")


st.title("BEAM Portfolio Manager")

# Main application logic
def main():
    
    # Création des onglets
    tab_titles = ["Portefeuille", "Performance Historique", "Transactions", "Opérations Comptables", "Taux de Change", "Paramètres"]
    # Removed "Synthèse Quotidienne" tab as it's part of Performance tab now
    onglets = st.tabs(tab_titles)

    # Onglet : Portefeuille
    with onglets[0]:
        total_valeur, total_actuelle, total_h52, total_lt = afficher_portefeuille()
        # Appel de la synthèse globale si les totaux sont disponibles
        if total_valeur is not None:
            afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt)

    # Onglet : Performance Historique
    with onglets[1]:
        display_performance_history() # Appel de la fonction de performance.py

    # Onglet : Transactions
    with onglets[2]:
        afficher_transactions()

    # Onglet : Opérations Comptables
    with onglets[3]:
        afficher_od_comptables()

    # Onglet : Taux de Change
    with onglets[4]:
        st.subheader("Taux de Change Actuels")
        
        # Logique d'actualisation des taux de change
        current_time = datetime.datetime.now()
        # Actualise si plus de 15 minutes se sont écoulées ou si la devise cible a changé
        time_diff = (current_time - st.session_state.last_update_time_fx).total_seconds()
        devise_cible_actuelle = st.session_state.get("devise_cible", "EUR")

        if time_diff > 900 or st.session_state.last_devise_cible_for_fx_update != devise_cible_actuelle:
            with st.spinner(f"Actualisation des taux de change vers {devise_cible_actuelle}..."):
                # Obtenir toutes les devises présentes dans le portefeuille
                devises_uniques = []
                if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                    devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
                
                # Actualiser les taux
                st.session_state.fx_rates = actualiser_taux_change(devise_cible_actuelle, devises_uniques)
                st.session_state.last_update_time_fx = current_time # Met à jour le timestamp
                st.session_state.last_devise_cible_for_fx_update = devise_cible_actuelle
                st.success("Taux de change actualisés.")
        else:
            st.info(f"Dernière actualisation des taux : {st.session_state.last_update_time_fx.strftime('%Y-%m-%d %H:%M:%S')}. (Actualisation automatique toutes les 15 minutes).")
        
        st.caption("Les taux de change sont mis à jour automatiquement toutes les 60 secondes.") # Corrected previous typo
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
    with onglets[5]: # Changed from 6 to 5 as one tab was removed
        # Cette fonction doit gérer le téléchargement de fichier et la sélection de la devise cible
        # et mettre à jour st.session_state.df, st.session_state.devise_cible, etc.
        afficher_parametres_globaux()

# Run the main function
if __name__ == "__main__":
    main()
