# performance.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import builtins # IMPORTANT : Explicitement importer builtins pour gérer les problèmes potentiels avec str()

# Importez uniquement ce qui est nécessaire pour cette version simplifiée
from historical_data_fetcher import fetch_stock_history 
from utils import format_fr # Gardez utils pour le formatage, assurez-vous qu'il ne contient pas 'str =' ou 'def str('

def display_performance_history():
    """
    Affiche la performance historique des prix d'un ticker sélectionné.
    Ceci est une version simplifiée pour le débogage et l'isolation.
    """
    st.subheader("📊 Performance d'un Symbole Boursier")
    st.write("Cet onglet vous permet d'afficher la performance historique des prix d'un symbole boursier sélectionné.")

    # Définir une liste de tickers courants pour la sélection
    # Vous pouvez personnaliser cette liste ou la rendre dynamique
    common_tickers = ["GLDG", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "BTC-USD", "ETH-USD"]
    
    selected_ticker = st.selectbox(
        "Sélectionnez un symbole boursier", 
        options=common_tickers,
        key="performance_ticker_select" # Clé unique pour ce widget
    )

    today = datetime.now()
    default_end_date = today.date()
    default_start_date = (today - timedelta(days=90)).date() # Par défaut, les 3 derniers mois

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Date de début", 
            value=default_start_date,
            min_value=datetime(1990, 1, 1).date(), # Date de début minimale
            max_value=default_end_date, # Ne peut pas commencer après la date de fin par défaut
            key="performance_start_date" # Clé unique
        )
    with col_end:
        end_date = st.date_input(
            "Date de fin", 
            value=default_end_date,
            min_value=start_date, # Doit être après la date de début sélectionnée
            max_value=today.date(), # Ne peut pas être dans le futur
            key="performance_end_date" # Clé unique
        )

    # Assurez-vous que la date de début n'est pas après la date de fin
    if start_date > end_date:
        st.error("La date de début ne peut pas être postérieure à la date de fin.")
        return

    # Convertir les objets date en objets datetime pour fetch_stock_history (qui attend des datetimes)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # Bouton pour lancer la récupération des données
    if st.button(f"Afficher la performance de {selected_ticker}", key="show_ticker_performance_button"):
        st.info(f"Récupération des données pour **{selected_ticker}** du **{start_date.strftime('%Y-%m-%d')}** au **{end_date.strftime('%Y-%m-%d')}**...")
        
        try:
            # Appel à fetch_stock_history du module historical_data_fetcher
            historical_prices = fetch_stock_history(selected_ticker, start_dt, end_dt)

            if not historical_prices.empty:
                st.success(f"✅ Données récupérées avec succès pour {selected_ticker}!")
                st.write("Aperçu des données (5 premières lignes) :")
                st.dataframe(historical_prices.head(), use_container_width=True)
                st.write("...")
                st.write("Aperçu des données (5 dernières lignes) :")
                st.dataframe(historical_prices.tail(), use_container_width=True)
                st.write(f"Nombre total de jours : **{builtins.str(len(historical_prices))}**") # Utiliser builtins.str
                
                # Utiliser builtins.str pour l'affichage des types par précaution
                st.write(f"Type de l'objet retourné : `{builtins.str(type(historical_prices))}`")
                st.write(f"L'index est un `DatetimeIndex` : `{builtins.str(builtins.isinstance(historical_prices.index, pd.DatetimeIndex))}`")

                st.subheader(f"Graphique des cours de clôture de {selected_ticker}")
                fig = px.line(
                    historical_prices, 
                    x=historical_prices.index, 
                    y=historical_prices.values, 
                    title=f"Cours de clôture ajusté pour {selected_ticker}",
                    labels={"x": "Date", "y": "Prix de Clôture Ajusté"}
                )
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

            else:
                st.warning(f"❌ Aucune donnée récupérée pour {selected_ticker} sur la période spécifiée. "
                           "Vérifiez le symbole boursier ou la période, et votre connexion à Yahoo Finance.")
        except Exception as e:
            st.error(f"❌ Une erreur est survenue lors de la récupération des données : {builtins.str(e)}")
            # Maintenir la vérification explicite de l'erreur str()
            if "str' object is not callable" in builtins.str(e):
                st.error("⚠️ **Confirmation :** L'erreur `str() object is not callable` persiste. Cela indique fortement "
                         "qu'une variable ou fonction nommée `str` est définie ailleurs dans votre code, "
                         "écrasant la fonction native de Python. **La recherche globale `str = ` est impérative.**")
            elif "No data found" in builtins.str(e) or "empty DataFrame" in builtins.str(e):
                 st.warning("Yahoo Finance n'a pas retourné de données. Le symbole boursier est-il valide ? La période est-elle trop courte ou dans le futur ?")
            else:
                st.error(f"Détail de l'erreur : {builtins.str(e)}")
