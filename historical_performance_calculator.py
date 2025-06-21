# historical_performance_calculator.py
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# from historical_data_fetcher import get_all_historical_data # Will be called from here

def calculate_daily_portfolio_value(snapshot_data, date, historical_prices, historical_fx, target_currency):
    """
    Calcule la valeur du portefeuille pour une date donnée en utilisant les cours et taux historiques.
    """
    df_snapshot = snapshot_data['portfolio_data']
    current_date_str = date.strftime("%Y-%m-%d")

    daily_portfolio_value_acquisition = 0.0
    daily_portfolio_value_current = 0.0

    for _, row in df_snapshot.iterrows():
        ticker = row.get("Ticker")
        quantity = row.get("Quantité", 0)
        acquisition_price = row.get("Acquisition", 0)
        source_currency = row.get("Devise", target_currency).upper() # Default to target_currency if not specified

        if pd.isna(quantity) or quantity == 0:
            continue

        # Get historical current price for the ticker
        current_price = np.nan
        if ticker and ticker in historical_prices and current_date_str in historical_prices[ticker].index:
            current_price = historical_prices[ticker].loc[current_date_str]
        
        if pd.isna(current_price): # If no specific price, use acquisition price for current value (conservative)
             current_price = acquisition_price # Or skip this asset if you prefer
             
        # Get historical FX rate for conversion
        fx_rate = 1.0
        if source_currency != target_currency:
            fx_key = f"{source_currency}/{target_currency}"
            if fx_key in historical_fx and current_date_str in historical_fx[fx_key].index:
                fx_rate = historical_fx[fx_key].loc[current_date_str]
            else:
                # Fallback: if FX rate not found, treat as 1:1 conversion (warn user if this happens often)
                # st.warning(f"FX rate for {fx_key} not found for {current_date_str}. Using 1:1 conversion.")
                fx_rate = 1.0 

        # Calculate values in source currency
        value_acquisition_source_curr = quantity * acquisition_price
        value_current_source_curr = quantity * current_price

        # Convert to target currency
        daily_portfolio_value_acquisition += value_acquisition_source_curr * fx_rate
        daily_portfolio_value_current += value_current_source_curr * fx_rate

    return daily_portfolio_value_acquisition, daily_portfolio_value_current


def reconstruct_historical_performance(start_date, end_date, target_currency, portfolio_journal):
    """
    Reconstruit l'historique de la valeur du portefeuille sur une plage de dates.
    """
    if not portfolio_journal:
        return pd.DataFrame()

    # Get all unique tickers and currencies from the entire journal
    all_tickers = set()
    all_currencies = set()
    for snapshot in portfolio_journal:
        df_snap = snapshot['portfolio_data']
        if 'Ticker' in df_snap.columns:
            all_tickers.update(df_snap['Ticker'].dropna().unique())
        if 'Devise' in df_snap.columns:
            all_currencies.update(df_snap['Devise'].dropna().unique())
    
    # Import here to avoid circular dependencies if historical_data_fetcher needs calculator later
    from historical_data_fetcher import get_all_historical_data
    
    # Fetch all necessary historical data once
    historical_prices, historical_fx = get_all_historical_data(
        list(all_tickers), list(all_currencies), start_date, end_date, target_currency
    )

    # Prepare a date range for the reconstruction
    # Only consider dates where we have a snapshot or an active portfolio state
    relevant_dates = sorted(list(set([s['date'] for s in portfolio_journal] + 
                                     [d.date() for d in pd.bdate_range(start_date, end_date)])))
    
    # Filter dates to be within the requested range
    relevant_dates = [d for d in relevant_dates if start_date <= d <= end_date]

    # Initialize results
    historical_data = []
    
    # Find the earliest snapshot that is before or on the start_date
    current_snapshot_index = -1
    for i, snapshot in enumerate(portfolio_journal):
        if snapshot['date'] <= start_date:
            current_snapshot_index = i
        else:
            break
    
    if current_snapshot_index == -1: # No snapshot before or on start_date
        # Try to find the first snapshot available
        if portfolio_journal:
            current_snapshot_index = 0
        else:
            return pd.DataFrame() # No data at all

    current_portfolio_state = portfolio_journal[current_snapshot_index]

    # Iterate through each business day in the desired range
    for single_date in pd.bdate_range(start_date, end_date):
        date_as_date = single_date.date()

        # Update the portfolio state if a new snapshot is available for this date or before
        while current_snapshot_index + 1 < len(portfolio_journal) and \
              portfolio_journal[current_snapshot_index + 1]['date'] <= date_as_date:
            current_snapshot_index += 1
            current_portfolio_state = portfolio_journal[current_snapshot_index]

        # Calculate values for the current date using the current_portfolio_state
        daily_acquisition, daily_current = calculate_daily_portfolio_value(
            current_portfolio_state, date_as_date, historical_prices, historical_fx, target_currency
        )
        
        # Add to results if we have valid data
        if not (np.isnan(daily_acquisition) or np.isnan(daily_current)):
            historical_data.append({
                "Date": date_as_date,
                "Valeur Acquisition": daily_acquisition,
                "Valeur Actuelle": daily_current,
                "Devise": target_currency # Store the target currency used for this day
            })
    
    if not historical_data:
        return pd.DataFrame()

    df_reconstructed = pd.DataFrame(historical_data)
    df_reconstructed["Gain/Perte Absolu"] = df_reconstructed["Valeur Actuelle"] - df_reconstructed["Valeur Acquisition"]
    df_reconstructed["Gain/Perte (%)"] = df_reconstructed.apply(
        lambda row: (row["Gain/Perte Absolu"] / row["Valeur Acquisition"]) * 100 if row["Valeur Acquisition"] != 0 else 0,
        axis=1
    )
    return df_reconstructed
