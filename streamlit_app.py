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
from parametres import afficher_parametres_globaux # La nouvelle fonction qui gère tous les paramètres

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
    "uploaded_file_id": None, # Pour suivre l'état du fichier chargé
    "_last_processed_file_id": None, # Pour suivre l'état du fichier traité
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# --- LOGIQUE D'ACTUALISATION DES TAUX DE CHANGE ---
# Cette logique doit être déclenchée si la devise cible change ou si le fichier est mis à jour
# ou si le temps d'actualisation est dépassé.
current_time = datetime.datetime.now()
if (st.session_state.last_update_time_fx == datetime.datetime.min) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)) or \
   (st.session_state.get("devise_cible") != st.session_state.get("last_devise_cible_for_fx_update", None)) or \
   ((current_time - st.session_state.last_update_time_fx).total_seconds() >= 60):

    devise_cible_to_use = st.session_state.get("devise_cible", "EUR")
    
    devises_uniques = []
    if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
        devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
    
    st.session_state.fx_rates = actualiser_taux_change(devise_cible_to_use, devises_uniques)
    st.session_state.last_update_time_fx = datetime.datetime.now()
    st.session_state.last_devise_cible_for_fx_update = devise_cible_to_use
    
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
        # Les totaux seront mis à jour par l'appel dans l'onglet "Portefeuille"
        # On passe ici les valeurs de session state
        afficher_synthese_globale(
            st.session_state.total_valeur,
            st.session_state.total_actuelle,
            st.session_state.total_h52,
            st.session_state.total_lt
        )

    # Onglet : Portefeuille
    with onglets[1]:
        if st.session_state.df is None:
            st.info("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' pour voir votre portefeuille.")
        else:
            # Appel de la fonction d'affichage du portefeuille et récupération des totaux
            # Ces totaux seront ensuite stockés dans st.session_state pour l'onglet Synthèse
            total_valeur, total_actuelle, total_h52, total_lt = afficher_portefeuille()
            st.session_state.total_valeur = total_valeur
            st.session_state.total_actuelle = total_actuelle
            st.session_state.total_h52 = total_h52
            st.session_state.total_lt = total_lt


    # Onglet : Performance
    with onglets[2]:
        if 'afficher_performance' in locals():
            afficher_performance()
        else:
            st.info("Module de performance non trouvé ou fonction non implémentée.")

    # Onglet : OD Comptables
    with onglets[3]:
        if 'afficher_od_comptables' in locals():
            afficher_od_comptables()
        else:
            st.info("Module des OD Comptables non trouvé ou fonction non implémentée.")

    # Onglet : Transactions
    with onglets[4]:
        if 'afficher_transactions' in locals():
            afficher_transactions()
        else:
            st.info("Module des transactions non trouvé ou fonction non implémentée.")

    # Onglet : Taux de change
    with onglets[5]:
        st.info(f"Les taux sont affichés par rapport à la devise de référence sélectionnée dans l'onglet 'Paramètres' : **{st.session_state.get('devise_cible', 'EUR')}**.")
        
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
        # Appel de la fonction de paramètres qui gère l'importation et la devise
        if 'afficher_parametres_globaux' in locals():
            afficher_parametres_globaux()
        else:
            st.info("Module des paramètres non trouvé ou fonction non implémentée.")


    st.markdown("---")
    
if __name__ == "__main__":
    main()
