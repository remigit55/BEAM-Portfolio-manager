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
    # today = datetime.now().date() # Supprimé
    # default_start_date_perf = today - timedelta(days=365) # Par défaut : 1 an d'historique # Supprimé
    
    # col1_perf, col2_perf = st.columns(2) # Supprimé
    # with col1_perf: # Supprimé
    #     start_date_perf = st.date_input("Date de début (Performance Portefeuille)", value=default_start_date_perf, key="perf_start_date") # Supprimé
    # with col2_perf: # Supprimé
    #     end_date_perf = st.date_input("Date de fin (Performance Portefeuille)", value=today, key="perf_end_date") # Supprimé

    # if start_date_perf >= end_date_perf: # Supprimé
    #     st.error("La date de début doit être antérieure à la date de fin pour la performance du portefeuille.") # Supprimé
    #     return # Supprimé

    # if st.button("Calculer Performance Historique du Portefeuille", key="calculate_portfolio_perf_btn"): # Supprimé
    #     with st.spinner("Calcul de la performance historique du portefeuille en cours... Cela peut prendre un moment si la période est longue et si de nombreuses données doivent être téléchargées."): # Supprimé
    #         df_historical_values = reconstruct_historical_portfolio_value( # Supprimé
    #             df_current_portfolio, start_date_perf, end_date_perf, target_currency # Utilisation des nouvelles dates # Supprimé
    #         ) # Supprimé

    #         if not df_historical_values.empty: # Supprimé
    #             st.success("Performance historique du portefeuille calculée avec succès !") # Supprimé
                
    #             # Affichage des statistiques de base sur la période # Supprimé
    #             st.markdown("##### Aperçu de la Performance") # Supprimé
    #             first_date_val = df_historical_values.iloc[0] # Supprimé
    #             last_date_val = df_historical_values.iloc[-1] # Supprimé
                
    #             initial_value = first_date_val["Valeur Actuelle"] # Supprimé
    #             final_value = last_date_val["Valeur Actuelle"] # Supprimé
    #             absolute_gain = final_value - initial_value # Supprimé
                
    #             percentage_gain = (absolute_gain / initial_value) * 100 if initial_value != 0 else 0 # Supprimé

    #             st.metric( # Supprimé
    #                 label=f"Valeur Initiale ({first_date_val['Date'].strftime('%d/%m/%Y')})", # Supprimé
    #                 value=f"{format_fr(initial_value)} {target_currency}" # Supprimé
    #             ) # Supprimé
    #             st.metric( # Supprimé
    #                 label=f"Valeur Finale ({last_date_val['Date'].strftime('%d/%m/%Y')})", # Supprimé
    #                 value=f"{format_fr(final_value)} {target_currency}" # Supprimé
    #             ) # Supprimé
    #             st.metric( # Supprimé
    #                 label="Gain/Perte Absolu sur la période", # Supprimé
    #                 value=f"{format_fr(absolute_gain)} {target_currency}", # Supprimé
    #                 delta=f"{format_fr(percentage_gain)} %" # Supprimé
    #             ) # Supprimé

    #             # Graphique de l'évolution du portefeuille # Supprimé
    #             st.markdown("##### Évolution de la Valeur du Portefeuille") # Supprimé
    #             fig = px.line( # Supprimé
    #                 df_historical_values, # Supprimé
    #                 x="Date", # Supprimé
    #                 y=["Valeur Actuelle", "Valeur Acquisition"], # Supprimé
    #                 title=f"Évolution de la Valeur du Portefeuille ({target_currency})", # Supprimé
    #                 labels={"value": "Valeur", "variable": "Type de Valeur"}, # Supprimé
    #                 hover_data={ # Supprimé
    #                     "Valeur Acquisition": ':.2f', # Supprimé
    #                     "Valeur Actuelle": ':.2f', # Supprimé
    #                     "Gain/Perte Absolu": ':.2f', # Supprimé
    #                     "Gain/Perte (%)": ':.2f' # Supprimé
    #                 } # Supprimé
    #             ) # Supprimé
    #             fig.update_layout(hovermode="x unified") # Supprimé
    #             st.plotly_chart(fig, use_container_width=True) # Supprimé

    #             # Affichage du détail des valeurs quotidiennes dans un tableau # Supprimé
    #             st.markdown("##### Détail des Valeurs Quotidiennes") # Supprimé
    #             st.dataframe(df_historical_values.round(2).style.format({ # Supprimé
    #                 "Valeur Acquisition": lambda x: f"{format_fr(x)} {target_currency}", # Supprimé
    #                 "Valeur Actuelle": lambda x: f"{format_fr(x)} {target_currency}", # Supprimé
    #                 "Gain/Perte Absolu": lambda x: f"{format_fr(x)} {target_currency}", # Supprimé
    #                 "Gain/Perte (%)": lambda x: f"{format_fr(x)} %" # Supprimé
    #             }), use_container_width=True) # Supprimé

    #         else: # Supprimé
    #             st.warning("Aucune donnée historique n'a pu être calculée pour la période et le portefeuille sélectionnés. Vérifiez les dates, la présence de tickers valides et votre connexion internet.") # Supprimé

    # st.markdown("---") # Supprimé

    # Section pour le tableau des derniers cours de clôture par ticker
    st.subheader("Derniers Cours de Clôture par Ticker")

    tickers_in_portfolio = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers_in_portfolio = sorted(st.session_state.df['Ticker'].dropna().unique().tolist())

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE PAR BOUTONS POUR LE TABLEAU DES COURS ---
    period_options = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),  # Environ 1 mois
        "3M": timedelta(days=90),  # Environ 3 mois
        "6M": timedelta(days=180), # Environ 6 mois
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
        "                                                                ": timedelta(days=365 * 10),
    }

    if 'selected_ticker_table_period' not in st.session_state:
        st.session_state.selected_ticker_table_period = "1W" # Période par défaut

    st.markdown("Sélectionnez une période pour les cours des tickers :")
    
    # Utilisation de st.columns pour placer les boutons côte à côte
    cols_period_buttons = st.columns(len(period_options))
    for i, (label, period_td) in enumerate(period_options.items()):
        with cols_period_buttons[i]:
            if st.button(label, key=f"period_btn_{label}"):
                st.session_state.selected_ticker_table_period = label
                st.rerun() 

    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td

    # st.info(f"Affichage des cours de clôture pour les tickers du portefeuille sur la période : {start_date_table.strftime('%d/%m/%Y')} à {end_date_table.strftime('%d/%m/%Y')}.")

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
