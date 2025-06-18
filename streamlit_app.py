# streamlit_app.py
import streamlit as st
import streamlit.components.v1 as components

# ➤ Cette commande DOIT être en première ligne Streamlit
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

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

# Afficher le titre principal
st.title("BEAM Portfolio Manager")

# Onglets horizontaux
onglets = st.tabs([
    "Portefeuille", 
    "Performance", 
    "OD Comptables", 
    "Transactions", 
    "Taux de change", 
    "Paramètres"
])

# Importer les scripts correspondant à chaque onglet
with onglets[0]:
    import portefeuille
with onglets[1]:
    import performance
with onglets[2]:
    import od_comptables
with onglets[3]:
    import transactions
with onglets[4]:
    import taux_change
with onglets[5]:
    import parametres
