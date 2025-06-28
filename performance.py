# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay # Pour les jours ouvrables
import yfinance as yf
import builtins # Pour contourner l'écrasement de str()

# Importe le nouveau composant personnalisé
from period_selector_component import period_selector

# Import des fonctions nécessaires
from historical_data_fetcher import fetch_stock_history, get_all_historical_data, fetch_historical_fx_rates # <-- Assurez-vous que fetch_historical_fx_rates est bien importé d'ici
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr
from portfolio_display import convertir # Importer la fonction de conversion

# La fonction fetch_fx_rates_dummy est supprimée car nous utilisons la vraie fonction maintenant.

def display_performance_history():
    """
    Affiche la performance historique du portefeuille basée sur sa composition actuelle,
    et un tableau des derniers cours de clôture pour tous les tickers, avec sélection de plage de dates.
    """
    st.subheader("Performance Historique du Portefeuille")

    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets pour voir les performances.")
        return

    df_current_portfolio = st.session_state.df.copy()
    target_currency = st.session_state.get("devise_cible", "EUR")

    # Initialisation ou rafraîchissement des taux de change historiques
    # Cette partie est maintenant plus simple car fetch_historical_fx_rates est mis en cache
    # et gère sa propre robustesse.
    if "historical_fx_rates_df" not in st.session_state or st.session_state.historical_fx_rates_df is None:
        st.info("Récupération des taux de change historiques initiaux...")
        end_date_for_fx = datetime.now().date()
        # Récupérer les taux sur une période plus large pour s'assurer de couvrir toutes les dates nécessaires
        start_date_for_fx = end_date_for_fx - timedelta(days=365 * 10) # Par exemple, 10 ans
        try:
            st.session_state.historical_fx_rates_df = fetch_historical_fx_rates(target_currency, start_date_for_fx, end_date_for_fx)
            if st.session_state.historical_fx_rates_df.empty:
                st.warning("Aucun taux de change historique n'a pu être récupéré. Les conversions de devise pourraient être incorrectes.")
                # Fallback to a default DataFrame if empty, though fetch_historical_fx_rates should handle this
                st.session_state.historical_fx_rates_df = pd.DataFrame(1.0, index=pd.date_range(start=start_date_for_fx, end=end_date_for_fx),
                                                                        columns=[f"{c}{target_currency}" for c in ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"] if c != target_currency])
        except Exception as e:
            st.error(f"Erreur lors de la récupération des taux de change historiques : {e}. Les conversions de devise pourraient être incorrectes.")
            st.session_state.historical_fx_rates_df = pd.DataFrame(1.0, index=pd.date_range(start=start_date_for_fx, end=end_date_for_fx),
                                                                    columns=[f"{c}{target_currency}" for c in ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"] if c != target_currency])

    # Vérification finale pour s'assurer que historical_fx_rates_df est un DataFrame valide
    if st.session_state.historical_fx_rates_df is None or not isinstance(st.session_state.historical_fx_rates_df, pd.DataFrame) or st.session_state.historical_fx_rates_df.empty:
        st.error("Les données de taux de change historiques sont manquantes ou invalides. Impossible de procéder aux conversions.")
        return # Exit if FX rates are not properly loaded

    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE VIA COMPOSANT PERSONNALISÉ ---

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

    st.markdown("#### Sélection de la période d'affichage des cours")
    
    # Appel du composant personnalisé
    new_selected_period = period_selector(
        period_options=period_options,
        selected_period=st.session_state.selected_ticker_table_period,
        key="period_selector_custom_component" # Clé unique pour ce composant
    )

    # Si une nouvelle période a été sélectionnée par le composant, mettre à jour l'état de session et relancer
    if new_selected_period != st.session_state.selected_ticker_table_period:
        st.session_state.selected_ticker_table_period = new_selected_period
        st.rerun() 

    end_date_table = datetime.now().date()
    selected_period_td = period_options[st.session_state.selected_ticker_table_period]
    start_date_table = end_date_table - selected_period_td

    st.info(f"Affichage des cours de clôture pour les tickers du portefeuille sur la période : {start_date_table.strftime('%d/%m/%Y')} à {end_date_table.strftime('%d/%m/%Y')}.")

    with st.spinner("Récupération et conversion des cours des tickers en cours..."):
        last_days_data = {}
        # Fetch a wider range of data to ensure enough business days are available
        fetch_start_date = start_date_table - timedelta(days=max(30, selected_period_td.days // 2)) # Adjust fetch range dynamically
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            ticker_devise = target_currency
            # Find the currency for the current ticker from the portfolio DataFrame
            if "Devise" in df_current_portfolio.columns and ticker in df_current_portfolio["Ticker"].values:
                ticker_devise_row = df_current_portfolio[df_current_portfolio["Ticker"] == ticker]["Devise"]
                if not ticker_devise_row.empty and pd.notnull(ticker_devise_row.iloc[0]):
                    ticker_devise = str(ticker_devise_row.iloc[0]).strip().upper()
            
            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                converted_data = pd.Series(index=filtered_data.index, dtype=float)
                
                for date_idx, price in filtered_data.items():
                    date_as_date = date_idx.date() # Convert Timestamp to date object
                    
                    # Get the specific FX rate for this date and currency pair
                    # The column name in historical_fx_rates_df is SOURCETARGET (e.g., "USDEUR")
                    fx_key = f"{ticker_devise}{target_currency}"
                    
                    fx_rate_for_date = 1.0 # Default fallback
                    # Check if the column exists in the FX DataFrame and if the date exists in its index
                    if fx_key in st.session_state.historical_fx_rates_df.columns:
                        if date_as_date in st.session_state.historical_fx_rates_df.index:
                            fx_rate_for_date = st.session_state.historical_fx_rates_df.loc[date_as_date, fx_key]
                        else:
                            # Fallback if date is not in FX index (should be rare with reindex/ffill/bfill)
                            st.warning(f"FX rate for {fx_key} on {date_as_date} not found in historical_fx_rates_df. Using 1.0.")
                    else:
                        # This means we don't have a direct or indirect conversion for this pair.
                        # This should ideally be handled by fetch_historical_fx_rates to create a column with 1.0s.
                        st.warning(f"FX column {fx_key} not found in historical_fx_rates_df. Using 1.0.")
                    
                    if pd.isna(fx_rate_for_date) or fx_rate_for_date == 0:
                        fx_rate_for_date = 1.0 # Final fallback if specific rate is NaN or zero

                    # The `convertir` function expects a dictionary of rates where key is source_devise
                    # So, we pass a small dict with just the rate for ticker_devise
                    converted_price, _ = convertir(price, ticker_devise, target_currency, {ticker_devise: fx_rate_for_date})
                    converted_data[date_idx] = converted_price
                last_days_data[ticker] = converted_data
            else:
                last_days_data[ticker] = pd.Series(dtype='float64')

        df_display_prices = pd.DataFrame()
        for ticker, series in last_days_data.items():
            if not series.empty:
                temp_df = pd.DataFrame({"Date": series.index, "Cours": series.values})
                temp_df["Ticker"] = ticker
                df_display_prices = pd.concat([df_display_prices, temp_df], ignore_index=True)

        if not df_display_prices.empty:
            df_pivot = df_display_prices.pivot_table(index="Ticker", columns="Date", values="Cours", dropna=False)
            df_pivot = df_pivot.sort_index(axis=1)
            
            # Ensure only dates within the selected display range are shown
            df_pivot = df_pivot.loc[:, (df_pivot.columns >= pd.Timestamp(start_date_table)) & (df_pivot.columns <= pd.Timestamp(end_date_table))]

            df_pivot.columns = [col.strftime('%d/%m/%Y') for col in df_pivot.columns]
            
            st.markdown("##### Cours de Clôture des Derniers Jours")
            st.dataframe(df_pivot.style.format(lambda x: f"{format_fr(x, 2)} {target_currency}" if pd.notnull(x) else "N/A"),
                          use_container_width=True)
        else:
            st.warning("Aucun cours de clôture n'a pu être récupéré pour la période sélectionnée.")

