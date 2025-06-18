# streamlit_app.py
import streamlit as st
import importlib  # Nécessaire si tu veux forcer le rechargement

st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

PRIMARY_COLOR = "#363636"
SECONDARY_COLOR = "#E8E8E8"
ACCENT_COLOR = "#A49B6D"

# CSS personnalisé
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

# Création des onglets
onglets = st.tabs([
    "Portefeuille", 
    "Performance", 
    "OD Comptables", 
    "Transactions", 
    "Taux de change", 
    "Paramètres"
])

# Import dynamique et exécution
with onglets[0]:
    import portefeuille
    importlib.reload(portefeuille)

with onglets[1]:
    import performance
    importlib.reload(performance)

with onglets[2]:
    import od_comptables
    importlib.reload(od_comptables)

with onglets[3]:
    import transactions
    importlib.reload(transactions)

with onglets[4]:
    import taux_change
    importlib.reload(taux_change)

with onglets[5]:
    import parametres
    importlib.reload(parametres)  # <-- Force l'exécution même si déjà chargé
