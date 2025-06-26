# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf # Garder si vous avez des tests yfinance séparés
import builtins
if not callable(str):
    str = builtins.str

# Import des fonctions nécessaires
from historical_data_fetcher import fetch_stock_history # Peut être utile pour un test de ticker individuel
from historical_performance_calculator import reconstruct_historical_portfolio_value # Import la nouvelle fonction
from utils import format_fr # Pour le formatage des nombres

def display_performance_history():
    """
    Affiche la performance historique du portefeuille basée sur sa composition actuelle.
    Permet de sélectionner une plage de dates et de visualiser la valeur du portefeuille.
    """
    st.subheader("Performance Historique du Portefeuille")

    # Vérifier si le portefeuille est chargé
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        return

    df_current_portfolio = st.session_state.df.copy()
    target_currency = st.session_state.get("devise_cible", "EUR")

    st.markdown(f"**Calcul de la performance pour la composition actuelle du portefeuille en {target_currency}.**")

    # Sélection de la plage de dates
    today = datetime.now().date()
    default_start_date = today - timedelta(days=365) # Par défaut : 1 an d'historique
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Date de début", value=default_start_date)
    with col2:
        end_date = st.date_input("Date de fin", value=today)

    if start_date >= end_date:
        st.error("La date de début doit être antérieure à la date de fin.")
        return

    # Bouton pour lancer le calcul
    if st.button("Calculer Performance Historique"):
        with st.spinner("Calcul de la performance historique en cours... Cela peut prendre un moment si la période est longue et si de nombreuses données doivent être téléchargées."):
            df_historical_values = reconstruct_historical_portfolio_value(
                df_current_portfolio, start_date, end_date, target_currency
            )

            if not df_historical_values.empty:
                st.success("Performance historique calculée avec succès !")
                
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
                    y=["Valeur Actuelle", "Valeur Acquisition"], # Affiche la valeur actuelle et la valeur d'acquisition
                    title=f"Évolution de la Valeur du Portefeuille ({target_currency})",
                    labels={"value": "Valeur", "variable": "Type de Valeur"},
                    # Personnalisation de l'info-bulle au survol
                    hover_data={
                        "Valeur Acquisition": ':.2f', 
                        "Valeur Actuelle": ':.2f', 
                        "Gain/Perte Absolu": ':.2f', 
                        "Gain/Perte (%)": ':.2f'
                    }
                )
                fig.update_layout(hovermode="x unified") # Info-bulle unifiée pour les points sur l'axe X
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

    # L'ancienne section de test de ticker individuel a été retirée pour simplifier l'interface ici.
    # Si vous souhaitez la conserver pour le débogage, vous pouvez la réintégrer.
