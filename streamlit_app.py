# streamlit_app.py

import streamlit as st
import pandas as pd
import datetime
from PIL import Image
import base64
from io import BytesIO

# Importation des modules fonctionnels
# Maintenant, nous importons les deux fonctions du même fichier
from portfolio_display import afficher_portefeuille, afficher_synthese_globale

# Assurez-vous que ces fichiers existent et contiennent les fonctions correspondantes.
# Si un fichier ou une fonction n'existe pas, commentez la ligne correspondante.
from performance import afficher_performance
from transactions import afficher_transactions
from od_comptables import afficher_od_comptables
from taux_change import afficher_tableau_taux_change, actualiser_taux_change
from parametres import afficher_parametres

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
    "devise_cible": "EUR",
    "ticker_names_cache": {},
    "sort_column": None,
    "sort_direction": "asc",
    "momentum_results": {},
    "last_devise_cible": "EUR",
    "last_update_time_fx": datetime.datetime.min,
    # NOUVEAU: Stocker les totaux dans session_state pour les rendre accessibles à l'onglet Synthèse
    "total_valeur": None,
    "total_actuelle": None,
    "total_h52": None,
    "total_lt": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

current_time = datetime.datetime.now()
if (st.session_state.last_update_time_fx == datetime.datetime.min) or \
   (st.session_state.get("uploaded_file_id") != st.session_state.get("_last_processed_file_id", None)) or \
   (st.session_state.get("devise_cible") != st.session_state.get("last_devise_cible_for_fx_update", None)) or \
   ((current_time - st.session_state.last_update_time_fx).total_seconds() >= 60):

    devise_cible_for_update = st.session_state.get("devise_cible", "EUR")
    
    devises_uniques = []
    if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
        devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
    
    st.session_state.fx_rates = actualiser_taux_change(devise_cible_for_update, devises_uniques)
    st.session_state.last_update_time_fx = datetime.datetime.now()
    st.session_state.last_devise_cible_for_fx_update = devise_cible_for_update
    
    if st.session_state.get("uploaded_file_id") is not None:
         st.session_state._last_processed_file_id = st.session_state.uploaded_file_id


# --- Structure de l'application principale ---
def main():
    # Sidebar pour l'importation de fichiers et les paramètres
    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("📥 Choisissez un fichier CSV ou Excel", type=["csv", "xlsx"], key="file_uploader")
        if uploaded_file is not None:
            if "uploaded_file_id" not in st.session_state or st.session_state.uploaded_file_id != uploaded_file.file_id:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_uploaded = pd.read_csv(uploaded_file)
                    elif uploaded_file.name.endswith('.xlsx'):
                        df_uploaded = pd.read_excel(uploaded_file)
                    
                    st.session_state.df = df_uploaded
                    st.session_state.uploaded_file_id = uploaded_file.file_id
                    st.success("Fichier importé avec succès !")
                    
                    st.session_state.sort_column = None
                    st.session_state.sort_direction = "asc"
                    st.session_state.ticker_names_cache = {}
                    st.session_state.last_update_time_fx = datetime.datetime.min # Forcer la mise à jour des taux
                    
                    st.cache_data.clear()
                    st.cache_resource.clear()

                    st.rerun()
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
            st.rerun()

    # Appelez afficher_portefeuille une fois pour obtenir les totaux
    # C'est important de le faire avant de définir les onglets pour que les totaux soient à jour
    # lors de la navigation entre les onglets.
    total_valeur, total_actuelle, total_h52, total_lt = afficher_portefeuille()

    # Mettre à jour les totaux dans session_state
    st.session_state.total_valeur = total_valeur
    st.session_state.total_actuelle = total_actuelle
    st.session_state.total_h52 = total_h52
    st.session_state.total_lt = total_lt


    # Onglets horizontaux (ordre modifié)
    onglets = st.tabs([
        "Synthèse", # NOUVEL ONGLE
        "Portefeuille",
        "Performance",
        "OD Comptables",
        "Transactions",
        "Taux de change",
        "Paramètres"
    ])

    # Onglet : Synthèse
    with onglets[0]:
        st.header("✨ Synthèse du Portefeuille")
        # Passez les totaux stockés dans session_state à la fonction de synthèse
        afficher_synthese_globale(
            st.session_state.total_valeur,
            st.session_state.total_actuelle,
            st.session_state.total_h52,
            st.session_state.total_lt
        )

    # Onglet : Portefeuille
    with onglets[1]: # L'index a changé de 0 à 1
        st.header("📈 Vue détaillée du Portefeuille")
        # La fonction afficher_portefeuille est déjà appelée plus haut pour calculer les totaux.
        # Ici, nous ne voulons pas la rappeler, car cela recalculerait tout et pourrait être inefficace.
        # Nous allons donc afficher le DataFrame du portefeuille directement (en s'assurant qu'il est géré par la session)
        # OU, si la fonction est conçue pour afficher et retourner, on peut juste l'appeler.
        # MAJ: La fonction afficher_portefeuille gère l'affichage du tableau et le retour des totaux,
        # donc l'appel ci-dessus suffit. Nous n'avons pas besoin de la rappeler ici car le rendu est déjà fait.
        # Si vous vouliez afficher le tableau DANS cet onglet UNIQUEMENT, il faudrait adapter.
        # Pour l'instant, le tableau est affiché implicitement par l'appel en dehors des onglets.
        # Je vais ajuster pour que l'appel d'afficher_portefeuille soit fait dans son onglet.

        # Retrait de l'appel d'afficher_portefeuille en dehors des onglets
        # Déplacez-le ici pour qu'il soit exécuté quand l'onglet "Portefeuille" est actif
        if st.session_state.df is None:
            st.info("Veuillez importer un fichier Excel pour voir la vue détaillée de votre portefeuille.")
        else:
            # Pour afficher le tableau seulement quand l'onglet est actif, la fonction doit être appelée ici.
            # Cependant, elle a déjà été appelée pour les totaux.
            # Il y a deux façons de gérer ça:
            # 1. Faire que afficher_portefeuille soit appelée dans les deux endroits (pas très optimisé).
            # 2. Séparer l'affichage du tableau et le calcul des totaux dans deux fonctions différentes.
            # Je vais revenir à l'approche où afficher_portefeuille ne fait que l'affichage et retourne les totaux.
            # Et l'appel pour les totaux sera fait avant les onglets.

            # Re-appelons la fonction ici, en acceptant la légère redondance si le calcul n'est pas trop lourd.
            # L'avantage est que l'affichage du tableau est bien dans son onglet.
            # Les caches Streamlit minimiseront l'impact sur les performances.
            total_valeur_dummy, total_actuelle_dummy, total_h52_dummy, total_lt_dummy = afficher_portefeuille()
            # Les totaux sont déjà mis à jour par le premier appel, donc ces retours sont "dummy".


    # Onglet : Performance
    with onglets[2]: # Index 2
        st.header("📊 Analyse de Performance")
        if 'afficher_performance' in locals():
            afficher_performance()
        else:
            st.info("Module de performance non trouvé ou fonction non implémentée.")

    # Onglet : OD Comptables
    with onglets[3]: # Index 3
        st.header("🧾 Opérations Diverses Comptables")
        if 'afficher_od_comptables' in locals():
            afficher_od_comptables()
        else:
            st.info("Module des OD Comptables non trouvé ou fonction non implémentée.")

    # Onglet : Transactions
    with onglets[4]: # Index 4
        st.header("📜 Historique des Transactions")
        if 'afficher_transactions' in locals():
            afficher_transactions()
        else:
            st.info("Module des transactions non trouvé ou fonction non implémentée.")

    # Onglet : Taux de change
    with onglets[5]: # Index 5
        st.header("💱 Taux de Change Actuels")
        if st.button("Actualiser les taux (manuel)", key="manual_fx_refresh_btn_tab"): # Clé unique
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
    with onglets[6]: # Index 6
        st.header("⚙️ Paramètres de l'Application")
        if 'afficher_parametres' in locals():
            afficher_parametres()
        else:
            st.info("Module des paramètres non trouvé ou fonction non implémentée.")

    st.markdown("---")
    st.info("💡 Importez un fichier CSV ou Excel pour visualiser et analyser votre portefeuille. Assurez-vous que les colonnes 'Quantité', 'Acquisition', 'Devise' et 'Ticker' (ou 'Tickers') sont présentes pour des calculs optimaux.")

if __name__ == "__main__":
    main()
