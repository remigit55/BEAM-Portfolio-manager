import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
from data_fetcher import fetch_fx_rates
import numpy as np

from period_selector_component import period_selector
from historical_data_fetcher import fetch_stock_history, fetch_historical_fx_rates
from historical_performance_calculator import reconstruct_historical_portfolio_value
from utils import format_fr
from portfolio_display import convertir

def calculate_rsi(data, periods=14):
    """
    Calcule le RSI (Relative Strength Index) sur une série de données.
    
    Args:
        data (pd.Series): Série de données (par exemple, Valeur Totale).
        periods (int): Période pour le calcul du RSI (défaut : 14).
    
    Returns:
        pd.Series: RSI calculé.
    """
    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=periods, min_periods=1).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=periods, min_periods=1).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # Remplir NaN avec 50 pour éviter des erreurs initiales

def calculate_macd(data, fast_period=12, slow_period=26, signal_period=9):
    """
    Calcule le MACD (Moving Average Convergence Divergence).
    
    Args:
        data (pd.Series): Série de données (par exemple, Valeur Totale).
        fast_period (int): Période pour l'EMA rapide (défaut : 12).
        slow_period (int): Période pour l'EMA lente (défaut : 26).
        signal_period (int): Période pour la ligne de signal (défaut : 9).
    
    Returns:
        tuple: (macd, signal, histogramme)
    """
    ema_fast = data.ewm(span=fast_period, adjust=False).mean()
    ema_slow = data.ewm(span=slow_period, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def convertir_valeur_performance(val, source_devise, devise_cible, fx_rates_or_scalar, fx_adjustment_factor=1.0):
    """
    Applique le facteur d'ajustement sur la valeur (ex: GBp -> GBP = x0.01),
    puis applique le taux de conversion.
    
    Args:
        val (float): Valeur à convertir.
        source_devise (str): Devise source.
        devise_cible (str): Devise cible.
        fx_rates_or_scalar (dict/float): Taux de change ou dictionnaire de taux.
        fx_adjustment_factor (float): Facteur d'ajustement (par défaut 1.0).
    
    Returns:
        tuple: (Valeur convertie, Taux utilisé).
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
        taux_scalar = 1.0

    if pd.isna(taux_scalar) or taux_scalar == 0:
        return val, np.nan

    valeur_ajustee = val * fx_adjustment_factor
    return valeur_ajustee * taux_scalar, taux_scalar

def display_performance_history():  
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        return

    df_current_portfolio = st.session_state.df.copy()
    
    # Initialisation des colonnes et gestion de GBp
    if "Devise" in df_current_portfolio.columns:
        df_current_portfolio["Devise"] = df_current_portfolio["Devise"].astype(str).str.strip()
        df_current_portfolio["Devise_Originale"] = df_current_portfolio["Devise"]
        df_current_portfolio["Facteur_Ajustement_FX"] = 1.0
        df_current_portfolio.loc[
            df_current_portfolio["Devise_Originale"].str.strip().str.upper() == "GBP",
            "Facteur_Ajustement_FX"
        ] = 0.01
    
    # Récupération de la devise cible
    target_currency = st.session_state.get("devise_cible", "EUR")
    
    # Récupération des taux de change
    devises_uniques_df = df_current_portfolio["Devise"].dropna().unique().tolist()
    devises_a_fetch = list(set([target_currency] + devises_uniques_df))
    st.session_state.fx_rates = fetch_fx_rates(target_currency)
    fx_rates = st.session_state.fx_rates
    
    # Tickers à afficher
    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []

    if not tickers_in_portfolio:
        return

    # Sélection de période
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
        fetch_start_date = start_date_table - timedelta(days=3*365)  # Charger 3 ans supplémentaires
        business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)
        all_business_days = pd.bdate_range(start=fetch_start_date, end=end_date_table)

        for ticker in tickers_in_portfolio:
            ticker_devise = target_currency
            quantity = 0.0
            fx_adjustment_factor = 1.0

            ticker_row = df_current_portfolio[df_current_portfolio["Ticker"] == ticker]
            if not ticker_row.empty:
                if "Devise_Originale" in ticker_row.columns and pd.notnull(ticker_row["Devise_Originale"].iloc[0]):
                    ticker_devise = str(ticker_row["Devise_Originale"].iloc[0]).strip().upper()
                    if ticker_devise == "GBP":
                        fx_adjustment_factor = 0.01
                        ticker_devise = "GBP"
                if "Quantité" in ticker_row.columns:
                    quantity = pd.to_numeric(ticker_row["Quantité"], errors='coerce').iloc[0] or 0.0

            data = fetch_stock_history(ticker, fetch_start_date, end_date_table)
            if data.empty:
                # Si aucune donnée, créer un DataFrame avec des prix à 0
                data = pd.Series(0.0, index=all_business_days)
            else:
                # Réindexer pour inclure toutes les dates, remplir les valeurs manquantes
                data = data.reindex(all_business_days).ffill().bfill()

            for date_idx, price in data.items():
                fx_key = ticker_devise
                fx_rate_for_date = fx_rates.get(fx_key, 1.0)
                converted_price, taux_scalar = convertir_valeur_performance(price, ticker_devise, target_currency, fx_rate_for_date, fx_adjustment_factor)
                all_ticker_data.append({
                    "Date": date_idx,
                    "Ticker": ticker,
                    f"Valeur Actuelle ({target_currency})": converted_price * quantity
                })

        df_display_values = pd.DataFrame(all_ticker_data)
        
        if not df_display_values.empty:
            # Calculer la valeur totale sur toutes les données disponibles
            df_total_daily_value = df_display_values.groupby('Date')[f"Valeur Actuelle ({target_currency})"].sum().reset_index()
            df_total_daily_value.columns = ['Date', 'Valeur Totale']
            df_total_daily_value['Date'] = pd.to_datetime(df_total_daily_value['Date'])
            df_total_daily_value = df_total_daily_value.sort_values('Date')

            # Calcul des moyennes mobiles pour Valeur Totale
            df_total_daily_value['MA50'] = df_total_daily_value['Valeur Totale'].rolling(window=50, min_periods=1).mean()
            df_total_daily_value['MA200'] = df_total_daily_value['Valeur Totale'].rolling(window=200, min_periods=1).mean()

            # Calcul du RSI et du MACD
            df_total_daily_value['RSI'] = calculate_rsi(df_total_daily_value['Valeur Totale'], periods=14)
            df_total_daily_value['MACD'], df_total_daily_value['MACD_Signal'], df_total_daily_value['MACD_Hist'] = calculate_macd(
                df_total_daily_value['Valeur Totale'], fast_period=12, slow_period=26, signal_period=9
            )

            # Vérifier si MA200 est calculable
            min_date = df_total_daily_value['Date'].min()
            if pd.notna(min_date) and min_date > pd.Timestamp(end_date_table - timedelta(days=200)):
                st.warning("⚠️ Données historiques insuffisantes pour calculer MA200 sur l'ensemble de la période. Essayez une période plus récente ou vérifiez les données des tickers.")

            # Filtrer pour l'affichage
            df_total_daily_value_display = df_total_daily_value[
                (df_total_daily_value['Date'] >= pd.Timestamp(start_date_table)) &
                (df_total_daily_value['Date'] <= pd.Timestamp(end_date_table))
            ]

            st.markdown("---")
            st.markdown("#### Performance du Portefeuille")
            # Créer une figure avec sous-graphiques
            fig_total = make_subplots(
                rows=3, cols=1,
                row_heights=[0.6, 0.2, 0.2],
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=[
                    "",
                    "",
                    ""
                ]
            )

            # Graphique principal : Valeur Totale, MA50, MA200
            fig_total.add_trace(
                go.Scatter(
                    x=df_total_daily_value_display['Date'],
                    y=df_total_daily_value_display['Valeur Totale'],
                    mode='lines',
                    name=f'Valeur Totale ({target_currency})',
                    line=dict(color='#363636'),
                    hovertemplate='%{x|%d/%m/%Y}<br>Valeur: %{y:.2f}<extra></extra>'
                ),
                row=1, col=1
            )
            fig_total.add_trace(
                go.Scatter(
                    x=df_total_daily_value_display['Date'],
                    y=df_total_daily_value_display['MA50'],
                    mode='lines',
                    name='MA50',
                    line=dict(color='orange', dash='dash'),
                    hovertemplate='%{x|%d/%m/%Y}<br>MA50: %{y:.2f}<extra></extra>'
                ),
                row=1, col=1
            )
            fig_total.add_trace(
                go.Scatter(
                    x=df_total_daily_value_display['Date'],
                    y=df_total_daily_value_display['MA200'],
                    mode='lines',
                    name='MA200',
                    line=dict(color='green', dash='dash'),
                    hovertemplate='%{x|%d/%m/%Y}<br>MA200: %{y:.2f}<extra></extra>'
                ),
                row=1, col=1
            )

            # Sous-graphique RSI
            fig_total.add_trace(
                go.Scatter(
                    x=df_total_daily_value_display['Date'],
                    y=df_total_daily_value_display['RSI'],
                    mode='lines',
                    name='RSI (14)',
                    line=dict(color='#363636'),
                    hovertemplate='%{x|%d/%m/%Y}<br>RSI: %{y:.2f}<extra></extra>'
                ),
                row=2, col=1
            )
            fig_total.add_hline(
                y=70, line_dash="dash", line_color="grey", annotation_text="Surachat (70)",
                annotation_position="right", row=2, col=1
            )
            fig_total.add_hline(
                y=30, line_dash="dash", line_color="grey", annotation_text="Survente (30)",
                annotation_position="right", row=2, col=1
            )

            # Sous-graphique MACD
            fig_total.add_trace(
                go.Scatter(
                    x=df_total_daily_value_display['Date'],
                    y=df_total_daily_value_display['MACD'],
                    mode='lines',
                    name='MACD',
                    line=dict(color='#363636'),
                    hovertemplate='%{x|%d/%m/%Y}<br>MACD: %{y:.2f}<extra></extra>'
                ),
                row=3, col=1
            )
            fig_total.add_trace(
                go.Scatter(
                    x=df_total_daily_value_display['Date'],
                    y=df_total_daily_value_display['MACD_Signal'],
                    mode='lines',
                    name='Signal',
                    line=dict(color='#A49B6D'),
                    hovertemplate='%{x|%d/%m/%Y}<br>Signal: %{y:.2f}<extra></extra>'
                ),
                row=3, col=1
            )
            fig_total.add_trace(
                go.Bar(
                    x=df_total_daily_value_display['Date'],
                    y=df_total_daily_value_display['MACD_Hist'],
                    name='Histogramme MACD',
                    marker_color=df_total_daily_value_display['MACD_Hist'].apply(lambda x: 'green' if x >= 0 else 'red'),
                    hovertemplate='%{x|%d/%m/%Y}<br>Hist: %{y:.2f}<extra></extra>'
                ),
                row=3, col=1
            )

            # Mise à jour du layout
            fig_total.update_layout(
                height=800,  # Augmenter la hauteur pour accueillir les sous-graphiques
                showlegend=True,
                hovermode="x unified",
                title=f"Valeur du Portefeuille | par jour en {target_currency}",
                xaxis_title="",
                yaxis_title=f"Valeur Totale ({target_currency})",
                yaxis2_title="RSI",
                yaxis3_title="MACD",
                xaxis3_title="",
                title_x=0.0,
                margin=dict(t=50, b=50)
            )
            fig_total.update_yaxes(range=[0, 100], row=2, col=1)  # RSI entre 0 et 100
            st.plotly_chart(fig_total, use_container_width=True)

            # Ajout des indicateurs Plus Haut, Plus Bas, Ouverture, Valeur Moyenne, Clôture
            if not df_total_daily_value_display.empty:
                high_value = df_total_daily_value_display['Valeur Totale'].max()
                low_value = df_total_daily_value_display['Valeur Totale'].min()
                open_value = df_total_daily_value_display.loc[df_total_daily_value_display['Date'] == df_total_daily_value_display['Date'].min(), 'Valeur Totale'].iloc[0] if not df_total_daily_value_display.empty else np.nan
                mean_value = df_total_daily_value_display['Valeur Totale'].mean()
                close_value = df_total_daily_value_display.loc[df_total_daily_value_display['Date'] == df_total_daily_value_display['Date'].max(), 'Valeur Totale'].iloc[0] if not df_total_daily_value_display.empty else np.nan
                # Calcul de la variation en pourcentage pour Clôture
                if pd.notna(open_value) and pd.notna(close_value) and open_value != 0:
                    percentage_change = ((close_value - open_value) / open_value) * 100
                    delta_str = f"{percentage_change:+.2f}%"
                else:
                    delta_str = "N/A"

                cols = st.columns(5)
                with cols[0]:
                    st.metric(label="Ouverture", value=f"{format_fr(open_value, 0)} {target_currency}")
                with cols[1]:
                    st.metric(label="Plus Bas", value=f"{format_fr(low_value, 0)} {target_currency}")
                with cols[2]:
                    st.metric(label="Valeur Moyenne", value=f"{format_fr(mean_value, 0)} {target_currency}")
                with cols[3]:
                    st.metric(label="Plus Haut", value=f"{format_fr(high_value, 0)} {target_currency}")
                with cols[4]:
                    st.metric(label="Clôture", value=f"{format_fr(close_value, 0)} {target_currency}", delta=delta_str)
            else:
                st.warning("⚠️ Aucune donnée disponible pour calculer les indicateurs sur la période sélectionnée.")

            # Graphique : Volatilité avec MA50, MA200 et objectif de volatilité
            # st.markdown("---")
            # st.markdown("#### Volatilité Quotidienne du Portefeuille")
            # Utiliser la valeur de target_volatility définie dans parametres.py
            target_volatility = st.session_state.get("target_volatility", 0.15)

            df_total_daily_value['Rendement Quotidien'] = df_total_daily_value['Valeur Totale'].pct_change()
            window_size = 20
            df_total_daily_value['Volatilité'] = df_total_daily_value['Rendement Quotidien'].rolling(window=window_size, min_periods=1).std() * (252**0.5)
            df_total_daily_value['Volatilité_MA50'] = df_total_daily_value['Volatilité'].rolling(window=50, min_periods=1).mean()
            df_total_daily_value['Volatilité_MA200'] = df_total_daily_value['Volatilité'].rolling(window=200, min_periods=1).mean()

            if not df_total_daily_value['Volatilité'].dropna().empty:
                df_volatility_display = df_total_daily_value[
                    (df_total_daily_value['Date'] >= pd.Timestamp(start_date_table)) &
                    (df_total_daily_value['Date'] <= pd.Timestamp(end_date_table))
                ]
                fig_volatility = go.Figure()
                fig_volatility.add_trace(go.Scatter(
                    x=df_volatility_display['Date'],
                    y=df_volatility_display['Volatilité'],
                    mode='lines',
                    name='Volatilité Annualisée',
                    line=dict(color='#363636'),
                    hovertemplate='%{x|%d/%m/%Y}<br>Volatilité: %{y:.4f}<extra></extra>'
                ))
                fig_volatility.add_trace(go.Scatter(
                    x=df_volatility_display['Date'],
                    y=df_volatility_display['Volatilité_MA50'],
                    mode='lines',
                    name='MA50 (Volatilité)',
                    line=dict(color='orange', dash='dash'),
                    hovertemplate='%{x|%d/%m/%Y}<br>MA50: %{y:.4f}<extra></extra>'
                ))
                fig_volatility.add_trace(go.Scatter(
                    x=df_volatility_display['Date'],
                    y=df_volatility_display['Volatilité_MA200'],
                    mode='lines',
                    name='MA200 (Volatilité)',
                    line=dict(color='green', dash='dash'),
                    hovertemplate='%{x|%d/%m/%Y}<br>MA200: %{y:.4f}<extra></extra>'
                ))
                fig_volatility.add_trace(go.Scatter(
                    x=[df_volatility_display['Date'].min(), df_volatility_display['Date'].max()],
                    y=[target_volatility, target_volatility],
                    mode='lines',
                    name='Objectif Volatilité',
                    line=dict(color='red', dash='dot'),
                    hovertemplate='Objectif Volatilité: %{y:.4f}<extra></extra>'
                ))
                fig_volatility.update_layout(
                    title=f"Volatilité | Fenêtre de {window_size} jours",
                    xaxis_title="",
                    yaxis_title="Volatilité Annualisée",
                    hovermode="x unified",
                    showlegend=True
                )
                st.plotly_chart(fig_volatility, use_container_width=True)

            # Graphique : Z-score (Momentum) avec Z-score_70 et Z-score_36mois
            # st.markdown("---")
            # st.markdown("#### Momentum du Portefeuille")
            # Calcul du Z-score pour une fenêtre de 70 jours
            df_total_daily_value['MA_Z_70'] = df_total_daily_value['Valeur Totale'].rolling(window=70, min_periods=1).mean()
            df_total_daily_value['STD_Z_70'] = df_total_daily_value['Valeur Totale'].rolling(window=70, min_periods=1).std()
            df_total_daily_value['Z-score_70'] = (
                (df_total_daily_value['Valeur Totale'] - df_total_daily_value['MA_Z_70']) / 
                df_total_daily_value['STD_Z_70']
            ).fillna(0)
            # Calcul du Z-score pour une fenêtre de 36 mois (~756 jours ouvrables)
            z_score_36mois_window = 36 * 21  # 21 jours ouvrables par mois
            df_total_daily_value['MA_Z_36mois'] = df_total_daily_value['Valeur Totale'].rolling(window=z_score_36mois_window, min_periods=1).mean()
            df_total_daily_value['STD_Z_36mois'] = df_total_daily_value['Valeur Totale'].rolling(window=z_score_36mois_window, min_periods=1).std()
            df_total_daily_value['Z-score_36mois'] = (
                (df_total_daily_value['Valeur Totale'] - df_total_daily_value['MA_Z_36mois']) / 
                df_total_daily_value['STD_Z_36mois']
            ).fillna(0)

            # Vérifier si les données couvrent au moins 36 mois
            min_date_z = df_total_daily_value['Date'].min()
            if pd.notna(min_date_z) and min_date_z > pd.Timestamp(end_date_table - timedelta(days=3*365)):
                st.warning("⚠️ Données historiques insuffisantes pour calculer le Z-score sur 36 mois. Essayez une période plus récente ou vérifiez les données des tickers.")

            if not df_total_daily_value['Z-score_70'].dropna().empty and not df_total_daily_value['Z-score_36mois'].dropna().empty:
                df_z_score_display = df_total_daily_value[
                    (df_total_daily_value['Date'] >= pd.Timestamp(start_date_table)) &
                    (df_total_daily_value['Date'] <= pd.Timestamp(end_date_table))
                ]
                fig_z_score = go.Figure()
                fig_z_score.add_trace(go.Scatter(
                    x=df_z_score_display['Date'],
                    y=df_z_score_display['Z-score_70'],
                    mode='lines',
                    name='Z-score (70 jours)',
                    line=dict(color='#363636'),
                    hovertemplate='%{x|%d/%m/%Y}<br>Z-score (70 jours): %{y:.2f}<extra></extra>'
                ))
                fig_z_score.add_trace(go.Scatter(
                    x=df_z_score_display['Date'],
                    y=df_z_score_display['Z-score_36mois'],
                    mode='lines',
                    name='Z-score (36 mois)',
                    line=dict(color='green'),
                    hovertemplate='%{x|%d/%m/%Y}<br>Z-score (36 mois): %{y:.2f}<extra></extra>'
                ))
                fig_z_score.update_layout(
                    title="Momentum | Z-scores sur 70 jours et 36 mois",
                    xaxis_title="",
                    yaxis_title="Z-score",
                    hovermode="x unified",
                    showlegend=True
                )
                st.plotly_chart(fig_z_score, use_container_width=True)

                # Ajout des indicateurs Signal, Action, Justification
                latest_z_score = df_z_score_display[df_z_score_display['Date'] == df_z_score_display['Date'].max()]
                if not latest_z_score.empty:
                    z_score_70 = latest_z_score['Z-score_70'].iloc[0]
                    z_score_36mois = latest_z_score['Z-score_36mois'].iloc[0]

                    # Déterminer le Signal
                    if z_score_70 > 1 and z_score_36mois > 0:
                        signal = "Haussier"
                        action = "Acheter"
                        justification = "Court terme fort avec tendance long terme positive"
                    elif z_score_70 < -1 and z_score_36mois < 0:
                        signal = "Baissier"
                        action = "Vendre"
                        justification = "Court terme faible avec tendance long terme négative"
                    else:
                        signal = "Neutre"
                        action = "Conserver"
                        justification = "Pas d'alignement clair pour une action décisive"

                    cols = st.columns([1, 1, 3])
                    with cols[0]:
                        st.metric(label="Signal", value=signal)
                    with cols[1]:
                        st.metric(label="Action", value=action)
                    with cols[2]:
                        st.metric(label="Justification", value=justification)
            else:
                st.warning("⚠️ Aucune donnée disponible pour calculer les Z-scores sur la période sélectionnée.")

            # Tableau des valeurs actuelles par ticker
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

            st.markdown(f"##### Valeur Actuelle du Portefeuille | en {target_currency}")
            st.dataframe(df_final_display.style.format(format_dict), use_container_width=True, hide_index=True)
