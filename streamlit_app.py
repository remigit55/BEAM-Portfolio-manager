# streamlit_app.py

import streamlit as st
import pandas as pd
import datetime # Pour gérer last_update_time
from PIL import Image
import base64
from io import BytesIO

# Importation des modules fonctionnels
# Pas besoin d'importer requests, time, html, components, yfinance ici.
# Ils sont gérés dans les modules spécifiques.
from portfolio_display import afficher_portefeuille # Votre fonction principale d'affichage du portefeuille
# from performance import afficher_performance # Gardez ces lignes si ces modules existent
# from transactions import afficher_transactions
# from od_comptables import afficher_od_comptables
# from parametres import afficher_parametres

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

# Initialisation des variables de session (ajout de last_devise_cible pour la gestion des taux)
for key, default in {
    "df": None,
    "fx_rates": {}, # Les taux de change seront gérés par data_fetcher
    "devise_cible": "EUR",
    "ticker_names_cache": {}, # Le cache est maintenant dans data_fetcher via st.session_state
    "sort_column": None,
    "sort_direction": "asc",
    "momentum_results": {}, # Les résultats momentum sont aussi gérés par data_fetcher
    "last_devise_cible": "EUR", # Pour détecter le changement de devise cible
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- Structure de l'application principale ---
def main():
    # Sidebar pour l'importation de fichiers et les paramètres
    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("📥 Choisissez un fichier CSV", type=["csv", "xlsx"]) # Ajout de xlsx si vous traitez les deux
        if uploaded_file is not None:
            # Utilisez un ID de fichier pour détecter un nouveau fichier et éviter de recharger inutilement
            if "uploaded_file_id" not in st.session_state or st.session_state.uploaded_file_id != uploaded_file.file_id:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_uploaded = pd.read_csv(uploaded_file)
                    elif uploaded_file.name.endswith('.xlsx'):
                        df_uploaded = pd.read_excel(uploaded_file)
                    
                    st.session_state.df = df_uploaded
                    st.session_state.uploaded_file_id = uploaded_file.file_id # Enregistre l'ID du fichier
                    st.success("Fichier importé avec succès !")
                    
                    # Réinitialiser le tri et les caches de données liées au portefeuille après un nouvel import
                    st.session_state.sort_column = None
                    st.session_state.sort_direction = "asc"
                    st.session_state.ticker_names_cache = {} # Vider le cache des noms de tickers
                    # st.session_state.momentum_results = {} # Vider le cache des résultats de momentum
                    
                    # Forcer un effacement du cache pour les fonctions data_fetcher
                    # Cela va invalider le cache pour fetch_yahoo_data et fetch_momentum_data
                    # quand un nouveau fichier est uploadé, assurant que de nouvelles données
                    # seront téléchargées pour les tickers du nouveau fichier.
                    # Pas besoin d'appeler explicitement clear_cache pour fetch_fx_rates car sa base est gérée par devise_cible.
                    st.cache_data.clear() # Efface tous les caches de type cache_data
                    st.cache_resource.clear() # Efface tous les caches de type cache_resource (si vous en utilisez)

                    st.rerun() # Recharger pour appliquer les changements
                except Exception as e:
                    st.error(f"❌ Erreur lors de la lecture du fichier : {e}")
                    st.session_state.df = None
            else:
                st.info("Fichier déjà chargé.") # Message si le même fichier est re-sélectionné
        elif st.session_state.df is None:
            st.info("Veuillez importer un fichier pour voir les données du portefeuille.")

        st.header("💱 Paramètres de Devise")
        selected_devise = st.selectbox(
            "Devise cible pour l'affichage",
            ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
            index=["EUR", "USD", "GBP", "JPY", "CAD", "CHF"].index(st.session_state.get("devise_cible", "EUR")),
            key="devise_selector" # Ajout d'une clé pour assurer l'unicité
        )
        if selected_devise != st.session_state.get("devise_cible", "EUR"):
            st.session_state.devise_cible = selected_devise
            # Pas besoin de rerun ici, le changement de devise_cible sera pris en compte
            # au prochain run de `afficher_portefeuille` via `fetch_fx_rates`.
            # Si vous voulez un rechargement immédiat, ajoutez st.rerun()
            st.rerun() 
            

    # Onglets horizontaux
    onglets = st.tabs([
        "Portefeuille",
        # "Performance",
        # "OD Comptables",
        # "Transactions",
        # "Taux de change",
        # "Paramètres"
    ])

    # Onglet : Portefeuille
    with onglets[0]:
        afficher_portefeuille() # La fonction gère désormais tout en interne

    # Ajoutez ici les autres onglets et leurs fonctions
    # with onglets[1]:
    #     afficher_performance()
    # etc.

    st.markdown("---")
    st.info("💡 Importez un fichier CSV ou Excel pour visualiser et analyser votre portefeuille. Assurez-vous que les colonnes 'Quantité', 'Acquisition', 'Devise' et 'Ticker' (ou 'Tickers') sont présentes pour des calculs optimaux.")

if __name__ == "__main__":
    main()
