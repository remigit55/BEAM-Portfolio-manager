import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
import numpy as np
import logging
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from period_selector_component import period_selector
    from historical_data_fetcher import fetch_stock_history, fetch_historical_fx_rates
    from historical_performance_calculator import reconstruct_historical_portfolio_value
    from utils import format_fr
    from portfolio_display import convertir
except ImportError as e:
    logger.error(f"Import error in performance.py: {str(e)}")
    st.error(f"Import error in performance.py: {str(e)}")
    raise

def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=periods, min_periods=1).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=periods, min_periods=1).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_macd(data, fast_period=12, slow_period=26, signal_period=9):
    ema_fast = data.ewm(span=fast_period, adjust=False).mean()
    ema_slow = data.ewm(span=slow_period, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def calculate_bollinger_bands(data, periods=20, num_std=2):
    sma = data.rolling(window=periods, min_periods=1).mean()
    std = data.rolling(window=periods, min_periods=1).std()
    upper_band = sma + num_std * std
    lower_band = sma - num_std * std
    return sma, upper_band, lower_band

def convertir_valeur_performance(val, source_devise, devise_cible, fx_rates, date=None, fx_adjustment_factor=1.0):
    if pd.isnull(val):
        logger.warning(f"Null value for conversion: {val}")
        return np.nan, np.nan
    source_devise = str(source_devise).strip().upper()
    devise_cible = str(devise_cible).strip().upper()
    if source_devise == devise_cible:
        return val * fx_adjustment_factor, 1.0
    
    fx_key = f"{source_devise}{devise_cible}"
    taux_scalar = np.nan

    if isinstance(fx_rates, dict) and date is not None:
        date_key = pd.Timestamp(date).date()
        if date_key in fx_rates and fx_key in fx_rates[date_key]:
            taux_scalar = float(fx_rates[date_key][fx_key])
            logger.debug(f"Found rate for {fx_key} on {date_key}: {taux_scalar}")
        else:
            logger.warning(f"No rate for {fx_key} on {date_key}. Using rate 1.0.")
            st.warning(f"No exchange rate for {fx_key} on {date_key}. Values may remain in {source_devise}.")
            taux_scalar = 1.0
    elif isinstance(fx_rates, (float, int, np.floating, np.integer)):
        taux_scalar = float(fx_rates)
        logger.debug(f"Using scalar rate for {fx_key}: {taux_scalar}")
    else:
        logger.warning(f"Invalid exchange rate format for {fx_key}. Using rate 1.0.")
        st.warning(f"Invalid exchange rate format for {fx_key}. Values may remain in {source_devise}.")
        taux_scalar = 1.0

    if pd.isna(taux_scalar) or taux_scalar == 0:
        logger.warning(f"Invalid or zero rate for {fx_key} on {date_key}. No conversion applied.")
        return val, np.nan
    
    valeur_ajustee = val * fx_adjustment_factor
    return valeur_ajustee * taux_scalar, taux_scalar

def display_performance_history():
    logger.info("Starting display_performance_history")
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        logger.warning("No portfolio data available")
        st.warning("No portfolio data available.")
        return

    df_current_portfolio = st.session_state.df.copy()
    logger.info(f"Portfolio columns: {list(df_current_portfolio.columns)}")
    
    # Check for required columns
    required_columns = ['Ticker']
    currency_col = None
    quantity_col = None
    for col in ['Currency', 'Devise']:
        if col in df_current_portfolio.columns:
            currency_col = col
            break
    for col in ['Quantity', 'Quantite', 'Quantité']:
        if col in df_current_portfolio.columns:
            quantity_col = col
            break
    if not all(col in df_current_portfolio.columns for col in required_columns) or currency_col is None or quantity_col is None:
        logger.error(f"Missing required columns. Found: {list(df_current_portfolio.columns)}, Required: {required_columns + ['Currency/Devise', 'Quantity/Quantite']}")
        st.error(f"Missing required columns in portfolio data. Found: {list(df_current_portfolio.columns)}, Required: {required_columns + ['Currency/Devise', 'Quantity/Quantite']}")
        return

    df_current_portfolio[currency_col] = df_current_portfolio[currency_col].astype(str).str.strip()
    df_current_portfolio["Currency_Original"] = df_current_portfolio[currency_col]
    df_current_portfolio["FX_Adjustment_Factor"] = 1.0
    df_current_portfolio.loc[
        df_current_portfolio["Currency_Original"].str.strip().str.upper() == "GBP",
        "FX_Adjustment_Factor"
    ] = 0.01

    target_currency = st.session_state.get("devise_cible", "EUR").upper()
    logger.info(f"Target currency: {target_currency}")
    devises_uniques_df = df_current_portfolio[currency_col].dropna().unique().tolist()
    devises_a_fetch = list(set([target_currency] + devises_uniques_df))
    logger.info(f"Currencies to fetch: {devises_a_fetch}")
    
    period_options = {
        "1W": timedelta(weeks=1), "1M": timedelta(days=30), "3M": timedelta(days=90),
        "6M": timedelta(days=180), "1Y": timedelta(days=365),
        "5Y": timedelta(days=365 * 5), "10Y": timedelta(days=365 * 10),
        "20Y": timedelta(days=365 * 20)
    }
    period_labels = list(period_options.keys())
    current_selected_label = st.session_state.get("selected_ticker_table_period_label", "1Y")
    if current_selected_label not in period_labels:
        current_selected_label = "1W"
    default_period_index = period_labels.index(current_selected_label)
    selected_label = st.radio(
        "Select period:",
        period_labels,
        index=default_period_index,
        key="selected_ticker_table_period_radio",
        horizontal=True
    )
    st.session_state.selected_ticker_table_period_label = selected_label
    selected_period_td = period_options[selected_label]
    end_date_table = datetime.now().date()
    start_date_table = end_date_table - selected_period_td
    fetch_start_date = start_date_table - timedelta(days=min(200, selected_period_td.days)) if selected_period_td.days > 365 else start_date_table

    interval = "1wk" if selected_period_td.days > 365 else "1d"
    cache_key = f"fx_rates_{'_'.join(sorted(devises_a_fetch))}_{target_currency}_{fetch_start_date}_{end_date_table}_{interval}"
    if cache_key not in st.session_state:
        with st.spinner("Fetching historical exchange rates..."):
            try:
                historical_fx_rates = fetch_historical_fx_rates(devises_a_fetch, target_currency, fetch_start_date, end_date_table, interval=interval)
                if not historical_fx_rates:
                    logger.error("No exchange rates fetched. Conversion to target currency may fail.")
                    st.error(f"No exchange rates available for {devises_a_fetch} to {target_currency}. Values may remain in original currencies.")
                st.session_state[cache_key] = historical_fx_rates
                logger.info(f"Cached FX rates for key: {cache_key}")
                sample_rates = {k: v for k, v in historical_fx_rates.items() if k in list(historical_fx_rates.keys())[:5]}
                st.write("DEBUG: Historical FX rates sample:", sample_rates)
                logger.info(f"Sample FX rates: {sample_rates}")
            except Exception as e:
                logger.error(f"Error fetching exchange rates: {str(e)}")
                st.error(f"Error fetching exchange rates: {str(e)}")
                historical_fx_rates = {}
                st.session_state[cache_key] = historical_fx_rates
    else:
        logger.info(f"Using cached FX rates for key: {cache_key}")
    historical_fx_rates = st.session_state[cache_key]

    tickers_in_portfolio = sorted(df_current_portfolio['Ticker'].dropna().unique().tolist()) if "Ticker" in df_current_portfolio.columns else []
    if not tickers_in_portfolio:
        logger.warning("No tickers found in portfolio")
        st.warning("No tickers found in portfolio.")
        return

    data_cache_key = f"portfolio_data_{'_'.join(sorted(tickers_in_portfolio))}_{target_currency}_{fetch_start_date}_{end_date_table}_{interval}"
    if data_cache_key not in st.session_state:
        with st.spinner("Fetching and converting prices..."):
            try:
                all_ticker_data = []
                business_days_for_display = pd.bdate_range(start=start_date_table, end=end_date_table)
                all_business_days = pd.bdate_range(start=fetch_start_date, end=end_date_table)

                # Parallel fetch stock prices
                def fetch_stock(ticker, start, end):
                    ticker_cache_key = f"stock_{ticker}_{start}_{end}"
                    if ticker_cache_key not in st.session_state:
                        data = fetch_stock_history(ticker, start, end)
                        if data.empty:
                            logger.warning(f"No data for ticker {ticker}. Using zero values.")
                            data = pd.Series(0.0, index=all_business_days)
                        else:
                            data = data.reindex(all_business_days).ffill().bfill()
                        st.session_state[ticker_cache_key] = data
                    return ticker, st.session_state[ticker_cache_key]

                with ThreadPoolExecutor(max_workers=5) as executor:
                    results = executor.map(lambda t: fetch_stock(t, fetch_start_date, end_date_table), tickers_in_portfolio)
                
                for ticker, data in results:
                    ticker_row = df_current_portfolio[df_current_portfolio["Ticker"] == ticker]
                    if ticker_row.empty:
                        continue
                    ticker_devise = str(ticker_row[currency_col].iloc[0]).strip().upper()
                    quantity = pd.to_numeric(ticker_row[quantity_col].iloc[0], errors='coerce') or 0.0
                    fx_adjustment_factor = ticker_row['FX_Adjustment_Factor'].iloc[0]
                    logger.debug(f"Processing ticker {ticker} in {ticker_devise} with quantity {quantity}")
                    
                    for date_idx, price in data.items():
                        if pd.Timestamp(date_idx).date() < start_date_table:
                            continue
                        converted_price, taux_scalar = convertir_valeur_performance(
                            price, ticker_devise, target_currency, historical_fx_rates, date=date_idx, fx_adjustment_factor=fx_adjustment_factor
                        )
                        all_ticker_data.append({
                            "Date": date_idx,
                            "Ticker": ticker,
                            f"Current Value ({target_currency})": converted_price * quantity
                        })

                df_display_values = pd.DataFrame(all_ticker_data)
                if df_display_values.empty:
                    logger.warning("No portfolio data processed")
                    st.warning("No portfolio data processed. Check ticker data or exchange rates.")
                st.session_state[data_cache_key] = df_display_values
                logger.info(f"Cached portfolio data for key: {data_cache_key}")
            except Exception as e:
                logger.error(f"Error fetching portfolio data: {str(e)}")
                st.error(f"Error fetching portfolio data: {str(e)}")
                return
    else:
        logger.info(f"Using cached portfolio data for key: {data_cache_key}")
    df_display_values = st.session_state[data_cache_key]

    if not df_display_values.empty:
        # Downsample for long periods
        if selected_period_td.days > 365 * 5:
            df_display_values = df_display_values[df_display_values['Date'].dt.dayofweek == 0]
        elif selected_period_td.days > 365 * 10:
            df_display_values = df_display_values[df_display_values['Date'].dt.day == 1]
        df_total_daily_value = df_display_values.groupby('Date')[f"Current Value ({target_currency})"].sum().reset_index()
        df_total_daily_value.columns = ['Date', 'Total Value']
        df_total_daily_value['Date'] = pd.to_datetime(df_total_daily_value['Date'])
        df_total_daily_value = df_total_daily_value.sort_values('Date')
        df_total_daily_value['MA50'] = df_total_daily_value['Total Value'].rolling(window=50, min_periods=1).mean()
        df_total_daily_value['MA200'] = df_total_daily_value['Total Value'].rolling(window=200, min_periods=1).mean()
        df_total_daily_value['RSI'] = calculate_rsi(df_total_daily_value['Total Value'], periods=14)
        df_total_daily_value['MACD'], df_total_daily_value['MACD_Signal'], df_total_daily_value['MACD_Hist'] = calculate_macd(
            df_total_daily_value['Total Value'], fast_period=12, slow_period=26, signal_period=9
        )
        df_total_daily_value['BB_SMA20'], df_total_daily_value['BB_Upper'], df_total_daily_value['BB_Lower'] = calculate_bollinger_bands(
            df_total_daily_value['Total Value'], periods=20, num_std=2
        )
        min_date = df_total_daily_value['Date'].min()
        if pd.notna(min_date) and min_date > pd.Timestamp(end_date_table - timedelta(days=200)):
            st.warning("Insufficient historical data for MA200 calculation.")
        
        df_total_daily_value_display = df_total_daily_value[
            (df_total_daily_value['Date'] >= pd.Timestamp(start_date_table)) &
            (df_total_daily_value['Date'] <= pd.Timestamp(end_date_table))
        ]
        
        st.markdown("#### Portfolio Performance")
        fig_total = make_subplots(
            rows=3, cols=1,
            row_heights=[0.6, 0.2, 0.2],
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=["", "", ""]
        )
        fig_total.add_trace(
            go.Scatter(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['Total Value'],
                mode='lines',
                name=f'Total Value ({target_currency})',
                line=dict(color='#363636', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>Value: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        fig_total.add_trace(
            go.Scatter(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['MA50'],
                mode='lines',
                name='MA50',
                line=dict(color='orange', dash='dash', width=1),
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
                line=dict(color='green', dash='dash', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>MA200: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        fig_total.add_trace(
            go.Scatter(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['BB_Upper'],
                mode='lines',
                name='Upper Band (BB)',
                line=dict(color='#A9A9A9', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>Upper Band: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        fig_total.add_trace(
            go.Scatter(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['BB_Lower'],
                mode='lines',
                name='Lower Band (BB)',
                line=dict(color='#A9A9A9', width=1),
                fill='tonexty',
                fillcolor='rgba(169, 169, 169, 0.2)',
                hovertemplate='%{x|%d/%m/%Y}<br>Lower Band: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        fig_total.add_trace(
            go.Scatter(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['BB_SMA20'],
                mode='lines',
                name='SMA20 (BB)',
                line=dict(color='#808080', width=1, dash='dot'),
                hovertemplate='%{x|%d/%m/%Y}<br>SMA20: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        fig_total.add_trace(
            go.Scatter(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['RSI'],
                mode='lines',
                name='RSI (14)',
                line=dict(color='#363636', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>RSI: %{y:.2f}<extra></extra>'
            ),
            row=2, col=1
        )
        fig_total.add_hline(
            y=70, line_dash="dash", line_color="grey", line_width=1, annotation_text="Overbought (70)",
            annotation_position="right", row=2, col=1
        )
        fig_total.add_hline(
            y=30, line_dash="dash", line_color="grey", line_width=1, annotation_text="Oversold (30)",
            annotation_position="right", row=2, col=1
        )
        fig_total.add_trace(
            go.Scatter(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['MACD'],
                mode='lines',
                name='MACD',
                line=dict(color='#363636', width=1),
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
                line=dict(color='#A49B6D', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>Signal: %{y:.2f}<extra></extra>'
            ),
            row=3, col=1
        )
        fig_total.add_trace(
            go.Bar(
                x=df_total_daily_value_display['Date'],
                y=df_total_daily_value_display['MACD_Hist'],
                name='MACD Histogram',
                marker_color=df_total_daily_value_display['MACD_Hist'].apply(lambda x: 'green' if x >= 0 else 'red'),
                hovertemplate='%{x|%d/%m/%Y}<br>Hist: %{y:.2f}<extra></extra>'
            ),
            row=3, col=1
        )
        fig_total.update_layout(
            height=800,
            showlegend=True,
            hovermode="x unified",
            title=f"Portfolio Value | Daily in {target_currency}",
            xaxis_title="",
            yaxis_title="Value",
            yaxis2_title="RSI",
            yaxis3_title="MACD",
            xaxis3_title="",
            title_x=0.0,
            margin=dict(t=50, b=50)
        )
        fig_total.update_yaxes(range=[0, 100], row=2, col=1)
        st.plotly_chart(fig_total, use_container_width=True)
        
        if not df_total_daily_value_display.empty:
            high_value = df_total_daily_value_display['Total Value'].max()
            low_value = df_total_daily_value_display['Total Value'].min()
            open_value = df_total_daily_value_display.loc[df_total_daily_value_display['Date'] == df_total_daily_value_display['Date'].min(), 'Total Value'].iloc[0]
            mean_value = df_total_daily_value_display['Total Value'].mean()
            close_value = df_total_daily_value_display.loc[df_total_daily_value_display['Date'] == df_total_daily_value_display['Date'].max(), 'Total Value'].iloc[0]
            if pd.notna(open_value) and pd.notna(close_value) and open_value != 0:
                percentage_change = ((close_value - open_value) / open_value) * 100
                delta_str = f"{percentage_change:+.2f}%"
            else:
                delta_str = "N/A"
            cols = st.columns(5)
            with cols[0]:
                st.metric(label="Open", value=f"{format_fr(open_value, 0)} {target_currency}")
            with cols[1]:
                st.metric(label="Low", value=f"{format_fr(low_value, 0)} {target_currency}")
            with cols[2]:
                st.metric(label="Average Value", value=f"{format_fr(mean_value, 0)} {target_currency}")
            with cols[3]:
                st.metric(label="High", value=f"{format_fr(high_value, 0)} {target_currency}")
            with cols[4]:
                st.metric(label="Close", value=f"{format_fr(close_value, 0)} {target_currency}", delta=delta_str)
        else:
            st.warning("No data available for calculating indicators over the selected period.")

        target_volatility = st.session_state.get("target_volatility", 0.15)
        df_total_daily_value['Daily Return'] = df_total_daily_value['Total Value'].pct_change()
        window_size = 20
        df_total_daily_value['Volatility'] = df_total_daily_value['Daily Return'].rolling(window=window_size, min_periods=1).std() * (252**0.5)
        df_total_daily_value['Volatility_MA50'] = df_total_daily_value['Volatility'].rolling(window=50, min_periods=1).mean()
        df_total_daily_value['Volatility_MA200'] = df_total_daily_value['Volatility'].rolling(window=200, min_periods=1).mean()

        if not df_total_daily_value['Volatility'].dropna().empty:
            df_volatility_display = df_total_daily_value[
                (df_total_daily_value['Date'] >= pd.Timestamp(start_date_table)) &
                (df_total_daily_value['Date'] <= pd.Timestamp(end_date_table))
            ]
            fig_volatility = go.Figure()
            fig_volatility.add_trace(go.Scatter(
                x=df_volatility_display['Date'],
                y=df_volatility_display['Volatility'],
                mode='lines',
                name='Annualized Volatility',
                line=dict(color='#363636', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>Volatility: %{y:.4f}<extra></extra>'
            ))
            fig_volatility.add_trace(go.Scatter(
                x=df_volatility_display['Date'],
                y=df_volatility_display['Volatility_MA50'],
                mode='lines',
                name='MA50 (Volatility)',
                line=dict(color='orange', dash='dash', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>MA50: %{y:.4f}<extra></extra>'
            ))
            fig_volatility.add_trace(go.Scatter(
                x=df_volatility_display['Date'],
                y=df_volatility_display['Volatility_MA200'],
                mode='lines',
                name='MA200 (Volatility)',
                line=dict(color='green', dash='dash', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>MA200: %{y:.4f}<extra></extra>'
            ))
            fig_volatility.add_trace(go.Scatter(
                x=[df_volatility_display['Date'].min(), df_volatility_display['Date'].max()],
                y=[target_volatility, target_volatility],
                mode='lines',
                name='Target Volatility',
                line=dict(color='red', dash='dot', width=1),
                hovertemplate='Target Volatility: %{y:.4f}<extra></extra>'
            ))
            fig_volatility.update_layout(
                title=f"Volatility | {window_size}-Day Window",
                xaxis_title="",
                yaxis_title="Annualized Volatility",
                hovermode="x unified",
                showlegend=True
            )
            st.plotly_chart(fig_volatility, use_container_width=True)

        df_total_daily_value['MA_Z_70'] = df_total_daily_value['Total Value'].rolling(window=70, min_periods=1).mean()
        df_total_daily_value['STD_Z_70'] = df_total_daily_value['Total Value'].rolling(window=70, min_periods=1).std()
        df_total_daily_value['Z-score_70'] = (
            (df_total_daily_value['Total Value'] - df_total_daily_value['MA_Z_70']) / 
            df_total_daily_value['STD_Z_70']
        ).fillna(0)
        z_score_36mois_window = 36 * 21
        df_total_daily_value['MA_Z_36mois'] = df_total_daily_value['Total Value'].rolling(window=z_score_36mois_window, min_periods=1).mean()
        df_total_daily_value['STD_Z_36mois'] = df_total_daily_value['Total Value'].rolling(window=z_score_36mois_window, min_periods=1).std()
        df_total_daily_value['Z-score_36mois'] = (
            (df_total_daily_value['Total Value'] - df_total_daily_value['MA_Z_36mois']) / 
            df_total_daily_value['STD_Z_36mois']
        ).fillna(0)

        min_date_z = df_total_daily_value['Date'].min()
        if pd.notna(min_date_z) and min_date_z > pd.Timestamp(end_date_table - timedelta(days=3*365)):
            st.warning("Insufficient historical data for 36-month Z-score calculation.")

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
                name='Z-score (70 days)',
                line=dict(color='#363636', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>Z-score (70 days): %{y:.2f}<extra></extra>'
            ))
            fig_z_score.add_trace(go.Scatter(
                x=df_z_score_display['Date'],
                y=df_z_score_display['Z-score_36mois'],
                mode='lines',
                name='Z-score (36 months)',
                line=dict(color='#A49B6D', width=1),
                hovertemplate='%{x|%d/%m/%Y}<br>Z-score (36 months): %{y:.2f}<extra></extra>'
            ))
            fig_z_score.update_layout(
                title="Momentum | Z-scores for 70 days and 36 months",
                xaxis_title="",
                yaxis_title="Z-score",
                hovermode="x unified",
                showlegend=True
            )
            st.plotly_chart(fig_z_score, use_container_width=True)

            latest_z_score = df_z_score_display[df_z_score_display['Date'] == df_z_score_display['Date'].max()]
            if not latest_z_score.empty:
                z_score_70 = latest_z_score['Z-score_70'].iloc[0]
                z_score_36mois = latest_z_score['Z-score_36mois'].iloc[0]
                if z_score_70 > 1 and z_score_36mois > 0:
                    signal = "Bullish"
                    action = "Buy"
                    justification = "Strong short-term with positive long-term trend"
                elif z_score_70 < -1 and z_score_36mois < 0:
                    signal = "Bearish"
                    action = "Sell"
                    justification = "Weak short-term with negative long-term trend"
                else:
                    signal = "Neutral"
                    action = "Hold"
                    justification = "No clear alignment for decisive action"
                cols = st.columns([1, 1, 3])
                with cols[0]:
                    st.metric(label="Signal", value=signal)
                with cols[1]:
                    st.metric(label="Action", value=action)
                with cols[2]:
                    st.metric(label="Justification", value=justification)
        else:
            st.warning("No data available for calculating Z-scores over the selected period.")

        st.markdown("---")
        df_pivot_current_value = df_display_values.pivot_table(index="Ticker", columns="Date", values=f"Current Value ({target_currency})", dropna=False)
        df_pivot_current_value = df_pivot_current_value.sort_index(axis=1)
        df_pivot_current_value = df_pivot_current_value.loc[:, (df_pivot_current_value.columns >= pd.Timestamp(start_date_table)) & (df_pivot_current_value.columns <= pd.Timestamp(end_date_table))]
        df_pivot_current_value.columns = [f"Current Value ({col.strftime('%d/%m/%Y')})" for col in df_pivot_current_value.columns]
        df_final_display = df_pivot_current_value.reset_index()

        sorted_columns = ['Ticker']
        dates_ordered = sorted(list(set([col.date() for col in df_display_values['Date']])))
        for d in dates_ordered:
            date_str = d.strftime('%d/%m/%Y')
            sorted_columns.append(f"Current Value ({date_str})")
        final_columns_to_display = [col for col in sorted_columns if col in df_final_display.columns]
        df_final_display = df_final_display[final_columns_to_display]

        format_dict = {col: lambda x: f"{format_fr(x, 2)} {target_currency}" if pd.notnull(x) else "N/A" for col in df_final_display.columns if "Current Value (" in col}

        st.markdown(f"#### Current Portfolio Value | in {target_currency}")
        st.dataframe(df_final_display.style.format(format_dict), use_container_width=True, hide_index=True)
