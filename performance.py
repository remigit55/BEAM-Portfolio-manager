# performance.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date # Garder date pour st.date_input
import builtins # Toujours essentiel pour gérer le problème de str()

# Importations spécifiques au test GLDG
import yfinance as yf # Utilisé indirectement par fetch_stock_history
from historical_data_fetcher import fetch_stock_history

# Les imports suivants ne sont plus nécessaires car l'onglet "Performance Globale" est retiré :
# from portfolio_journal import load_portfolio_journal
# from historical_performance_calculator import reconstruct_historical_performance
# from utils import format_fr


def display_performance_history():
    """
    Affiche uniquement le test de récupération des données historiques GLDG.
    (Version simplifiée - l'onglet "Performance Globale" est retiré pour le débogage.)
    """
    
    st.subheader("📊 Test de Récupération des Données Historiques GLDG")
    st.write("Cet onglet sert à vérifier spécifiquement la récupération des données historiques de GLDG.")

    today = datetime.now()
    default_start_date_gldg = today - timedelta(days=30)
    
    start_date_gldg = st.date_input(
        "Date de début (GLDG)",
        value=default_start_date_gldg.date(), # S'assurer que c'est un objet date
        min_value=datetime(1990, 1, 1).date(),
        max_value=today.date(),
        key="start_date_gldg_test"
    )
    end_date_gldg = st.date_input(
        "Date de fin (GLDG)",
        value=today.date(),
        min_value=datetime(1990, 1, 1).date(),
        max_value=today.date(),
        key="end_date_gldg_test"
    )

    if st.button("Récupérer les données GLDG"):
        st.info(f"Tentative de récupération des données pour GLDG du {start_date_gldg.strftime('%Y-%m-%d')} au {end_date_gldg.strftime('%Y-%m-%d')}...")
        
        try:
            start_dt_gldg = datetime.combine(start_date_gldg, datetime.min.time())
            end_dt_gldg = datetime.combine(end_date_gldg, datetime.max.time())
            
            # Appel de la fonction pour récupérer l'historique
            historical_prices = fetch_stock_history("GLDG", start_dt_gldg, end_dt_gldg)

            if not historical_prices.empty:
                st.success(f"✅ Données récupérées avec succès pour GLDG!")
                st.write("Aperçu des données (5 premières lignes) :")
                st.dataframe(historical_prices.head(), use_container_width=True)
                st.write("...")
                st.write("Aperçu des données (5 dernières lignes) :")
                st.dataframe(historical_prices.tail(), use_container_width=True)
                st.write(f"Nombre total de jours : **{len(historical_prices)}**")
                # Utilisation de builtins.str et builtins.isinstance pour éviter le problème de str() écrasé
                st.write(f"Type de l'objet retourné : `{builtins.str(type(historical_prices))}`") 
                st.write(f"L'index est un `DatetimeIndex` : `{builtins.isinstance(historical_prices.index, pd.DatetimeIndex)}`")

                st.subheader("Graphique des cours de clôture GLDG")
                st.line_chart(historical_prices)

            else:
                st.warning(f"❌ Aucune donnée récupérée pour GLDG sur la période spécifiée. "
                           "Vérifiez le ticker ou la période, et votre connexion à Yahoo Finance.")
        except Exception as e:
            # Utilisation de builtins.str pour afficher l'erreur en toute sécurité
            st.error(f"❌ Une erreur est survenue lors de la récupération des données : {builtins.str(e)}")
            if "str' object is not callable" in builtins.str(e):
                st.error("⚠️ **Confirmation :** L'erreur `str() object is not callable` persiste. Cela indique fortement "
                         "qu'une variable ou fonction nommée `str` est définie ailleurs dans votre code, "
                         "écrasant la fonction native de Python. **La recherche globale `str = ` est impérative.**")
            elif "No data found" in builtins.str(e) or "empty DataFrame" in builtins.str(e):
                 st.warning("Yahoo Finance n'a pas retourné de données. Le ticker est-il valide ? La période est-elle trop courte ou dans le futur ?")
            else:
                st.error(f"Détail de l'erreur : {builtins.str(e)}")
