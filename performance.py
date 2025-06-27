# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import builtins

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

    # --- SÉLECTION DE PÉRIODE PAR BOUTONS STYLISÉS DANS ST.COLUMNS ---

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

    st.markdown("""
        <style>
        /* Cible le conteneur principal de toutes les colonnes généré par st.columns */
        div[data-testid="stColumns"] {
            gap: 5px; /* Espacement de 5px entre chaque colonne */
            /* Si vous voulez contrôler la largeur totale de cette rangée de colonnes: */
            width: 100px; /* La largeur s'adapte au contenu des colonnes */
            /* ou une largeur fixe: */
            /* width: 400px; */
            /* ou une largeur maximale: */
            /* max-width: 600px; */
            margin-bottom: 1rem; /* Marge en bas pour séparer du contenu suivant */
        }

        /* Cible chaque colonne individuelle générée par st.columns */
        div[data-testid^="stColumn"] {
            padding: 0 !important; /* Supprime le padding interne par défaut de chaque colonne */
            margin: 0 !important; /* Supprime la marge externe par défaut de chaque colonne */
            flex-grow: 0 !important; /* Empêche les colonnes de prendre plus d'espace qu'elles n'en ont besoin */
            width: fit-content; /* Chaque colonne s'adapte à la largeur de son contenu (le bouton) */ 
            /*width: 100px;  Chaque colonne s'adapte à la largeur de son contenu (le bouton) */
        }

        /* Cible le conteneur Streamlit de chaque bouton (le div autour du <button>) */
        div.stButton {
            /*margin: 0 !important;*/ /* Supprime les marges par défaut de Streamlit autour du bouton */
            height: auto; /* Ajuste la hauteur à son contenu */
            width: 100%;
        }
        
        /* Style du bouton lui-même pour qu'il ressemble à du texte cliquable */
        div.stButton > button {
            background: none !important; /* Pas de fond */
             /*border: none !important;*/ /* Pas de bordure */
            padding: 0 !important; /* Pas de padding interne */
            font-size: 1rem; /* Taille de police par défaut */
            color: inherit !important; /* Utilise la couleur du texte parent */
            cursor: pointer;
            text-decoration: none !important; /* Pas de soulignement */
            box-shadow: none !important; /* Pas d'ombre */
        }
        /* Style au survol */
        div.stButton > button:hover {
            text-decoration: none !important; /* Pas de soulignement au survol */
            color: var(--primary-color) !important; /* Couleur au survol (peut être ajustée) */
        }
        /* Style du bouton sélectionné */
        div.stButton > button.selected {
            font-weight: bold !important;
            color: var(--secondary-color) !important; /* Utilise la couleur secondaire définie dans le thème Streamlit */
            text-decoration: none !important; /* Pas de soulignement pour l'élément sélectionné */
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("#### Sélection de la période d'affichage des cours")
    
    # Utilisation de st.columns pour créer les colonnes pour chaque bouton
    # Il n'est pas nécessaire de passer des ratios si vous voulez qu'elles s'adaptent au contenu.
    cols = st.columns(len(period_options)) 
    
    for i, label in enumerate(period_options):
        with cols[i]: # Place chaque bouton dans sa propre colonne
            # Toujours créer un bouton et ajouter la classe 'selected' via JavaScript
            if st.button(label, key=f"period_{label}"):
                st.session_state.selected_ticker_table_period = label
                st.rerun()
            
            # Injecter du JavaScript pour ajouter la classe 'selected' au bouton actif
            if st.session_state.selected_ticker_table_period == label:
                st.markdown(f"""
                    <script>
                        const button = document.querySelector('button[data-testid="stButton-period_{label}"]');
                        if (button) {{
                            button.classList.add('selected');
                        }}
                    </script>
                """, unsafe_allow_html=True)

    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td
    
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
