# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay # Pour les jours ouvrables
import yfinance as yf
import builtins # Pour contourner l'écrasement de str()

# Import des fonctions nécessaires
from historical_data_fetcher import fetch_stock_history, get_all_historical_data
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr

def display_performance_history():
    """
    Affiche la performance historique du portefeuille basée sur sa composition actuelle,
    et un tableau des derniers cours de clôture pour tous les tickers, avec sélection de plage de dates.
    """
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        return

    df_current_portfolio = st.session_state.df.copy()
    target_currency = st.session_state.get("devise_cible", "EUR")

    tickers_in_portfolio = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers_in_portfolio = sorted(st.session_state.df['Ticker'].dropna().unique().tolist())

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE PAR BOUTONS STYLISÉS EN HTML/CSS/JS INLINE ---

    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
    }

    if "selected_ticker_table_period" not in st.session_state:
        st.session_state.selected_ticker_table_period = "1W"

    # CSS pour styliser les "boutons-texte" et leur conteneur
    # et pour cacher le conteneur des boutons Streamlit natifs
    st.markdown("""
        <style>
        /* Conteneur spécifique pour les éléments de période */
        .period-buttons-wrapper {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-start;
            gap: 5px; /* Espacement de 5px entre les éléments */
            margin-bottom: 1rem;
        }

        /* Style de chaque élément de période (le texte cliquable) */
        .period-item {
            /* Réinitialise les styles par défaut qui pourraient être hérités */
            background: none;
            border: none;
            padding: 0; /* Pas de padding pour coller au texte */
            font-size: 1rem; /* Taille de police par défaut */
            color: inherit; /* Hérite la couleur du texte parent (thème Streamlit) */
            cursor: pointer; /* Indique que l'élément est cliquable */
            text-decoration: none; /* Supprime le soulignement par défaut */
            box-shadow: none; /* Supprime l'ombre par défaut */
            display: inline-block; /* Permet d'appliquer padding/margin si nécessaire */
            line-height: 1; /* Ajuste la hauteur de ligne si besoin */
            white-space: nowrap; /* Empêche le texte de s'enrouler */
            -webkit-tap-highlight-color: transparent; /* Supprime l'effet de surbrillance au toucher sur mobile */
        }

        /* Style au survol (hover) */
        .period-item:hover {
            text-decoration: none !important; /* Pas de soulignement au survol */
            color: var(--primary-color) !important; /* Couleur au survol (peut être ajustée) */
        }

        /* Style de l'élément sélectionné */
        .period-item.selected {
            font-weight: bold !important; /* Texte en gras */
            color: var(--secondary-color) !important; /* Utilise la couleur secondaire définie dans le thème Streamlit */
            text-decoration: none !important; /* Pas de soulignement pour l'élément sélectionné */
        }

        /* Cache le conteneur des boutons Streamlit natifs */
        div[data-testid="stVerticalBlock"] > div > div > button[data-testid^="stButton-hidden_period_btn_"] {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("#### Sélection de la période d'affichage des cours")
    
    # Génération du HTML pour les éléments de période et des boutons Streamlit cachés
    period_items_html = '<div class="period-buttons-wrapper">'
    for label in period_options:
        is_selected = (st.session_state.selected_ticker_table_period == label)
        
        # Chaque élément span aura un ID unique pour que le JS puisse le cibler
        period_items_html += f"""
        <span id="period_item_{label}" class="period-item {'selected' if is_selected else ''}">
            {label}
        </span>
        """
    period_items_html += '</div>'
    
    st.markdown(period_items_html, unsafe_allow_html=True)

    # Créer les boutons Streamlit cachés qui seront cliqués par le JavaScript
    # Ces boutons mettront à jour la session_state et déclencheront un rerun.
    # Utilisation d'un st.container() pour les regrouper et les cacher plus facilement
    # Le data-testid du container sera utilisé pour le CSS de masquage
    hidden_buttons_container = st.container()
    with hidden_buttons_container:
        for label in period_options:
            # Utilisez une clé unique pour chaque bouton
            if st.button(label, key=f"hidden_period_btn_{label}", help=f"Sélectionner {label}"):
                st.session_state.selected_ticker_table_period = label
                st.rerun()
    
    # JavaScript pour attacher les écouteurs d'événements aux spans
    # et simuler un clic sur le bouton Streamlit caché correspondant.
    # Le script est enveloppé dans DOMContentLoaded pour s'assurer que tous les éléments sont chargés.
    js_code = """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const periodLabels = %s; // Pass period labels from Python
            periodLabels.forEach(label => {
                const span = document.getElementById(`period_item_${label}`);
                if (span) {
                    span.onclick = function() {
                        // Trouver le bouton Streamlit caché par son data-testid
                        // Le data-testid est généré par Streamlit sous la forme "stButton-<key>"
                        const hiddenButton = document.querySelector(`button[data-testid="stButton-hidden_period_btn_${label}"]`);
                        if (hiddenButton) {
                            hiddenButton.click(); // Simule un clic sur le bouton caché
                        } else {
                            console.warn(`Bouton caché pour ${label} non trouvé.`);
                        }
                    };
                } else {
                    console.warn(`Span pour ${label} non trouvé.`);
                }
            });
        });
    </script>
    """ % (list(period_options.keys())) # Passer la liste des clés Python au JavaScript

    st.markdown(js_code, unsafe_allow_html=True)

    # --- FIN SÉLECTION DE PÉRIODE ---

    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td

    st.info(f"Affichage des cours de clôture pour les tickers du portefeuille sur la période : {start_date_table.strftime('%d/%m/%Y')} à {end_date_table.strftime('%d/%m/%Y')}.")

    with st.spinner("Récupération des cours des tickers en cours..."):
        last_days_data = {}
        fetch_start_date = start_date_table - timedelta(days=10) 
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                last_days_data[ticker] = filtered_data
            else:
                last_days_data[ticker] = pd.Series(dtype='float64') 

        df_display_prices = pd.DataFrame()
        for ticker, series in last_days_data.items():
            if not series.empty:
                temp_df = pd.DataFrame(series.rename("Cours").reset_index())
                temp_df.columns = ["Date", "Cours"]
                temp_df["Ticker"] = ticker
                df_display_prices = pd.concat([df_display_prices, temp_df])

        if not df_display_prices.empty:
            df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours")
            df_pivot = df_pivot.sort_index(axis=1)
            
            df_pivot = df_pivot.loc[:, (df_pivot.columns >= pd.Timestamp(start_date_table)) & (df_pivot.columns <= pd.Timestamp(end_date_table))]

            df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]
            
            st.markdown("##### Cours de Clôture des Derniers Jours")
            st.dataframe(df_pivot.style.format(format_fr), use_container_width=True)
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")
