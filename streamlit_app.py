# streamlit_app.py

import streamlit as st
import pandas as pd
import datetime
from PIL import Image
import base64
from io import BytesIO

# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille, afficher_synthese_globale
from performance import afficher_performance
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change, actualiser_taux_change
from parametres import afficher_parametres_globaux # La fonction qui gère tous les paramètres globaux

# Configuration de la page
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Thème personnalisé (Votre code original)
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
    logo = Image.open("Logo.png.png")
    buffer = BytesIO()
    logo.save(buffer, format="PNG")
    logo_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
except Exception:
    st.warning("Logo.png.png non trouvé ou erreur de chargement. Vérifiez le chemin.")
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
    "ticker_names_cache": {},
    "sort_column": None,
    "sort_direction": "asc",
    "momentum_results": {},
    "last_devise_cible_for_fx_update": "EUR", # Garder pour la logique de rafraîchissement
    "last_update_time_fx": datetime.datetime.min,
    "total_valeur": None,
    "total_actuelle": None,
    "total_h52": None,
    "total_lt": None,
    "uploaded_file_id": None, # Pour suivre l'état du fichier chargé (pour le uploader)
    "_last_processed_file_id": None, # Pour suivre l'état du fichier traité
    "url_data_loaded": False # Nouveau: pour marquer si les données URL ont été chargées
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
            st.session_state.url_data_loaded = True # Marquer comme chargé
            # Utiliser un ID spécifique pour le chargement URL pour éviter le conflit avec le file uploader
            st.session_state.uploaded_file_id = "initial_url_load" 
            st.session_state._last_processed_file_id = "initial_url_load"
            st.success("Portefeuille chargé depuis Google Sheets.")
            # Forcer une mise à jour des taux après le chargement initial
            st.session_state.last_update_time_fx = datetime.datetime.min
            st.rerun() # Recharger pour que les données soient disponibles pour les autres onglets
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement initial du portefeuille depuis l'URL : {e}")
        st.session_state.url_data_loaded = True # Marquer pour ne pas essayer de charger en boucle si échec


# --- LOGIQUE D'ACTUALISATION DES TAUX DE CHANGE ---
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
    
    # Appel à la fonction d'actualisation des taux de `taux_change.py`
    st.session_state.fx_rates = actualiser_taux_change(devise_cible_to_use, devises_uniques)
    st.session_state.last_update_time_fx = datetime.datetime.now()
    st.session_state.last_devise_cible_for_fx_update = devise_cible_to_use
    
    # Mettre à jour _last_processed_file_id uniquement si un fichier ou une URL a été chargé
    if st.session_state.get("uploaded_file_id") is not None:
         st.session_state._last_processed_file_id = st.session_state.uploaded_file_id


# --- Structure de l'application principale ---
def main():
    # Onglets horizontaux
    onglets = st.tabs([
        "Synthèse",
        "Portefeuille",
        "Performance",
        "OD Comptables",
        "Transactions",
        "Taux de change",
        "Paramètres" # L'onglet Paramètres va maintenant gérer le téléchargement et la devise
    ])

    # Onglet : Synthèse
    with onglets[0]:
        st.header("✨ Synthèse du Portefeuille")
        afficher_synthese_globale(
            st.session_state.total_valeur,
            st.session_state.total_actuelle,
            st.session_state.total_h52,
            st.session_state.total_lt
        )

    # Onglet : Portefeuille
    with onglets[1]:
        st.header("📈 Vue détaillée du Portefeuille")
        if st.session_state.df is None:
            st.warning("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets.") # Message mis à jour
        else:
            total_valeur, total_actuelle, total_h52, total_lt = afficher_portefeuille()
            st.session_state.total_valeur = total_valeur
            st.session_state.total_actuelle = total_actuelle
            st.session_state.total_h52 = total_h52
            st.session_state.total_lt = total_lt


    # Onglet : Performance
    with onglets[2]:
        st.header("📊 Analyse de Performance")
        if 'afficher_performance' in locals():
            afficher_performance()
        
    # Onglet : OD Comptables
    with onglets[3]:
        st.header("🧾 Opérations Diverses Comptables")
        if 'afficher_od_comptables' in locals():
            afficher_od_comptables()
        
    # Onglet : Transactions
    with onglets[4]:
        st.header("📜 Historique des Transactions")
        if 'afficher_transactions' in locals():
            afficher_transactions()
        
    # Onglet : Taux de change
    with onglets[5]:
        st.header("💱 Taux de Change Actuels")
        
        if st.button("Actualiser les taux (manuel)", key="manual_fx_refresh_btn_tab"):
            with st.spinner("Mise à jour manuelle des taux de change..."):
                devise_cible_for_manual_update = st.session_state.get("devise_cible", "EUR")
                devises_uniques = []
                if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                    devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
                
                st.session_state.fx_rates = actualiser_taux_change(devise_cible_for_manual_update, devises_uniques)
                st.session_state.last_update_time_fx = datetime.datetime.now()
                st.session_state.last_devise_cible_for_fx_update = devise_cible_for_manual_update
                st.success(f"Taux de change actualisés pour {devise_cible_for_manual_update} (manuel).")
                st.rerun()

        afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

    # Onglet : Paramètres
    with onglets[6]:
        st.header("⚙️ Paramètres de l'Application")
        afficher_parametres_globaux()


    st.markdown("---")
    
if __name__ == "__main__":
    main()
