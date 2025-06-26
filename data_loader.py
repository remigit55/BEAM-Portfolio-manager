# data_loader.py
import pandas as pd
import os
import streamlit as st # <-- Assurez-vous que streamlit est importé ici
import io # Ajouté pour une meilleure gestion future si besoin, mais pas critique pour l'URL

def load_data(uploaded_file):
    """
    Loads data from an uploaded Excel (.xlsx, .xls) or CSV file.
    Returns a DataFrame and the sheet name (for Excel).
    """
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    df = None
    sheet_name = None

    if file_extension == ".csv":
        df = pd.read_csv(uploaded_file)
    elif file_extension in [".xlsx", ".xls"]:
        df = pd.read_excel(uploaded_file)
        sheet_name = df.columns[0]
    else:
        raise ValueError("Unsupported file type. Please upload a CSV or Excel file.")

    return df, sheet_name

def save_data(df, file_path):
    """
    Saves the DataFrame to a file, inferring format from file_path extension.
    This is a placeholder as saving modifications directly back to the original
    uploaded file in Streamlit is complex (Stateless app).
    You would typically offer a download button for the modified DataFrame.
    """
    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == ".csv":
        df.to_csv(file_path, index=False)
    elif file_extension in [".xlsx", ".xls"]:
        df.to_excel(file_path, index=False)
    else:
        st.error("Format de fichier non supporté pour la sauvegarde. Veuillez utiliser .csv ou .xlsx.")

# --- NOUVELLE FONCTION POUR CHARGEMENT DEPUIS URL (DOIT ÊTRE PRÉSENTE) ---
def load_portfolio_from_google_sheets(url):
    """
    Loads portfolio data from a Google Sheets URL.
    The URL must be a 'publish to web' CSV export link.
    """
    if not url:
        st.error("L'URL Google Sheets n'est pas configurée. Veuillez la saisir dans l'onglet 'Paramètres'.")
        return None

    try:
        df = pd.read_csv(url)
        # Vérifier si le DataFrame est vide après chargement
        if df.empty:
            st.warning("Le fichier Google Sheets est vide ou ne contient pas de données.")
            return None
        st.success("Portefeuille chargé avec succès depuis Google Sheets.")
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement depuis Google Sheets : {e}. Assurez-vous que l'URL est correcte et publiée au format CSV.")
        return None
