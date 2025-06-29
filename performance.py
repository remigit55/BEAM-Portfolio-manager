# -*- coding: utf-8 -*-
# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import yfinance as yf
import numpy as np

from period_selector_component import period_selector  # Assumes this module exists
from historical_data_fetcher import fetch_stock_history, get_all_historical_data, fetch_historical_fx_rates
from historical_performance_calculator import reconstruct_historical_portfolio_value  # Assumes this module exists
from utils import format_fr
from portfolio_display import convertir

def display_performance_history():
    """
    Affiche la performance historique du portefeuille basée sur sa composition actuelle,
    et un tableau des derniers cours de clôture pour tous les tickers, avec sélection de plage de dates.
    """
    if "df" not in st.session_state or st.session_state.df is None or not isinstance(st.session_state.df, pd.DataFrame):
        st.error("Le portefeuille (st.session_state.df) est manquant ou invalide. Veuillez importer un fichier CSV/Excel via l'onglet 'Paramètres' ou charger depuis l'URL de Google Sheets.")
        return

    df_current_portfolio = st.session_state.df.copy()
    
    # Validate required columns
    required_columns = ['Ticker', 'Quantité', 'Devise']
    missing_columns = [col for col in required_columns if col not in df_current_portfolio.columns]
    if missing_columns:
        st.error(f"Colonnes manquantes dans le portefeuille : {missing_columns}. Assurez-vous que le fichier importé contient 'Ticker', 'Quantité', et 'Devise'.")
        return

    # Log portfolio data for debugging
    st.write("DEBUG: df_current_portfolio head()")
    st.dataframe(df_current_portfolio.head())
    try:
        st.write("DEBUG: df_current_portfolio info()")
        st.write(df_current_portfolio.info())
        st.write("DEBUG: df_current_portfolio describe()")
        st.write(df_current_portfolio.describe(include='all'))
    except Exception as e:
        st.warning(f"Impossible d'afficher les informations de df_current_portfolio : {e}")

    target_currency = st.session_state.get("devise_cible", "EUR")

    # Initialisation ou rafraîchissement des taux de change historiques
    if "historical_fx_rates_df" not in st.session_state or st.session_state.historical_fx_rates_df is None or st.session_state.historical_fx_rates_df.empty:
        st.info("Récupération des taux de change historiques initiaux...")
        end_date_for_fx = datetime.now().date()
        start_date_for_fx = end_date_for_fx - timedelta(days=365 * 10)
        try:
            st.session_state.historical_fx_rates_df = fetch_historical_fx_rates(target_currency, start_date_for_fx, end_date_for_fx)
            if st.session_state.historical_fx_rates_df.empty:
                st.warning("Aucun taux de change historique n'a pu être récupéré. Création d'un DataFrame de secours avec taux à 1.0.")
                st.session_state.historical_fx_rates_df = pd.DataFrame(
                    1.0, 
                    index=pd.bdate_range(start=start_date_for_fx, end=end_date_for_fx),
                    columns=[f"{c}{target_currency}" for c in ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"] if c != target_currency]
                )
        except Exception as e:
            st.error(f"Erreur lors de la récupération des taux de change historiques : {e}. Création d'un DataFrame de secours avec taux à 1.0.")
            st.session_state.historical_fx_rates_df = pd.DataFrame(
                1.0, 
                index=pd.bdate_range(start=start_date_for_fx, end=end_date_for_fx),
                columns=[f"{c}{target_currency}" for c in ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"] if c != target_currency]
            )

    # Log FX rates for debugging
    st.write("DEBUG: historical_fx_rates_df head()")
    try:
        st.dataframe(st.session_state.historical_fx_rates_df.head())
        st.write("DEBUG: historical_fx_rates_df info()")
        st.write(st.session_state.historical_fx_rates_df.info())
    except Exception as e:
        st.warning(f"Impossible d'afficher les informations de historical_fx_rates_df : {e}")

    if st.session_state.historical_fx_rates_df is None or not isinstance(st.session_state.historical_fx_rates_df, pd.DataFrame):
        st.error("Les données de taux de change historiques sont manquantes ou invalides. Impossible de procéder aux conversions.")
        return

    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []
    st.write("DEBUG: Tickers dans le portefeuille", tickers_in_portfolio)

    if not tickers_in_portfolio:
        st.info("Aucun ticker à afficher. Veuillez importer un portefeuille avec des tickers valides.")
        return

    # SÉLECTION DE PÉRIODE AVEC ST.RADIO
    period_options = {
        "1W": timedelta(weeks=1), 
        "1M": timedelta(days=30), 
        "3M": timedelta(days=90),
        "6M": timedelta(days=180), 
        "1Y": timedelta(days=365), 
        "5Y": timedelta(days=365 * 5),
        "10Y": timedelta(days=365 * 10),
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
    st.write(f"DEBUG: Période sélectionnée - Début: {start_date_table}, Fin: {end_date_table}")

    with st.spinner("Récupération et conversion des cours des tickers en cours..."):
        all_ticker_data = []
        fetch_start_date = start_date_table - timedelta(days=max(30, selected_period_td.days // 2))
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)

        valid_tickers = []
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
                    if not numeric_quantities.empty and pd.notnull(numeric_quantities.iloc[0]) and numeric_quantities.iloc[0] > 0:
                        quantity = numeric_quantities.iloc[0]
                    else:
                        st.warning(f"Quantité pour le ticker '{ticker}' est vide, invalide ou zéro. Ignoré.")
                        continue
                else:
                    st.warning(f"Colonne 'Quantité' manquante pour le ticker '{ticker}'. Ignoré.")
                    continue

                if "Facteur_Ajustement_FX" in ticker_row.columns:
                    numeric_fx_factor = pd.to_numeric(ticker_row["Facteur_Ajustement_FX"], errors='coerce')
                    if not numeric_fx_factor.empty and pd.notnull(numeric_fx_factor.iloc[0]) and numeric_fx_factor.iloc[0] != 0:
                        fx_adjustment_factor = numeric_fx_factor.iloc[0]
                    else:
                        st.warning(f"Facteur d'ajustement FX pour '{ticker}' est vide, invalide ou zéro. Utilisation de 1.0.")
                        fx_adjustment_factor = 1.0
                else:
                    fx_adjustment_factor = 1.0

            else:
                st.warning(f"Ticker '{ticker}' non trouvé dans le DataFrame. Ignoré.")
                continue

            # Récupérer les données historiques
            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            st.write(f"DEBUG: Données brutes pour {ticker} (head)")
            st.dataframe(data.head())
            if not data.empty:
                filtered_data = data.dropna().reindex(business_days_for_display).ffill().bfill()
                if filtered_data.empty or filtered_data.eq(0).all().all():
                    st.warning(f"Données historiques pour {ticker} sont vides ou toutes nulles après traitement. Ignoré.")
                    continue
                
                valid_data = False
                for date_idx, price in filtered_data.items():
                    if pd.isna(price) or price == 0:
                        st.warning(f"Prix nul ou manquant pour {ticker} à {date_idx}. Ignoré.")
                        continue
                    fx_key = f"{ticker_devise}{target_currency}"
                    fx_rate_for_date = 1.0
                    if fx_key in st.session_state.historical_fx_rates_df.columns:
                        if date_idx in st.session_state.historical_fx_rates_df.index:
                            fx_rate_for_date = st.session_state.historical_fx_rates_df.loc[date_idx, fx_key]
                    
                    if pd.isna(fx_rate_for_date) or fx_rate_for_date == 0:
                        fx_rate_for_date = 1.0
                        st.warning(f"Taux de change manquant pour {fx_key} à la date {date_idx}. Utilisation de 1.0.")

                    converted_price, _ = convertir(price, ticker_devise, target_currency, fx_rate_for_date, fx_adjustment_factor)
                    st.write(f"DEBUG: Conversion pour {ticker} à {date_idx}: Prix={price}, Devise={ticker_devise}, Taux={fx_rate_for_date}, Facteur FX={fx_adjustment_factor}, Prix converti={converted_price}")
                    if pd.isna(converted_price) or np.isinf(converted_price):
                        st.warning(f"Échec de la conversion pour {ticker} à {date_idx}. Prix: {price}, Taux: {fx_rate_for_date}, Facteur FX: {fx_adjustment_factor}. Ignoré.")
                        continue
                    current_value = converted_price * quantity
                    if current_value == 0 or pd.isna(current_value):
                        st.warning(f"Valeur actuelle nulle pour {ticker} à {date_idx}. Ignoré.")
                        continue

                    all_ticker_data.append({
                        "Date": date_idx,
                        "Ticker": ticker,
                        f"Valeur Actuelle ({target_currency})": current_value
                    })
                    valid_data = True
                if valid_data:
                    valid_tickers.append(ticker)
            else:
                st.warning(f"Aucune donnée historique pour {ticker} sur la période {fetch_start_date} à {end_date_table}. Ignoré.")

        st.write("DEBUG: Tickers valides avec données historiques", valid_tickers)

        df_display_values = pd.DataFrame(all_ticker_data)

        # Log df_display_values for debugging
        st.write("DEBUG: df_display_values head()")
        st.dataframe(df_display_values.head())
        try:
            st.write("DEBUG: df_display_values info()")
            st.write(df_display_values.info())
            st.write("DEBUG: df_display_values describe()")
            st.write(df_display_values.describe())
        except Exception as e:
            st.warning(f"Impossible d'afficher les informations de df_display_values : {e}")

        if not df_display_values.empty and not df_display_values[f"Valeur Actuelle ({target_currency})"].isna().all() and df_display_values[f"Valeur Actuelle ({target_currency})"].ne(0).any():
            df_total_daily_value = df_display_values.groupby('Date')[f"Valeur Actuelle ({target_currency})"].sum().reset_index()
            df_total_daily_value.columns = ['Date', 'Valeur Totale']
            df_total_daily_value['Date'] = pd.to_datetime(df_total_daily_value['Date'], errors='coerce')
            df_total_daily_value['Valeur Totale'] = pd.to_numeric(df_total_daily_value['Valeur Totale'], errors='coerce')
            df_total_daily_value = df_total_daily_value.dropna(subset=['Date', 'Valeur Totale'])
            df_total_daily_value = df_total_daily_value.replace([np.inf, -np.inf], np.nan).dropna()
            df_total_daily_value = df_total_daily_value.sort_values('Date')

            # Log df_total_daily_value for debugging
            st.write("DEBUG: df_total_daily_value head()")
            st.dataframe(df_total_daily_value.head())
            try:
                st.write("DEBUG: df_total_daily_value info()")
                st.write(df_total_daily_value.info())
                st.write("DEBUG: df_total_daily_value describe()")
                st.write(df_total_daily_value.describe())
            except Exception as e:
                st.warning(f"Impossible d'afficher les informations de df_total_daily_value : {e}")

            if not df_total_daily_value.empty and df_total_daily_value['Valeur Totale'].ne(0).any():
                # Graphique 1: Valeur Totale du Portefeuille
                st.markdown("---")
                st.markdown("#### Performance du Portefeuille")
                fig_total = px.line(
                    df_total_daily_value,
                    x="Date",
                    y="Valeur Totale",
                    title=f"Valeur Totale du Portefeuille par Jour ({target_currency})",
                    labels={"Valeur Totale": f"Valeur Totale ({target_currency})", "Date": "Date"},
                    hover_data={"Valeur Totale": lambda x: f"{format_fr(x, 2)}"}
                )
                fig_total.update_layout(hovermode="x unified")
                st.plotly_chart(fig_total, use_container_width=True)

                # Graphique 2: Volatilité Quotidienne
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
                        title=f"Volatilité Annualisée du Portefeuille (Fenêtre de {window_size} jours)",
                        labels={"Volatilité": "Volatilité Annualisée", "Date": "Date"},
                        hover_data={"Volatilité": lambda x: f"{format_fr(x, 4)}"}
                    )
                    fig_volatility.update_layout(hovermode="x unified")
                    st.plotly_chart(fig_volatility, use_container_width=True)
                else:
                    st.info("Pas assez de données pour calculer la volatilité sur la période sélectionnée ou toutes les valeurs de volatilité sont NaN.")

                # Graphique 3: Momentum du Portefeuille
                st.markdown("---")
                st.markdown("#### Momentum du Portefeuille")
                if not df_total_daily_value['Valeur Totale'].empty and df_total_daily_value['Valeur Totale'].iloc[0] != 0:
                    initial_value = df_total_daily_value['Valeur Totale'].iloc[0]
                    df_total_daily_value['Momentum (%)'] = ((df_total_daily_value['Valeur Totale'] / initial_value) - 1) * 100
                    df_total_daily_value['Momentum (%)'] = df_total_daily_value['Momentum (%)'].replace([np.inf, -np.inf], np.nan)
                else:
                    df_total_daily_value['Momentum (%)'] = np.nan
                    st.warning("Valeur initiale du portefeuille nulle ou manquante. Le momentum est défini à NaN.")

                df_total_daily_value['Momentum (%)'] = pd.to_numeric(df_total_daily_value['Momentum (%)'], errors='coerce')

                # Log Momentum DataFrame for debugging
                st.write("DEBUG: df_total_daily_value head() after momentum calculation")
                st.dataframe(df_total_daily_value.head())
                try:
                    st.write("DEBUG: df_total_daily_value info() after momentum calculation")
                    st.write(df_total_daily_value.info())
                except Exception as e:
                    st.warning(f"Impossible d'afficher les informations de df_total_daily_value après calcul du momentum : {e}")

                if not df_total_daily_value['Momentum (%)'].dropna().empty:
                    fig_momentum = px.line(
                        df_total_daily_value.dropna(subset=['Momentum (%)']),
                        x="Date",
                        y="Momentum (%)",
                        title=f"Performance Cumulée du Portefeuille ({target_currency})",
                        labels={"Momentum (%)": "Changement en %", "Date": "Date"},
                        hover_data={"Momentum (%)": lambda x: f"{format_fr(x, 2)}"}
                    )
                    fig_momentum.update_layout(hovermode="x unified")
                    st.plotly_chart(fig_momentum, use_container_width=True)
                else:
                    st.info("Pas assez de données valides pour afficher le graphique de momentum. Vérifiez les données historiques ou la période sélectionnée.")

                # Tableau des valeurs actuelles
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

                # CSS pour aligner les colonnes du tableau
                css_alignments = """
                    [data-testid="stDataFrame"] * { box-sizing: border-box; }
                    [data-testid="stDataFrame"] div[role="grid"] table {
                        width: 100% !important;
                    }
                """
                for i, label in enumerate(df_final_display.columns):
                    col_idx = i + 1
                    if label == "Ticker":
                        css_alignments += f"""
                            [data-testid="stDataFrame"] div[role="grid"] table tbody tr td:nth-child({col_idx}),
                            [data-testid="stDataFrame"] div[role="grid"] table thead tr th:nth-child({col_idx}) {{
                                text-align: left !important;
                                white-space: normal !important;
                                padding-left: 10px !important;
                            }}
                        """
                    else:
                        css_alignments += f"""
                            [data-testid="stDataFrame"] div[role="grid"] table tbody tr td:nth-child({col_idx}),
                            [data-testid="stDataFrame"] div[role="grid"] table thead tr th:nth-child({col_idx}) {{
                                text-align: right !important;
                                white-space: nowrap !important;
                                padding-right: 10px !important;
                            }}
                        """

                st.markdown(f"""
                    <style>
                        {css_alignments}
                    </style>
                """, unsafe_allow_html=True)

                st.markdown("##### Valeur Actuelle du Portefeuille par Ticker (avec conversion)")
                st.dataframe(df_final_display.style.format(format_dict), use_container_width=True, hide_index=True)
            else:
                st.warning("Aucune donnée valide pour afficher les graphiques. Vérifiez les quantités (non nulles et positives), les prix historiques, les taux de change, ou la période sélectionnée.")
        else:
            st.warning("Aucune valeur actuelle valide n'a pu être calculée pour la période sélectionnée. Vérifiez les quantités (non nulles et positives), les tickers, les données historiques, ou les taux de change.")
