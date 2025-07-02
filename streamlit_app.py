import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

# NOUVEL IMPORT : Importez la fonction depuis votre fichier parametres.py
from parametres import afficher_parametres_globaux


# --- Configuration de la page Streamlit ---
st.set_page_config(layout="wide", page_title="Mon Portefeuille d'Investissement")

# --- Initialisation des variables de session ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'devise_cible' not in st.session_state:
    st.session_state.devise_cible = "USD"
# Ces initialisations sont maintenant gérées en grande partie dans afficher_parametres_globaux
# mais une initialisation de base peut rester ici si elles sont utilisées avant l'appel à afficher_parametres_globaux
if 'google_sheets_url_from_input' not in st.session_state: # Clé mise à jour
    st.session_state.google_sheets_url_from_input = ""
if 'last_update_time_fx' not in st.session_state:
    st.session_state.last_update_time_fx = datetime.now(timezone.utc)
if 'fx_rates' not in st.session_state:
    st.session_state.fx_rates = {}
if 'target_volatility' not in st.session_state: # Initialisation de base
    st.session_state.target_volatility = 15.0 / 100.0 # 15% par défaut
if 'target_allocations' not in st.session_state: # Initialisation de base
    st.session_state.target_allocations = {}


# --- Fonctions auxiliaires (REMPLISSEZ AVEC VOTRE CODE RÉEL si elles sont des placeholders) ---

def load_data(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        return df, "success"
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier : {e}")
        return pd.DataFrame(), "error"

def load_portfolio_from_google_sheets(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement depuis Google Sheets ({url}): {e}. Vérifiez l'URL et les permissions.")
        return None

def fetch_current_yahoo_data():
    st.warning("`fetch_current_yahoo_data` est un placeholder. Remplissez avec votre code yfinance.")
    return {}

def fetch_current_momentum_data():
    st.warning("`fetch_current_momentum_data` est un placeholder. Remplissez avec votre code de momentum.")
    return {'momentum_score': {}, 'z_score': {}}

def fetch_current_fx_rates():
    if 'last_update_time_fx' not in st.session_state:
        st.session_state.last_update_time_fx = datetime.now(timezone.utc)
        st.session_state.fx_rates = {}

    current_time = datetime.now(timezone.utc)
    time_diff = (current_time - st.session_state.last_update_time_fx).total_seconds()

    if time_diff > 600 or not st.session_state.get('fx_rates'):
        st.warning("`fetch_current_fx_rates` est un placeholder. Remplissez avec votre code d'API de taux de change.")
        fx_rates = {'EUR/USD': 1.08, 'GBP/USD': 1.27, 'USD/EUR': 1/1.08, 'USD/GBP': 1/1.27}
        st.session_state.fx_rates = fx_rates
        st.session_state.last_update_time_fx = current_time
    else:
        fx_rates = st.session_state.get('fx_rates', {})

    return fx_rates


def convertir(montant, devise_source, devise_cible, fx_rates):
    if devise_source == devise_cible:
        return montant
    
    taux_direct = fx_rates.get(f"{devise_source}/{devise_cible}")
    if taux_direct:
        return montant * taux_direct
    
    taux_inverse = fx_rates.get(f"{devise_cible}/{devise_source}")
    if taux_inverse:
        return montant / taux_inverse
        
    st.warning(f"Taux de change non trouvé pour {devise_source}/{devise_cible}. Conversion non effectuée.")
    return montant

def load_or_reload_portfolio(source_type, uploaded_file=None, google_sheets_url=None):
    df_loaded = None
    if source_type == "fichier" and uploaded_file:
        df_loaded, _ = load_data(uploaded_file)
    elif source_type == "google_sheets" and google_sheets_url:
        df_loaded = load_portfolio_from_google_sheets(google_sheets_url)

    if df_loaded is not None and not df_loaded.empty:
        st.session_state.df = df_loaded
        st.write("DEBUG (SUCCESS): st.session_state.df successfully loaded with columns:", st.session_state.df.columns.tolist())
        st.write("DEBUG (SUCCESS): Is st.session_state.df empty?", st.session_state.df.empty)
    else:
        st.session_state.df = pd.DataFrame()
        st.error("DEBUG (ERROR): Failed to load portfolio data or DataFrame is empty. Check your data source (Google Sheets URL/file content).")

def display_portfolio_details(df_processed_portfolio, currency_target="USD"):
    st.subheader("Résumé Détaillé du Portefeuille")

    if df_processed_portfolio.empty:
        st.warning("Aucune donnée de portefeuille à afficher pour le moment.")
        return

    st.dataframe(df_processed_portfolio, use_container_width=True)

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    valeur_totale_actuelle = 0
    profit_perte = 0
    if 'Quantité' in df_processed_portfolio.columns and 'Prix Actuel' in df_processed_portfolio.columns:
        valeur_totale_actuelle = (df_processed_portfolio['Quantité'] * df_processed_portfolio['Prix Actuel']).sum()
        col1.metric("Valeur Totale Actuelle", f"{valeur_totale_actuelle:,.2f} {currency_target}")

    if 'Acquisition (Devise Cible)' in df_processed_portfolio.columns and 'Quantité' in df_processed_portfolio.columns and 'Prix Actuel' in df_processed_portfolio.columns:
        cout_acquisition_total = df_processed_portfolio['Acquisition (Devise Cible)'].sum()
        valeur_actuelle_total_devise_cible = (df_processed_portfolio['Quantité'] * df_processed_portfolio['Prix Actuel']).sum()
        profit_perte = valeur_actuelle_total_devise_cible - cout_acquisition_total
        col2.metric("Profit/Perte", f"{profit_perte:,.2f} {currency_target}", delta=f"{profit_perte:,.2f} {currency_target}")

    col3.metric("Nombre de Titres", len(df_processed_portfolio))
    col4.metric("Autre KPI", "N/A")

    st.markdown("---")

    st.subheader("Visualisations du Portefeuille")

    if 'Catégorie' in df_processed_portfolio.columns and 'Valeur Actuelle' in df_processed_portfolio.columns:
        df_grouped_by_category = df_processed_portfolio.groupby('Catégorie')['Valeur Actuelle'].sum().reset_index()
        fig_pie = px.pie(df_grouped_by_category, values='Valeur Actuelle', names='Catégorie', title='Répartition du portefeuille par catégorie')
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Ajoutez des colonnes 'Catégorie' et 'Valeur Actuelle' pour le graphique de répartition.")

    st.info("Ajoutez ici vos graphiques spécifiques : performance par titre, répartition sectorielle, évolution historique, etc.")


# --- Interface utilisateur (Tabs) ---
tab1, tab2, tab3 = st.tabs(["Accueil", "Analyse du Portefeuille", "Paramètres"])

with tab1:
    st.header("Tableau de bord du Portefeuille")

    if st.session_state.df.empty:
        st.info("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets.")

    # --- Traitement des données et affichage ---
    if not st.session_state.df.empty:
        current_prices = fetch_current_yahoo_data()
        momentum_data = fetch_current_momentum_data()
        fx_rates = fetch_current_fx_rates()

        df_portfolio = st.session_state.df.copy()

        if isinstance(df_portfolio, pd.DataFrame) and not df_portfolio.empty:
            st.write("DEBUG (PROCESSING): Columns in df_portfolio before mapping:", df_portfolio.columns.tolist())
        else:
            st.write("DEBUG (PROCESSING): df_portfolio is empty or not a DataFrame AFTER COPYING from session_state.")

        if 'Ticker' in df_portfolio.columns:
            df_portfolio['Prix Actuel'] = df_portfolio['Ticker'].map(current_prices)
            df_portfolio['Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('momentum_score', {}))
            df_portfolio['Z_Momentum'] = df_portfolio['Ticker'].map(momentum_data.get('z_score', {}))

            if 'Acquisition' in df_portfolio.columns and 'Devise' in df_portfolio.columns:
                df_portfolio['Acquisition (Devise Cible)'] = df_portfolio.apply(
                    lambda row: convertir(row['Acquisition'], row['Devise'], st.session_state.devise_cible, fx_rates),
                    axis=1
                )
                if 'Prix Actuel' in df_portfolio.columns and 'Quantité' in df_portfolio.columns:
                    df_portfolio['Valeur Actuelle'] = df_portfolio['Quantité'] * df_portfolio['Prix Actuel']
                else:
                    st.warning("Colonnes 'Prix Actuel' ou 'Quantité' manquantes pour calculer 'Valeur Actuelle'.")
                    df_portfolio['Valeur Actuelle'] = 0
            else:
                st.warning("Colonnes 'Acquisition' ou 'Devise' manquantes pour la conversion.")
                df_portfolio['Acquisition (Devise Cible)'] = df_portfolio['Acquisition']
                df_portfolio['Valeur Actuelle'] = 0

            display_portfolio_details(df_portfolio, currency_target=st.session_state.devise_cible)

        else:
            st.error("La colonne 'Ticker' est introuvable dans votre DataFrame chargé. Veuillez vérifier votre source de données.")


with tab2:
    st.header("Analyse Détaillée du Portefeuille")
    if not st.session_state.df.empty:
        st.write("Contenu de l'analyse détaillée...")
    else:
        st.info("Chargement du portefeuille nécessaire pour l'analyse.")


with tab3:
    # >>> APPEL DE LA FONCTION DES PARAMÈTRES EXTERNE <<<
    # Cette fonction gère maintenant toute la logique de chargement de fichier/Google Sheets,
    # ainsi que les autres paramètres.
    afficher_parametres_globaux(load_or_reload_portfolio)
    # >>> FIN DE L'APPEL <<<
