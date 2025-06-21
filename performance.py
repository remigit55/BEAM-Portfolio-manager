# performance.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
# Supprimez 'import yfinance as yf' car nous utiliserons fetch_stock_history
import builtins # IMPORTANT : Explicitement importer builtins pour gérer les problèmes potentiels avec str()

# Importez uniquement ce qui est nécessaire pour cette version simplifiée
from historical_data_fetcher import fetch_stock_history
from utils import format_fr # Gardez utils pour le formatage, assurez-vous qu'il ne contient pas 'str =' ou 'def str('

def display_performance_history():
    """
    Affiche la performance historique d'un ticker sélectionné par l'utilisateur
    à partir des tickers présents dans le DataFrame du portefeuille.
    Version simplifiée de l'onglet Performance.
    """
    st.subheader("📊 Performance d'un Symbole Boursier du Portefeuille")
    st.write("Sélectionnez un symbole boursier de votre portefeuille pour afficher son historique de prix.")

    # Vérifier si le DataFrame du portefeuille est chargé
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.info("Veuillez importer un fichier Excel ou CSV via l'onglet 'Paramètres' pour charger votre portefeuille et afficher les tickers disponibles.")
        return

    # Extraire les tickers uniques du DataFrame du portefeuille
    unique_tickers = []
    if 'Ticker' in st.session_state.df.columns and not st.session_state.df['Ticker'].empty:
        # Convertir en string avant unique() pour gérer les types mixtes et filtrer les valeurs vides/NaN
        unique_tickers = [
            t for t in st.session_state.df['Ticker'].astype(builtins.str).unique().tolist()
            if builtins.isinstance(t, builtins.str) and t.strip() # S'assurer que ce sont des chaînes non vides
        ]
        
        if not unique_tickers:
            st.warning("Aucun symbole boursier valide trouvé dans la colonne 'Ticker' de votre portefeuille.")
            # Si aucun ticker valide n'est trouvé dans le CSV, proposez au moins GLDG comme fallback
            unique_tickers = ["GLDG"]
    else:
        st.warning("La colonne 'Ticker' est introuvable ou vide dans votre portefeuille. Assurez-vous d'avoir une colonne 'Ticker' dans votre fichier importé.")
        # Proposez GLDG comme fallback si la colonne n'existe pas ou est vide
        unique_tickers = ["GLDG"]

    # Ajouter "GLDG" à la liste des tickers si elle n'est pas déjà présente, utile pour les tests
    if "GLDG" not in unique_tickers:
        unique_tickers.insert(0, "GLDG") # Ajoute GLDG au début pour un accès facile

    # Sélecteur de ticker
    selected_ticker = st.selectbox(
        "Sélectionnez un symbole boursier à analyser",
        options=unique_tickers,
        key="selected_portfolio_ticker_performance" # Clé unique
    )

    # Sélecteur de date
    today = datetime.now()
    default_end_date = today.date()
    # Default start date: 1 year ago, but not before 1990-01-01 (common Yahoo Finance limit)
    default_start_date = max(datetime(1990, 1, 1).date(), (today - timedelta(days=365)).date())

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Date de début",
            value=default_start_date,
            min_value=datetime(1990, 1, 1).date(),
            max_value=default_end_date,
            key="performance_date_start" # Clé unique
        )
    with col_end:
        end_date = st.date_input(
            "Date de fin",
            value=default_end_date,
            min_value=start_date,
            max_value=today.date(),
            key="performance_date_end" # Clé unique
        )

    if start_date > end_date:
        st.error("La date de début ne peut pas être postérieure à la date de fin.")
        return

    # Convertir les objets date en objets datetime pour fetch_stock_history
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # Bouton pour lancer la récupération
    if st.button(f"Afficher l'historique de {selected_ticker}", key="fetch_selected_ticker_history_button"):
        if not selected_ticker:
            st.warning("Veuillez sélectionner un symbole boursier valide.")
            return

        st.info(f"Récupération des données pour **{selected_ticker}** du **{start_date.strftime('%Y-%m-%d')}** au **{end_date.strftime('%Y-%m-%d')}**...")
        
        try:
            # Utilisez fetch_stock_history qui est déjà robuste et gère yfinance
            historical_prices = fetch_stock_history(selected_ticker, start_dt, end_dt)

            if not historical_prices.empty:
                st.success(f"✅ Données récupérées avec succès pour {selected_ticker}!")
                st.write("Aperçu des données :")
                st.dataframe(historical_prices.head(), use_container_width=True)
                st.write("...")
                st.dataframe(historical_prices.tail(), use_container_width=True)
                st.write(f"Nombre total d'entrées : **{builtins.str(len(historical_prices))}**")
                st.write(f"Type de l'objet retourné : `{builtins.str(type(historical_prices))}`")
                st.write(f"L'index est un `DatetimeIndex` : `{builtins.isinstance(historical_prices.index, pd.DatetimeIndex)}`")

                st.subheader(f"Graphique des cours de clôture de {selected_ticker}")
                fig = px.line(
                    historical_prices, # Assurez-vous que c'est une Series ou un DataFrame avec la bonne structure
                    x=historical_prices.index, # L'index est la date
                    y=historical_prices.values, # Les valeurs de la Series
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
            if "str' object is not callable" in builtins.str(e):
                st.error("⚠️ **Confirmation :** L'erreur `str() object is not callable` persiste. Cela indique fortement "
                         "qu'une variable ou fonction nommée `str` est définie ailleurs dans votre code, "
                         "écrasant la fonction native de Python. **La recherche globale `str = ` est impérative.**")
            elif "No data found" in builtins.str(e) or "empty DataFrame" in builtins.str(e):
                 st.warning("Yahoo Finance n'a pas retourné de données. Le symbole boursier est-il valide ? La période est-elle trop courte ou dans le futur ?")
            else:
                st.error(f"Détail de l'erreur : {builtins.str(e)}")
