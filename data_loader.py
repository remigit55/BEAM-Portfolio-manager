# data_loader.py
import pandas as pd
import os

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
        # For Excel, you might want to let the user select a sheet
        # For simplicity, we'll just load the first sheet here.
        # In a real app, you might use pd.read_excel(uploaded_file, sheet_name=sheet_name_input)
        df = pd.read_excel(uploaded_file)
        sheet_name = df.columns[0] # Placeholder for sheet name if needed later
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

    # In a real Streamlit app, you'd generate a download link rather than saving directly
    # Example for download (not implemented here, just for illustration):
    # csv = df.to_csv(index=False).encode('utf-8')
    # st.download_button(
    #     label="Télécharger le portefeuille modifié en CSV",
    #     data=csv,
    #     file_name='mon_portefeuille_modifie.csv',
    #     mime='text/csv',
    # )
