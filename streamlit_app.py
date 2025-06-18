# streamlit_app.py
import streamlit as st
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")
st.title("BEAM Portfolio Manager")

st.markdown("""
    <style>
        .stApp { font-family: 'Arial', sans-serif; }
    </style>
""", unsafe_allow_html=True)

# Menu de navigation
menu = st.sidebar.radio("Navigation", [
    "Portefeuille", 
    "Performance", 
    "OD Comptables", 
    "Transactions M&A", 
    "Taux de change", 
    "Paramètres"
])

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
