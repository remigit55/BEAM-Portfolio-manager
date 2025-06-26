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

    # --- SÉLECTION DE PÉRIODE PAR TEXTE CLIQUABLE ---

    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
    }

    # Lire la période sélectionnée depuis les query parameters de l'URL
    # Si 'period' est dans les query params, l'utiliser, sinon utiliser '1W' par défaut
    query_period = st.query_params.get("period", ["1W"])[0]
    if query_period in period_options:
        st.session_state.selected_ticker_table_period = query_period
    else:
        st.session_state.selected_ticker_table_period = "1W" # Fallback si le paramètre est invalide

    st.markdown("""
        <style>
        .period-links-container {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-start;
            gap: 5px; /* Espacement de 5px entre les éléments cliquables */
            margin-bottom: 1rem;
        }
        .period-links-container a {
            text-decoration: none; /* Supprime le soulignement par défaut des liens */
            color: inherit; /* Utilise la couleur du texte parent */
            padding: 5px 0; /* Ajoute un peu de padding pour une meilleure zone de clic */
            cursor: pointer;
        }
        .period-links-container a:hover {
            text-decoration: underline; /* Souligne au survol pour indiquer la cliquabilité */
            color: var(--primary-color); /* Change la couleur au survol si désiré */
        }
        .period-links-container a.selected {
            font-weight: bold;
            color: var(--secondary-color); /* Couleur pour l'élément sélectionné */
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("#### Sélection de la période d'affichage des cours")
    st.markdown('<div class="period-links-container">', unsafe_allow_html=True)
    
    # Générer les liens cliquables
    for label in period_options:
        is_selected = (st.session_state.selected_ticker_table_period == label)
        # Créer l'URL avec le nouveau paramètre de période
        # st.experimental_set_query_params est déprécié, utiliser st.query_params directement
        current_query_params = st.query_params.to_dict()
        current_query_params['period'] = label
        
        # Construire l'URL avec les nouveaux paramètres de requête
        # st.experimental_get_query_params() est remplacé par st.query_params
        # et st.experimental_set_query_params() n'est plus utilisé pour le lien direct
        # Le lien est généré pour que le navigateur le suive, ce qui déclenche un rerun.
        query_string = "&".join([f"{k}={v}" for k, v_list in current_query_params.items() for v in (v_list if isinstance(v_list, list) else [v_list])])
        link_href = f"?{query_string}"
        
        # Appliquer la classe 'selected' si c'est la période active
        selected_class = "selected" if is_selected else ""
        
        st.markdown(f'<a href="{link_href}" class="{selected_class}">{label}</a>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

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
