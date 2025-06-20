# portfolio_journal.py
import pandas as pd
import os
from datetime import datetime
import json

JOURNAL_FILE = "portfolio_journal.json" # Nous utiliserons JSON pour la flexibilité

def save_portfolio_snapshot(date, df_portfolio_state, target_currency):
    """
    Sauvegarde un snapshot complet de l'état du portefeuille pour une date donnée.
    Le DataFrame est converti en format JSON pour le stockage.
    """
    if df_portfolio_state is None or df_portfolio_state.empty:
        return

    # Nettoyons le DataFrame avant de le sauvegarder pour ne garder que les colonnes pertinentes
    # Cela évite de sauvegarder des colonnes temporaires ou calculées qui ne sont pas la "source"
    cols_to_save = [
        "Ticker", "Quantité", "Acquisition", "Devise", "Catégorie", "Objectif_LT"
    ]
    # S'assurer que seules les colonnes existantes sont sauvegardées
    df_save = df_portfolio_state.copy()
    existing_cols = [col for col in cols_to_save if col in df_save.columns]
    df_save = df_save[existing_cols]

    # Convertir les types pour la sérialisation JSON si nécessaire
    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
        if col in df_save.columns:
            df_save[col] = pd.to_numeric(df_save[col], errors='coerce') # Ensure numeric
            df_save[col] = df_save[col].fillna(0) # Fill NaN for JSON serialization

    snapshot_data = {
        "date": date.strftime("%Y-%m-%d"),
        "target_currency": target_currency,
        "portfolio_data": df_save.to_dict(orient="records") # Convert DataFrame to list of dicts
    }

    all_snapshots = []
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, 'r') as f:
            try:
                all_snapshots = json.load(f)
            except json.JSONDecodeError:
                all_snapshots = [] # Handle empty or corrupt file

    # Check if a snapshot for this date already exists and update it
    found = False
    for i, snapshot in enumerate(all_snapshots):
        if snapshot["date"] == snapshot_data["date"]:
            all_snapshots[i] = snapshot_data
            found = True
            break
    if not found:
        all_snapshots.append(snapshot_data)

    # Sort snapshots by date
    all_snapshots.sort(key=lambda x: x["date"])

    with open(JOURNAL_FILE, 'w') as f:
        json.dump(all_snapshots, f, indent=4)

def load_portfolio_journal():
    """
    Charge le journal historique du portefeuille.
    Retourne une liste de dictionnaires, chaque dict contenant 'date', 'target_currency' et 'portfolio_data'.
    'portfolio_data' est un DataFrame Pandas.
    """
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, 'r') as f:
            try:
                all_snapshots = json.load(f)
                for snapshot in all_snapshots:
                    snapshot['date'] = datetime.strptime(snapshot['date'], "%Y-%m-%d").date()
                    snapshot['portfolio_data'] = pd.DataFrame(snapshot['portfolio_data'])
                    # Reconverting types might be necessary if JSON serialization changed them
                    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
                        if col in snapshot['portfolio_data'].columns:
                            snapshot['portfolio_data'][col] = pd.to_numeric(snapshot['portfolio_data'][col], errors='coerce')
                return all_snapshots
            except json.JSONDecodeError:
                return [] # Handle empty or corrupt file
    return []
