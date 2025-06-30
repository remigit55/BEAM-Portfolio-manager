from data_fetcher import fetch_fx_rates
# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import numpy as np

from period_selector_component import period_selector
from historical_data_fetcher import fetch_stock_history, fetch_historical_fx_rates
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr
from portfolio_display import convertir

def convertir_valeur_performance(val, source_devise, devise_cible, fx_rates_or_scalar, fx_adjustment_factor=1.0):
    """
    Fonction locale pour performance.py.
    Applique le facteur d'ajustement sur la valeur (ex: GBp -> GBP = x0.01),
    puis applique le taux de conversion.
    """
    if pd.isnull(val):
        return np.nan, np.nan

    source_devise = str(source_devise).strip().upper()
    devise_cible = str(devise_cible).strip().upper()

    if source_devise == devise_cible:
        return val * fx_adjustment_factor, 1.0

    taux_scalar = np.nan
    if isinstance(fx_rates_or_scalar, dict):
        taux_scalar = float(fx_rates_or_scalar.get(source_devise, np.nan))
    elif isinstance(fx_rates_or_scalar, (float, int, np.floating, np.integer)):
        taux_scalar = float(fx_rates_or_scalar)
    else:
        st.warning(f"Type de taux de change inattendu: {type(fx_rates_or_scalar)}. Utilisation de 1.0.")
        taux_scalar = 1.0

    if pd.isna(taux_scalar) or taux_scalar == 0:
        st.warning(f"Pas de conversion pour {source_devise} vers {devise_cible}: taux manquant ou invalide ({taux_scalar}).")
        return val, np.nan

    valeur_ajustee = val * fx_adjustment_factor
    return valeur_ajustee * taux_scalar, taux_scalar

def display_performance_history():  
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres'.")
        return

    df_current_portfolio = st.session_state.df.copy()
    
    # Debugging: Inspect DataFrame columns and Devise values
    st.write("Colonnes du DataFrame:", df_current_portfolio.columns.tolist())
    if "Devise" in df_current_portfolio.columns:
        st.write("Valeurs uniques dans 'Devise':", df_current_portfolio["Devise"].unique())
    
    # Initialize columns and handle GBp
    if "Devise" in df_current_portfolio.columns:
        df_current_portfolio["Devise"] = df_current_portfolio["Devise"].astype(str).str.strip()
        df_current_portfolio["Devise_Originale"] = df_current_portfolio["Devise"]
        # Set adjustment factor based on Devise_Originale
        df_current_portfolio["Facteur_Ajustement_FX"] = 1.0
        df_current_portfolio.loc[
            df_current_portfolio["Devise_Originale"].str.strip().str.upper() == "GBP",
            "Facteur_Ajustement_FX"
        ] = 0.01
        # Pop-up for GBp detection
        if (df_current_portfolio["Devise_Originale"].str.strip().str.upper() == "GBP").any():
            st.warning("Devise GBp détectée dans la colonne 'Devise_Originale'. Facteur d'ajustement fixé à 0.01.")
        else:
            st.info("Aucune devise 'GBp' trouvée dans la colonne 'Devise_Originale'.")
    
    # --- Récupération de la devise cible ---
    target_currency = st.session_state.get("devise_cible", "EUR")
    
    # --- Récupération des taux de change nécessaires ---
    devises_uniques_df = df_current_portfolio["Devise"].dropna().unique().tolist()
    devises_a_fetch = list(set([target_currency] + devises_uniques_df))
    st.session_state.fx_rates = fetch_fx_rates(target_currency)
    fx_rates = st.session_state.fx_rates
    st.write("Taux de change disponibles:", fx_rates)
    
    # --- Tickers à afficher ---
    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher.")
        return

    # --- Sélection de période ---
    period_options = {
        "1W": timedelta(weeks=1), "1M": timedelta(days=30), "3M": timedelta(days=90),
        "6M": timedelta(days=180), "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5), "10Y": timedelta(days=365 * 10),
        "20Y": timedelta(days=365 * 20)
    }
    period_labels = list(period_options.keys())
    current_selected_label = st.session_state.get("selected_ticker_table_period_label", "1W")
    if current_selected_label not in period_labels:
        current_selected_label = "1W"
    default_period_index = period_labels.index(current_selected_label)

    selected_label = st.radio(
        "Sélectionnez une période:",
        period_labels,
        index=default_period_index,
        key="selected_ticker_table_period_radio",
        horizontal=True
    )
    st.session_state.selected_ticker_table_period_label = selected_label
    selected_period_td = period_options[selected_label]

    end_date_table = datetime.now().date()
    start_date_table = end_date_table - selected_period_td

    with st.spinner("Récupération et conversion des cours..."):
        all_ticker_data = []
        fetch_start_date = start_date_table - timedelta(days=max(30, selected_period_td.days // 2))
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            ticker_devise = target_currency
            quantity = 0.0
            fx_adjustment_factor = 1.0

            ticker_row = df_current_portfolio[df_current_portfolio["Ticker"] == ticker]
            if not ticker_row.empty:
                if "Devise_Originale" in ticker_row.columns and pd.notnull(ticker_row["Devise_Originale"].iloc[0]):
                    ticker_devise = str(ticker_row["Devise_Originale"].iloc[0]).strip().upper()
                    if ticker_devise == "GBP":
                        # Note: If fetch_stock_history returns prices in GBP, set fx_adjustment_factor to 1.0
                        # If it returns prices in GBp, use 0.01
                        fx_adjustment_factor = 0.01  # Assuming prices are in GBp
                        ticker_devise = "GBP"
                        st.write(f"GBp détecté pour {ticker}, Facteur_Ajustement_FX: {fx_adjustment_factor}, Devise ajustée: {ticker_devise}")
                    else:
                        fx_adjustment_factor = 1.0
                if "Quantité" in ticker_row.columns:
                    quantity = pd.to_numeric(ticker_row["Quantité"], errors='coerce').iloc[0] or 0.0

            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                for date_idx, price in filtered_data.items():
                    fx_key = ticker_devise
                    fx_rate_for_date = fx_rates.get(fx_key, 1.0)
                    st.write(f"Ticker: {ticker}, Date: {date_idx}, Price: {price}, Devise: {fx_key}, FX Rate: {fx_rate_for_date}, FX Adjustment: {fx_adjustment_factor}")
                    converted_price, taux_scalar = convertir_valeur_performance(price, ticker_devise, target_currency, fx_rate_for_date, fx_adjustment_factor)
                    st.write(f"Converted Price for {ticker} on {date_idx}: {converted_price}")
                    all_ticker_data.append({
                        "Date": date_idx,
                        "Ticker": ticker,
                        f"Valeur Actuelle ({target_currency})": converted_price * quantity
                    })

        df_display_values = pd.DataFrame(all_ticker_data)
        
        if not df_display_values.empty:
            df_total_daily_value = df_display_values.groupby('Date')[f"Valeur Actuelle ({target_currency})"].sum().reset_index()
            df_total_daily_value.columns = ['Date', 'Valeur Totale']
            df_total_daily_value['Date'] = pd.to_datetime(df_total_daily_value['Date'])
            df_total_daily_value = df_total_daily_value.sort_values('Date')

            st.markdown("---")
            st.markdown("#### Performance du Portefeuille")
            fig_total = px.line(
                df_total_daily_value,
                x="Date",
                y="Valeur Totale",
                title=f"Valeur Totale du Portefeuille par Jour ({target_currency})",
                labels={"Valeur Totale": f"Valeur Totale ({target_currency})", "Date": "Date"},
                hover_data={"Valeur Totale": ':.2f'}
            )
            fig_total.update_layout(hovermode="x unified")
            st.plotly_chart(fig_total, use_container_width=True)

            st.markdown("---")
            st.markdown("#### Volatilité Quotidienne du Portefeuille")
            df_total_daily_value['Rendement Quotidien'] = df_total_daily_value['Valeur Totale'].pct_change()
            window_size = 20
            df_total_daily_value['Volatilité'] = df_total_daily_value['Rendement Quotidien'].rolling(window=window_size).std() * (252**0.5)

            if not df_total_daily_value['Volatilité'].dropna().empty:
                fig_volatility = px.line(
                    df_total_daily_value.dropna(subset=['Volatilité']),
                    x="Date",
                    y="Volatilité",
                    title=f"Volatilité Annualisée (Fenêtre de {window_size} jours)",
                    labels={"Volatilité": "Volatilité Annualisée", "Date": "Date"},
                    hover_data={"Volatilité": ':.4f'}
                )
                fig_volatility.update_layout(hovermode="x unified")
                st.plotly_chart(fig_volatility, use_container_width=True)

            st.markdown("---")
            st.markdown("#### Momentum du Portefeuille")
            initial_value = df_total_daily_value['Valeur Totale'].iloc[0] if not df_total_daily_value['Valeur Totale'].empty else 0
            df_total_daily_value['Momentum (%)'] = ((df_total_daily_value['Valeur Totale'] / initial_value) - 1) * 100 if initial_value != 0 else 0

            if not df_total_daily_value['Momentum (%)'].dropna().empty:
                fig_momentum = px.line(
                    df_total_daily_value,
                    x="Date",
                    y="Momentum (%)",
                    title=f"Performance Cumulée du Portefeuille ({target_currency})",
                    labels={"Momentum (%)": "Changement en %", "Date": "Date"},
                    hover_data={"Momentum (%)": ':.2f'}
                )
                fig_momentum.update_layout(hovermode="x unified")
                st.plotly_chart(fig_momentum, use_container_width=True)

            st.markdown("---")
            df_pivot_current_value = df_display_values.pivot_table(index="Ticker", columns="Date", values=f"Valeur Actuelle ({target_currency})", dropna=False)
            df_pivot_current_value = df_pivot_current_value.sort_index(axis=1)
            df_pivot_current_value = df_pivot_current_value.loc[:, (df_pivot_current_value.columns >= pd.Timestamp(start_date_table)) & (df_pivot_current_value.columns <= pd.Timestamp(end_date_table))]
            df_pivot_current_value.columns = [f"Valeur Actuelle ({col.strftime('%d/%m/%Y')})" for col in df_pivot_current_value.columns]
            df_final_display = df_pivot_current_value.reset_index()

            sorted_columns = ['Ticker']
            dates_ordered = sorted(list(set([col.date() for col in df_display_values['Date']])))
            for d in dates_ordered:
                date_str = d.strftime('%d/%m/%Y')
                sorted_columns.append(f"Valeur Actuelle ({date_str})")
            final_columns_to_display = [col for col in sorted_columns if col in df_final_display.columns]
            df_final_display = df_final_display[final_columns_to_display]

            format_dict = {col: lambda x: f"{format_fr(x, 2)} {target_currency}" if pd.notnull(x) else "N/A" for col in df_final_display.columns if "Valeur Actuelle (" in col}

            st.markdown("##### Valeur Actuelle du Portefeuille par Ticker (avec conversion)")
            st.dataframe(df_final_display.style.format(format_dict), use_container_width=True, hide_index=True)
        else:
            st.warning("Aucune valeur actuelle calculée pour la période sélectionnée.")
