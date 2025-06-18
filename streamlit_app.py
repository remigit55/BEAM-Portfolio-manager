# streamlit_app.py
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")
st.title("BEAM Portfolio Manager")

# Thème personnalisé
PRIMARY_COLOR = "#363636"
SECONDARY_COLOR = "#E8E8E8"
ACCENT_COLOR = "#A49B6D"

# Style CSS pour bandeau horizontal
st.markdown(f"""
    <style>
        body {{
            background-color: {SECONDARY_COLOR};
            color: {PRIMARY_COLOR};
        }}
        .stApp {{
            font-family: 'Arial', sans-serif;
        }}
        .st-emotion-cache-18ni7ap {{
            background-color: {ACCENT_COLOR};
            padding: 10px;
            border-radius: 0 0 10px 10px;
            margin-bottom: 25px;
        }}
        .st-emotion-cache-1v0mbdj, .st-emotion-cache-1avcm0n {{
            display: none;
        }}
    </style>
""", unsafe_allow_html=True)

# Onglets de navigationMore actions
tabs = st.tabs(["Portefeuille", "Performance", "OD Comptables", "Transactions", "Taux de change", "Paramètres"])

# Bandeau horizontal de navigation
menu = st.selectbox("Navigation", [
    "Portefeuille", 
    "Performance", 
    "OD Comptables", 
    "Transactions M&A", 
    "Taux de change", 
    "Paramètres"
], key="navigation_select")

# Gestion des onglets via import de fichiers séparés
if menu == "Portefeuille":
    import portefeuille
elif menu == "Performance":
    import performance
elif menu == "OD Comptables":
    import od_comptables
elif menu == "Transactions M&A":
    import transactions_ma
elif menu == "Taux de change":
    import taux_change
elif menu == "Paramètres":
    import parametres
