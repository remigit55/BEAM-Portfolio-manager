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
    st.subheader("Performance Historique du Portefeuille")

    # Vérifier si le portefeuille est chargé
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        return

    df_current_portfolio = st.session_state.df.copy()
    target_currency = st.session_state.get("devise_cible", "EUR")

    st.markdown(f"**Calcul de la performance pour la composition actuelle du portefeuille (sans parité des changes).**")

    # Section pour le calcul et l'affichage de la performance globale du portefeuille
    st.markdown("#### Évolution de la Valeur Totale du Portefeuille")
    
    # --- NOUVEAU : SÉLECTION DE LA PLAGE DE DATES POUR LA PERFORMANCE GLOBALE ---
    today = datetime.now().date()
    default_start_date_perf = today - timedelta(days=365) # Par défaut : 1 an d'historique
    
    col1_perf, col2_perf = st.columns(2)
    with col1_perf:
        start_date_perf = st.date_input("Date de début (Performance Portefeuille)", value=default_start_date_perf, key="perf_start_date")
    with col2_perf:
        end_date_perf = st.date_input("Date de fin (Performance Portefeuille)", value=today, key="perf_end_date")

    if start_date_perf >= end_date_perf:
        st.error("La date de début doit être antérieure à la date de fin pour la performance du portefeuille.")
        return

    if st.button("Calculer Performance Historique du Portefeuille", key="calculate_portfolio_perf_btn"):
        with st.spinner("Calcul de la performance historique du portefeuille en cours... Cela peut prendre un moment si la période est longue et si de nombreuses données doivent être téléchargées."):
            df_historical_values = reconstruct_historical_portfolio_value(
                df_current_portfolio, start_date_perf, end_date_perf, target_currency # Utilisation des nouvelles dates
            )

            if not df_historical_values.empty:
                st.success("Performance historique du portefeuille calculée avec succès !")
                
                # Affichage des statistiques de base sur la période
                st.markdown("##### Aperçu de la Performance")
                first_date_val = df_historical_values.iloc[0]
                last_date_val = df_historical_values.iloc[-1]
                
                initial_value = first_date_val["Valeur Actuelle"]
                final_value = last_date_val["Valeur Actuelle"]
                absolute_gain = final_value - initial_value
                
                percentage_gain = (absolute_gain / initial_value) * 100 if initial_value != 0 else 0

                st.metric(
                    label=f"Valeur Initiale ({first_date_val['Date'].strftime('%d/%m/%Y')})",
                    value=f"{format_fr(initial_value)} {target_currency}"
                )
                st.metric(
                    label=f"Valeur Finale ({last_date_val['Date'].strftime('%d/%m/%Y')})",
                    value=f"{format_fr(final_value)} {target_currency}"
                )
                st.metric(
                    label="Gain/Perte Absolu sur la période",
                    value=f"{format_fr(absolute_gain)} {target_currency}",
                    delta=f"{format_fr(percentage_gain)} %"
                )

                # Graphique de l'évolution du portefeuille
                st.markdown("##### Évolution de la Valeur du Portefeuille")
                fig = px.line(
                    df_historical_values,
                    x="Date",
                    y=["Valeur Actuelle", "Valeur Acquisition"],
                    title=f"Évolution de la Valeur du Portefeuille ({target_currency})",
                    labels={"value": "Valeur", "variable": "Type de Valeur"},
                    hover_data={
                        "Valeur Acquisition": ':.2f', 
                        "Valeur Actuelle": ':.2f', 
                        "Gain/Perte Absolu": ':.2f', 
                        "Gain/Perte (%)": ':.2f'
                    }
                )
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                # Affichage du détail des valeurs quotidiennes dans un tableau
                st.markdown("##### Détail des Valeurs Quotidiennes")
                st.dataframe(df_historical_values.round(2).style.format({
                    "Valeur Acquisition": lambda x: f"{format_fr(x)} {target_currency}",
                    "Valeur Actuelle": lambda x: f"{format_fr(x)} {target_currency}",
                    "Gain/Perte Absolu": lambda x: f"{format_fr(x)} {target_currency}",
                    "Gain/Perte (%)": lambda x: f"{format_fr(x)} %"
                }), use_container_width=True)

            else:
                st.warning("Aucune donnée historique n'a pu être calculée pour la période et le portefeuille sélectionnés. Vérifiez les dates, la présence de tickers valides et votre connexion internet.")

    st.markdown("---")

    # Section pour le tableau des derniers cours de clôture par ticker
    st.subheader("Derniers Cours de Clôture par Ticker")

    tickers_in_portfolio = []
    if "df" in st.session_state and st.session_state.df is not None and "Ticker" in st.session_state.df.columns:
        tickers_in_portfolio = sorted(st.session_state.df['Ticker'].dropna().unique().tolist())

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- NOUVEAU : SÉLECTION DU NOMBRE DE JOURS POUR LE TABLEAU DES DERNIERS COURS ---
    days_range_5_days_table = st.slider(
        "Nombre de jours d'historique pour les derniers cours", 
        min_value=1, 
        max_value=3650, # Limité à 3650 jours pour la lisibilité du tableau
        value=5, 
        key="days_range_5_days_table"
    )

    end_date_5days = datetime.now().date()
    # Récupérer les 'days_range_5_days_table' derniers jours ouvrables
    business_days_table = pd.bdate_range(end=end_date_5days, periods=days_range_5_days_table)
    start_date_5days_table = business_days_table[0].date()


    st.info(f"Affichage des cours de clôture pour les tickers du portefeuille sur la période : {start_date_5days_table.strftime('%d/%m/%Y')} à {end_date_5days.strftime('%d/%m/%Y')}.")

    if st.button("Actualiser les cours des tickers", key="refresh_5_day_prices_btn"): # Renommé le bouton
        with st.spinner("Récupération des cours des tickers en cours..."):
            last_days_data = {}
            for ticker in tickers_in_portfolio:
                # On récupère un peu plus de jours pour être sûr d'avoir suffisamment de données
                data = fetch_stock_history(ticker, start_date_5days_table - timedelta(days=10), end_date_5days)
                if not data.empty:
                    # Récupère les 'days_range_5_days_table' dernières valeurs non nulles et les re-indexe
                    last_values = data.dropna().reindex(business_days_table).ffill().bfill().tail(days_range_5_days_table)
                    last_days_data[ticker] = last_values
                else:
                    last_days_data[ticker] = pd.Series(dtype='float64') # Vide si pas de données

            # Création d'un DataFrame pour l'affichage
            df_display_prices = pd.DataFrame()
            for ticker, series in last_days_data.items():
                if not series.empty:
                    temp_df = pd.DataFrame(series.rename("Cours").reset_index())
                    temp_df.columns = ["Date", "Cours"]
                    temp_df["Ticker"] = ticker
                    df_display_prices = pd.concat([df_display_prices, temp_df])

            if not df_display_prices.empty:
                # Pivoter le DataFrame pour avoir les dates en colonnes
                df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours")
                # Trier les colonnes de date
                df_pivot = df_pivot.sort_index(axis=1)
                
                # Renommer les colonnes de date pour un affichage plus lisible
                df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]
                
                st.markdown("##### Cours de Clôture des Derniers Jours")
                st.dataframe(df_pivot.style.format(format_fr), use_container_width=True)
            else:
                st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")
