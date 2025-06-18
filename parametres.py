# parametres.py
import streamlit as st
import pandas as pd

st.subheader("Paramètres")

# Définir la devise cible par défaut si non définie
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR"

# Choix de la devise de consolidation
st.session_state.devise_cible = st.selectbox(
    "Devise de référence pour consolidation",
    options=["USD", "EUR", "CAD", "CHF"],
    index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
)

# Zone d’import de portefeuille depuis un lien Google Sheets
st.markdown("#### Importer le portefeuille depuis Google Sheets (export CSV public)")
csv_url = st.text_input("Lien vers le fichier CSV exporté de Google Sheets")

if csv_url:
    try:
        st.session_state.df = pd.read_csv(csv_url)
        st.success("Données importées avec succès depuis le lien CSV.")
    except Exception as e:
        st.error(f"Erreur lors de l'import : {e}")
