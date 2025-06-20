# streamlit_app.py

import streamlit as st
import pandas as pd
import datetime
import requests
from PIL import Image
import base64
from io import BytesIO
import time # NOUVEAU : Nécessaire pour time.sleep

# NOUVEAU : Importe toutes les fonctions du module taux_change.py
# Assurez-vous que taux_change.py est dans le même dossier
from taux_change import (
    actualiser_taux_change,
    afficher_tableau_taux_change # C'est la fonction principale pour l'affichage de la table
    # Vous pouvez importer d'autres fonctions si vous les utilisez directement ici
    # format_fr,
    # get_yfinance_ticker_info,
    # obtenir_taux_yfinance
)

# Configuration de la page
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Thème personnalisé (RESTAURÉ À VOTRE VERSION ORIGINALE)
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
    logo = Image.open("Logo.png.png")  # Ajuste le nom si besoin
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

# Initialisation des variables de session (AJOUT de last_update_time)
for key, default in {
    "df": None,
    "fx_rates": {},
    "devise_cible": "EUR",
    "ticker_names_cache": {},
    "sort_column": None,
    "sort_direction": "asc",
    "momentum_results": {},
    "last_update_time": datetime.datetime.min # NOUVEAU : Pour l'actualisation automatique des taux
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Importation des modules fonctionnels (gardés tels quels)
from portefeuille import afficher_portefeuille
from performance import afficher_performance
from transactions import afficher_transactions
# from taux_change import afficher_taux_change # CETTE LIGNE EST MAINTENANT GÉRÉE PAR NOTRE LOGIQUE DIRECTEMENT
from parametres import afficher_parametres
from od_comptables import afficher_od_comptables

# --- LOGIQUE D'ACTUALISATION DES TAUX DE CHANGE ---
# Cette logique doit être exécutée à chaque re-run de l'application
# pour gérer l'actualisation à la connexion, au chargement de fichier, etc.

current_time = datetime.datetime.now()
# Actualisation initiale ou si le fichier Excel a changé ou toutes les 60 secondes (basé sur ttl du cache)
# La condition `st.session_state.last_update_time == datetime.datetime.min` force un premier run
# La condition `uploaded_file_id` détecte si un nouveau fichier a été chargé
# La condition de temps assure une actualisation régulière si l'app est active,
# mais c'est surtout le `ttl` de `st.cache_resource` dans `taux_change.py` qui gérera la fraîcheur.
if (st.session_state.last_update_time == datetime.datetime.min) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)) or \
   ((current_time - st.session_state.last_update_time).total_seconds() >= 60): # Ajout d'une condition basée sur le temps pour déclencher l'actualisation

    with st.spinner("Mise à jour des taux de change..."):
        devise_cible_for_update = st.session_state.devise_cible
        devises_uniques = []
        if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
            devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
        
        st.session_state.fx_rates = actualiser_taux_change(devise_cible_for_update, devises_uniques)
        st.session_state.last_update_time = datetime.datetime.now()
        # Stocke l'ID du fichier traité pour éviter de recharger inutilement
        if st.session_state.get("uploaded_file_id") is not None:
             st.session_state._last_processed_file_id = st.session_state.uploaded_file_id
        
        # Ce message s'affichera brièvement au-dessus du contenu si l'actualisation auto se déclenche
        # st.success(f"Taux de change actualisés pour {devise_cible_for_update} (auto).")

# --- FIN LOGIQUE D'ACTUALISATION DES TAUX DE CHANGE ---


# Onglets horizontaux
onglets = st.tabs([
    "Portefeuille",
    "Performance",
    "OD Comptables",
    "Transactions",
    "Taux de change", # Cet onglet affichera les taux
    "Paramètres"
])

# Onglet : Portefeuille
with onglets[0]:
    # Passez les taux de change à afficher_portefeuille si nécessaire pour les calculs
    afficher_portefeuille(fx_rates=st.session_state.fx_rates, devise_cible=st.session_state.devise_cible)

# Onglet : Performance
with onglets[1]:
    afficher_performance()

# Onglet : OD Comptables
with onglets[2]:
    afficher_od_comptables()

# Onglet : Transactions
with onglets[3]:
    afficher_transactions()

# Onglet : Taux de change
with onglets[4]:
    st.header("💱 Taux de Change Actuels")

    # Bouton d'actualisation manuelle pour cet onglet
    if st.button("Actualiser les taux (manuel)"):
        with st.spinner("Mise à jour manuelle des taux de change..."):
            devise_cible_for_manual_update = st.session_state.devise_cible
            devises_uniques = []
            if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
            st.session_state.fx_rates = actualiser_taux_change(devise_cible_for_manual_update, devises_uniques)
            st.session_state.last_update_time = datetime.datetime.now()
            st.success(f"Taux de change actualisés pour {devise_cible_for_manual_update} (manuel).")
            st.rerun() # Recharger toute l'application pour que les changements soient pris en compte

    # Affiche le tableau des taux de change en utilisant les données de session
    afficher_tableau_taux_change(st.session_state.devise_cible, st.session_state.fx_rates)

# Onglet : Paramètres
with onglets[5]:
    afficher_parametres()

st.markdown("---")
st.info("💡 Importez un fichier Excel pour visualiser et analyser votre portefeuille. Assurez-vous que les colonnes 'Quantité', 'Acquisition', 'Devise' et 'Ticker' (ou 'Tickers') sont présentes pour des calculs optimaux.")
