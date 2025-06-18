# parametres.py
import streamlit as st
import pandas as pd

st.subheader("Paramètres")

# Devise cible
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR"

st.session_state.devise_cible = st.selectbox(
    "Devise de référence pour consolidation",
    options=["USD", "EUR", "CAD", "CHF"],
    index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
)

# Import depuis Google Sheets CSV
st.markdown("### Import du portefeuille")
csv_url = st.text_input("Lien vers le CSV Google Sheets (onglet Portefeuille)")

if csv_url:
    try:
        st.session_state.df = pd.read_csv(csv_url)
        st.success("✅ Données importées depuis le lien CSV")
        if "df" in st.session_state and st.session_state.df is not None:
            st.markdown("### Aperçu des données importées")
            st.dataframe(st.session_state.df.head(), use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erreur lors de l'import : {e}")
else:
    st.info("Veuillez entrer un lien CSV public depuis Google Sheets pour charger les données du portefeuille.")
