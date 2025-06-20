# streamlit_app.py

import streamlit as st
import pandas as pd
import datetime
import requests # Garde requests si d'autres modules l'utilisent, sinon yfinance le remplace
from PIL import Image
import base64
from io import BytesIO
import time # NOUVEAU : Nécessaire pour time.sleep

# NOUVEAU : Importe toutes les fonctions du module taux_change.py
# Assurez-vous que taux_change.py est dans le même dossier
from taux_change import (
    actualiser_taux_change,
    afficher_tableau_taux_change,
    format_fr, # Utile si vous formatez des nombres ailleurs
    get_yfinance_ticker_info, # Utile pour d'autres appels yfinance
    obtenir_taux_yfinance # Utile pour des appels spécifiques si besoin
)

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
        /* Réajustement des styles pour correspondre au nouveau header */
        .st-emotion-cache-18ni7ap {{ /* En-tête de page Streamlit */
            background-color: {ACCENT_COLOR};
            padding: 10px;
            border-radius: 0 0 10px 10px;
            margin-bottom: 25px;
            margin-top: -55px; /* Ajuste si le logo remonte trop */
        }}
        section.main > div:nth-child(1) {{
            margin-top: -55px; /* Ajuste le contenu principal */
        }}
        /* Styles pour les en-têtes (h1, h2, etc.) */
        h1, h2, h3, h4, h5, h6 {{
            color: {PRIMARY_COLOR};
        }}
        /* Styles pour les onglets */
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {{
            font-size: 1.1em; /* Taille de police des onglets */
            font-weight: bold;
            color: {PRIMARY_COLOR}; /* Couleur du texte des onglets */
        }}
        .stTabs [data-baseweb="tab-list"] button.st-emotion-cache-1ftvtfb {{ /* Onglet actif */
            background-color: {PRIMARY_COLOR};
            color: {SECONDARY_COLOR};
            border-bottom: 3px solid {ACCENT_COLOR};
        }}
        .stTabs [data-baseweb="tab-list"] button:hover {{ /* Onglet survolé */
            background-color: {ACCENT_COLOR};
        }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] p {{ /* Texte de l'onglet sélectionné */
            color: {SECONDARY_COLOR};
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
# from taux_change import afficher_taux_change # REMPLACÉ PAR LA LOGIQUE D'ACTUALISATION CI-DESSOUS
from parametres import afficher_parametres
from od_comptables import afficher_od_comptables

# --- LOGIQUE D'ACTUALISATION DES TAUX DE CHANGE ---
# Ceci doit être en dehors des onglets pour pouvoir actualiser en arrière-plan
# et gérer l'état de session globalement.

# Conteneur pour l'affichage dynamique des taux de change
# Nous allons utiliser un placeholder pour mettre les taux à jour sans recharger toute l'application
# Cependant, avec la structure de Streamlit, chaque re-run recalcule tout.
# Le placeholder sera utilisé spécifiquement dans l'onglet des taux de change.

# Pour gérer l'actualisation automatique qui affecte le `st.session_state.fx_rates`
# et donc l'affichage dans l'onglet "Taux de change",
# la logique de la boucle `while True` doit être présente quelque part.
# Une bonne approche est de la placer au début ou dans une section dédiée
# de `streamlit_app.py` avant les onglets, ou de la déclencher depuis l'onglet.

# Cependant, la boucle `while True` avec `time.sleep` va rendre Streamlit
# réactif seulement toutes les X secondes. Pour un comportement optimal avec des onglets,
# nous allons déclencher l'actualisation via le bouton manuel ET à la première
# connexion/changement de fichier, puis laisser l'utilisateur actualiser manuellement
# ou se fier à l'actualisation par cache.
# L'actualisation automatique "en boucle" peut bloquer l'interface.

# Option 1 : Garder la logique de while True dans l'onglet "Taux de change"
# C'est la plus simple pour l'intégration existante.
# Nous allons remettre la logique d'actualisation automatique DANS l'onglet
# "Taux de change". Cela signifie que l'actualisation ne se fera que lorsque cet onglet est actif.
# Si vous voulez une actualisation "en fond", c'est plus complexe et implique des approches
# comme des threads ou des boucles asynchrones que Streamlit ne gère pas nativement dans
# la boucle principale de l'application.
# Pour le moment, nous allons adapter pour que l'onglet "Taux de change" contienne
# la logique d'actualisation que nous avions mise en place dans l'exemple précédent.

# Onglets horizontaux
onglets = st.tabs([
    "Portefeuille",
    "Performance",
    "OD Comptables",
    "Transactions",
    "Taux de change", # Cet onglet aura sa logique modifiée
    "Paramètres"
])

# Onglet : Portefeuille
with onglets[0]:
    # Vous devrez probablement passer st.session_state.fx_rates et st.session_state.devise_cible
    # à votre fonction afficher_portefeuille si elle en a besoin.
    # Assurez-vous que votre fonction afficher_portefeuille est à jour avec cela.
    afficher_portefeuille()

# Onglet : Performance
with onglets[1]:
    afficher_performance()

# Onglet : OD Comptables
with onglets[2]:
    afficher_od_comptables()

# Onglet : Transactions
with onglets[3]:
    afficher_transactions()

# Onglet : Taux de change (Mise à jour pour l'actualisation)
with onglets[4]:
    st.header("💱 Taux de Change Actuels")

    # Conteneur pour l'affichage dynamique des taux de change
    # Ceci est essentiel pour l'actualisation automatique à l'intérieur de l'onglet
    placeholder_taux = st.empty()

    # Logique d'actualisation des taux de change (manuelle ou automatique)
    # L'approche avec while True directement ici fera que l'onglet sera bloqué par le sleep.
    # Une meilleure approche pour les onglets est de charger les taux une fois
    # à la connexion et quand l'utilisateur change la devise cible.
    # Le `st.cache_data` sur `get_yfinance_ticker_info` gérera la fraîcheur des données.

    # Actualisation initiale ou si le fichier Excel a changé
    # Cette partie sera exécutée à chaque re-run (connexion, interaction)
    current_time = datetime.datetime.now()
    if (st.session_state.last_update_time == datetime.datetime.min) or \
       (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)): # Détecte nouveau fichier
        
        with st.spinner("Initialisation des taux de change..."):
            devise_cible = st.session_state.devise_cible
            devises_uniques = []
            if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
            
            st.session_state.fx_rates = actualiser_taux_change(devise_cible, devises_uniques)
            st.session_state.last_update_time = datetime.datetime.now()
            st.session_state._last_processed_file_id = st.session_state.get("uploaded_file_id") # Marque le fichier comme traité
            st.success(f"Taux de change initialisés pour {devise_cible}.")
            # Pas besoin de st.rerun() ici, car cela fait partie du re-run initial.

    # Bouton d'actualisation manuelle
    if st.button("Actualiser les taux (manuel)"):
        with st.spinner("Mise à jour manuelle des taux de change..."):
            devise_cible = st.session_state.devise_cible
            devises_uniques = []
            if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
            st.session_state.fx_rates = actualiser_taux_change(devise_cible, devises_uniques)
            st.session_state.last_update_time = datetime.datetime.now()
            st.success(f"Taux de change actualisés pour {devise_cible} (manuel).")
            # st.experimental_rerun() # Pour Streamlit < 1.18
            st.rerun() # Recharger toute l'application pour que les changements soient pris en compte

    # Affichage du tableau des taux de change
    # Le placeholder est utilisé pour permettre d'éventuels futurs rafraîchissements
    # sans reconstruire toute la page. Mais pour l'actualisation automatique, c'est le cache
    # de yfinance qui gère la fraîcheur ici.
    with placeholder_taux.container():
        afficher_tableau_taux_change(st.session_state.devise_cible, st.session_state.fx_rates)

    # Note sur l'actualisation automatique "toutes les 60 secondes":
    # La boucle `while True` + `time.sleep` est problématique avec la structure des onglets
    # car elle bloquerait l'application. Streamlit fonctionne par re-runs.
    # La stratégie est de se baser sur:
    # 1. Actualisation à la connexion (via `last_update_time = datetime.datetime.min`)
    # 2. Actualisation au changement de fichier Excel
    # 3. Actualisation manuelle via le bouton
    # 4. Le cache `st.cache_data` (ttl=15min) sur `get_yfinance_ticker_info` assure
    #    que les données ne sont pas trop anciennes si un re-run se produit
    #    pour une autre raison dans l'application.
    # Pour une vraie actualisation en fond toutes les 60 secondes indépendamment de l'onglet,
    # il faudrait une approche plus avancée non native à Streamlit (ex: threads, websockets, mais c'est complexe).
    # Pour le moment, cette approche est la plus compatible et la plus simple.

# Onglet : Paramètres
with onglets[5]:
    afficher_parametres()

st.markdown("---")
st.info("💡 Importez un fichier Excel pour visualiser et analyser votre portefeuille. Assurez-vous que les colonnes 'Quantité', 'Acquisition', 'Devise' et 'Ticker' (ou 'Tickers') sont présentes pour des calculs optimaux.")
