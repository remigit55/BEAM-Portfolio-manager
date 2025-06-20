# historical_data_manager.py
import pandas as pd
import os
from datetime import datetime

# Define the file path for storing historical data
HISTORY_FILE = "portfolio_history.csv"

def save_daily_totals(date, acquisition_value, current_value, h52_value, lt_value, currency):
    """
    Saves daily portfolio totals to a CSV file.
    Creates the file if it doesn't exist.
    """
    new_data = {
        "Date": [date.strftime("%Y-%m-%d")],
        "Valeur Acquisition": [acquisition_value],
        "Valeur Actuelle": [current_value],
        "Valeur H52": [h52_value],
        "Valeur LT": [lt_value],
        "Devise": [currency]
    }
    new_df = pd.DataFrame(new_data)

    if not os.path.exists(HISTORY_FILE):
        new_df.to_csv(HISTORY_FILE, index=False)
    else:
        # Check if an entry for today already exists
        history_df = pd.read_csv(HISTORY_FILE)
        history_df["Date"] = pd.to_datetime(history_df["Date"])
        
        # If an entry for today already exists, update it; otherwise, append
        if not history_df[history_df["Date"] == pd.to_datetime(date)].empty:
            history_df.loc[history_df["Date"] == pd.to_datetime(date), 
                           ["Valeur Acquisition", "Valeur Actuelle", "Valeur H52", "Valeur LT", "Devise"]] = \
                [acquisition_value, current_value, h52_value, lt_value, currency]
            history_df.to_csv(HISTORY_FILE, index=False)
        else:
            new_df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

def load_historical_data():
    """
    Loads historical portfolio totals.
    Returns an empty DataFrame if the file doesn't exist.
    """
    if os.path.exists(HISTORY_FILE):
        df = pd.read_csv(HISTORY_FILE)
        df["Date"] = pd.to_datetime(df["Date"])
        return df
    return pd.DataFrame(columns=["Date", "Valeur Acquisition", "Valeur Actuelle", "Valeur H52", "Valeur LT", "Devise"])
