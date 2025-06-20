# streamlit_app.py

import streamlit as st
import pandas as pd
import datetime
from PIL import Image
import base64
from io import BytesIO

# Importation des modules fonctionnels
from portfolio_display import afficher_portefeuille

# Assurez-vous que ces fichiers existent et contiennent les fonctions correspondantes.
# Si un fichier ou une fonction n'existe pas, commentez la ligne correspondante.
# Exemple : si vous n'avez pas de fichier performance.py, commentez la ligne ci-dessous.
from performance import afficher_performance
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change, actualiser_taux_change # On a besoin de ces deux pour l'onglet Taux de Change
from parametres import afficher_parametres # Pour l'onglet Paramètres

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

# Initialisation des variables de session
for key, default in {
    "df": None,
    "fx_rates": {}, # Les taux de change seront gérés par data_fetcher
    "devise_cible": "EUR",
    "ticker_names_cache": {},
    "sort_column": None,
    "sort_direction": "asc",
    "momentum_results": {},
    "last_devise_cible": "EUR",
    "last_update_time_fx": datetime.datetime.min # NOUVEAU: Pour gérer la fraîcheur des taux de change
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- LOGIQUE D'ACTUALISATION DES TAUX DE CHANGE POUR L'ONGLET DÉDIÉ ---
# Cette logique est séparée de celle de portfolio_display car elle concerne l'onglet Taux de Change.
# Elle va maintenir les taux dans st.session_state.fx_rates pour l'affichage dans l'onglet dédié.
current_time = datetime.datetime.now()
# Actualisation si le fichier Excel a changé, la devise cible a changé ou toutes les 60 secondes
if (st.session_state.last_update_time_fx == datetime.datetime.min) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)) or \
   (st.session_state.get("devise_cible") != st.session_state.get("last_devise_cible_for_fx_update", None)) or \
   ((current_time - st.session_state.last_update_time_fx).total_seconds() >= 60):

    # Récupérer la devise cible actuelle pour la mise à jour
    devise_cible_for_update = st.session_state.get("devise_cible", "EUR")
    
    # Récupérer les devises uniques du portefeuille si un DataFrame est chargé
    devises_uniques = []
    if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
        devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
    
    # Appel à la fonction d'actualisation des taux de `taux_change.py`
    # Cela va utiliser st.cache_resource ou st.cache_data en interne
    st.session_state.fx_rates = actualiser_taux_change(devise_cible_for_update, devises_uniques)
    st.session_state.last_update_time_fx = datetime.datetime.now()
    st.session_state.last_devise_cible_for_fx_update = devise_cible_for_update
    
    # Stocke l'ID du fichier traité pour éviter de recharger inutilement
    if st.session_state.get("uploaded_file_id") is not None:
         st.session_state._last_processed_file_id = st.session_state.uploaded_file_id

# --- FIN LOGIQUE D'ACTUALISATION DES TAUX DE CHANGE ---


# --- Structure de l'application principale ---
def main():
    # Sidebar pour l'importation de fichiers et les paramètres
    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("📥 Choisissez un fichier CSV ou Excel", type=["csv", "xlsx"], key="file_uploader")
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
                    st.session_state.last_update_time_fx = datetime.datetime.min # Forcer la mise à jour des taux
                    
                    st.cache_data.clear() # Efface tous les caches de type cache_data (inclut yahoo et momentum)
                    st.cache_resource.clear() # Efface tous les caches de type cache_resource (pour yfinance.ticker.Ticker si utilisé)

                    st.rerun() # Recharger pour appliquer les changements
                except Exception as e:
                    st.error(f"❌ Erreur lors de la lecture du fichier : {e}")
                    st.session_state.df = None
            else:
                st.info("Fichier déjà chargé.")
        elif st.session_state.df is None:
            st.info("Veuillez importer un fichier pour voir les données du portefeuille.")

        st.header("💱 Paramètres de Devise")
        selected_devise = st.selectbox(
            "Devise cible pour l'affichage",
            ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
            index=["EUR", "USD", "GBP", "JPY", "CAD", "CHF"].index(st.session_state.get("devise_cible", "EUR")),
            key="devise_selector"
        )
        if selected_devise != st.session_state.get("devise_cible", "EUR"):
            st.session_state.devise_cible = selected_devise
            # Pas besoin de st.rerun() ici spécifiquement pour la devise, la logique ci-dessus le gère
            # via last_devise_cible_for_fx_update et les caches de data_fetcher.
            st.rerun() # Pour que le changement de devise soit visible immédiatement dans les onglets

    # Onglets horizontaux
    onglets = st.tabs([
        "Portefeuille",
        "Performance",
        "OD Comptables",
        "Transactions",
        "Taux de change",
        "Paramètres"
    ])

    # Onglet : Portefeuille
    with onglets[0]:
        afficher_portefeuille() # La fonction gère l'affichage du portefeuille

    # Onglet : Performance
    with onglets[1]:
        # Appelez votre fonction afficher_performance si elle existe
        if 'afficher_performance' in locals(): # Vérifie si la fonction est importée
            afficher_performance()
        else:
            st.info("Module de performance non trouvé ou fonction non implémentée.")

    # Onglet : OD Comptables
    with onglets[2]:
        # Appelez votre fonction afficher_od_comptables si elle existe
        if 'afficher_od_comptables' in locals():
            afficher_od_comptables()
        else:
            st.info("Module des OD Comptables non trouvé ou fonction non implémentée.")

    # Onglet : Transactions
    with onglets[3]:
        # Appelez votre fonction afficher_transactions si elle existe
        if 'afficher_transactions' in locals():
            afficher_transactions()
        else:
            st.info("Module des transactions non trouvé ou fonction non implémentée.")

    # Onglet : Taux de change
    with onglets[4]:
        # Bouton d'actualisation manuelle pour cet onglet
        if st.button("Actualiser les taux (manuel)", key="manual_fx_refresh_btn"):
            with st.spinner("Mise à jour manuelle des taux de change..."):
                devise_cible_for_manual_update = st.session_state.get("devise_cible", "EUR")
                devises_uniques = []
                if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                    devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
                
                # Re-fetch les taux, le cache sera ignoré si le TTL est passé ou si c'est forcé par clear()
                # On utilise directement la fonction `actualiser_taux_change` de `taux_change.py`
                # pour mettre à jour `st.session_state.fx_rates`.
                st.session_state.fx_rates = actualiser_taux_change(devise_cible_for_manual_update, devises_uniques)
                st.session_state.last_update_time_fx = datetime.datetime.now()
                st.session_state.last_devise_cible_for_fx_update = devise_cible_for_manual_update
                st.success(f"Taux de change actualisés pour {devise_cible_for_manual_update} (manuel).")
                st.rerun() # Recharger toute l'application pour que les changements soient pris en compte

        # Affiche le tableau des taux de change en utilisant les données de session
        # On passe les fx_rates depuis st.session_state.fx_rates
        afficher_tableau_taux_change(st.session_state.get("devise_cible", "EUR"), st.session_state.fx_rates)

    # Onglet : Paramètres
    with onglets[5]:
        # Appelez votre fonction afficher_parametres si elle existe
        if 'afficher_parametres' in locals():
            afficher_parametres()
        else:
            st.info("Module des paramètres non trouvé ou fonction non implémentée.")

    st.markdown("---")
    st.info("💡 Importez un fichier CSV ou Excel pour visualiser et analyser votre portefeuille. Assurez-vous que les colonnes 'Quantité', 'Acquisition', 'Devise' et 'Ticker' (ou 'Tickers') sont présentes pour des calculs optimaux.")

if __name__ == "__main__":
    main()
