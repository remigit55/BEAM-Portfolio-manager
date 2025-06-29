# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import builtins

from period_selector_component import period_selector
from historical_data_fetcher import fetch_stock_history, get_all_historical_data, fetch_historical_fx_rates
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr
from portfolio_display import convertir

def is_pence_denominated(currency):
    """
    Détermine si un actif est libellé en pence (GBp) en fonction de la devise.
    Retourne True si une conversion (division par 100) est nécessaire.
    """
    return str(currency).strip().lower() in ['gbp', 'gbp.', 'gbp ']

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
    if "historical_fx_rates_df" not in st.session_state or st.session_state.historical_fx_rates_df is None:
        st.info("Récupération des taux de change historiques initiaux...")
        end_date_for_fx = datetime.now().date()
        start_date_for_fx = end_date_for_fx - timedelta(days=365 * 10)
        try:
            st.session_state.historical_fx_rates_df = fetch_historical_fx_rates(target_currency, start_date_for_fx, end_date_for_fx)
            if st.session_state.historical_fx_rates_df.empty:
                st.warning("Aucun taux de change historique n'a pu être récupéré. Les conversions de devise pourraient être incorrectes.")
                st.session_state.historical_fx_rates_df = pd.DataFrame(
                    1.0, 
                    index=pd.bdate_range(start=start_date_for_fx, end=end_date_for_fx),
                    columns=[f"{c}{target_currency}" for c in ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"] if c != target_currency]
                )
        except Exception as e:
            st.error(f"Erreur lors de la récupération des taux de change historiques : {e}. Les conversions de devise pourraient être incorrectes.")
            st.session_state.historical_fx_rates_df = pd.DataFrame(
                1.0, 
                index=pd.bdate_range(start=start_date_for_fx, end=end_date_for_fx),
                columns=[f"{c}{target_currency}" for c in ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"] if c != target_currency]
            )

    if st.session_state.historical_fx_rates_df is None or not isinstance(st.session_state.historical_fx_rates_df, pd.DataFrame) or st.session_state.historical_fx_rates_df.empty:
        st.error("Les données de taux de change historiques sont manquantes ou invalides. Impossible de procéder aux conversions.")
        return

    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille.")
        return

    # --- SÉLECTION DE PÉRIODE AVEC ST.RADIO ---
    period_options = {
        "1W": timedelta(weeks=1), 
        "1M": timedelta(days=30), 
        "3M": timedelta(days=90),
        "6M": timedelta(days=180), 
        "1Y": timedelta(days=365), 
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10)
    }
    period_labels = list(period_options.keys())
    
    current_selected_label = st.session_state.get("selected_ticker_table_period_label", "1W")
    if current_selected_label not in period_labels:
        current_selected_label = "1W"
    default_period_index = period_labels.index(current_selected_label)

    st.markdown("#### Sélection de la période d'affichage des cours")
    selected_label = st.radio(
        "", 
        period_labels, 
        index=default_period_index,
        key="selected_ticker_table_period_radio", 
        horizontal=True
    )
    st.session_state.selected_ticker_table_period_label = selected_label
    selected_period_td = period_options[selected_label]

    end_date_table = datetime.now().date()
    start_date_table = end_date_table - selected_period_td

    st.info(f"Affichage des valeurs actuelles pour les tickers du portefeuille sur la période : {start_date_table.strftime('%d/%m/%Y')} à {end_date_table.strftime('%d/%m/%Y')}.")

    with st.spinner("Récupération et conversion des cours des tickers en cours..."):
        all_ticker_data = [] 
        fetch_start_date = start_date_table - timedelta(days=max(30, selected_period_td.days // 2))
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        for ticker in tickers_in_portfolio:
            ticker_devise = target_currency
            quantity = 0.0 
            fx_adjustment_factor = 1.0 
            
            ticker_row = df_current_portfolio[df_current_portfolio["Ticker"] == ticker]
            
            if not ticker_row.empty:
                if "Devise" in ticker_row.columns and not ticker_row["Devise"].empty and pd.notnull(ticker_row["Devise"].iloc[0]):
                    ticker_devise = str(ticker_row["Devise"].iloc[0]).strip().upper()
                
                if "Quantité" in ticker_row.columns:
                    numeric_quantities = pd.to_numeric(ticker_row["Quantité"], errors='coerce')
                    if not numeric_quantities.empty and pd.notnull(numeric_quantities.iloc[0]):
                        quantity = numeric_quantities.iloc[0]
                    else:
                        st.warning(f"Quantité pour le ticker '{ticker}' est vide ou invalide dans le DataFrame du portefeuille. Utilisation de 0.")
                        quantity = 0.0
                else:
                    st.warning(f"Colonne 'Quantité' manquante pour le ticker '{ticker}' dans le DataFrame du portefeuille. Utilisation de 0.")
                    quantity = 0.0

                if "Facteur_Ajustement_FX" in ticker_row.columns:
                    numeric_fx_factor = pd.to_numeric(ticker_row["Facteur_Ajustement_FX"], errors='coerce')
                    if not numeric_fx_factor.empty and pd.notnull(numeric_fx_factor.iloc[0]):
                        fx_adjustment_factor = numeric_fx_factor.iloc[0]
                    else:
                        st.warning(f"Facteur d'ajustement FX pour le ticker '{ticker}' est vide ou invalide. Utilisation de 1.0.")
                        fx_adjustment_factor = 1.0
                else:
                    fx_adjustment_factor = 1.0 

            else:
                st.warning(f"Ticker '{ticker}' non trouvé dans le DataFrame du portefeuille. Impossible de récupérer la quantité et le facteur FX. Utilisation de 0 et 1.0.")
                quantity = 0.0
                fx_adjustment_factor = 1.0

            data = fetch_stock_history(ticker, fetch_start_date, end_date_table, currency=ticker_devise)
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                
                for date_idx, price in filtered_data.items():
                    conversion_currency = ticker_devise
                    if is_pence_denominated(ticker_devise):
                        conversion_currency = "GBP"
                    
                    fx_key = f"{conversion_currency}{target_currency}"
                    
                    fx_rate_for_date = 1.0
                    if fx_key in st.session_state.historical_fx_rates_df.columns:
                        if date_idx in st.session_state.historical_fx_rates_df.index: 
                            fx_rate_for_date = st.session_state.historical_fx_rates_df.loc[date_idx, fx_key]
                    
                    if pd.isna(fx_rate_for_date) or fx_rate_for_date == 0:
                        fx_rate_for_date = 1.0

                    converted_price, _ = convertir(price, conversion_currency, target_currency, fx_rate_for_date, fx_adjustment_factor)
                    
                    current_value = converted_price * quantity 

                    all_ticker_data.append({
                        "Date": date_idx,
                        "Ticker": ticker,
                        f"Valeur Actuelle ({target_currency})": current_value 
                    })

        df_display_values = pd.DataFrame(all_ticker_data)

        if not df_display_values.empty:
            df_total_daily_value = df_display_values.groupby('Date')[f"Valeur Actuelle ({target_currency})"].sum().reset_index()
            df_total_daily_value.columns = ['Date', 'Valeur Totale']
            
            st.markdown("##### Évolution Quotidienne de la Valeur Totale du Portefeuille")
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

            format_dict = {}
            for col in df_final_display.columns:
                if "Valeur Actuelle (" in col: 
                    format_dict[col] = lambda x: f"{format_fr(x, 2)} {target_currency}" if pd.notnull(x) else "N/A"

            st.markdown("##### Valeur Actuelle du Portefeuille par Ticker (avec conversion)")
            st.dataframe(df_final_display.style.format(format_dict), use_container_width=True, hide_index=True)
        else:
            st.warning("Aucune valeur actuelle n'a pu être calculée pour la période sélectionnée.")
