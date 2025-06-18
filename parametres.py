import streamlit as st
import pandas as pd

def afficher_parametres():
    st.subheader("Paramètres")

    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    # Choix de la devise de référence dans le corps principal (plus de sidebar)
    st.session_state.devise_cible = st.selectbox(
        st.markdown(f"#### Devise de référence")
        ["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    # Lien vers la source de données
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"#### Source des données : [Google Sheets CSV]({csv_url})")

    # Bouton pour rafraîchir manuellement les données
    if st.button("Rafraîchir les données"):
        try:
            df = pd.read_csv(csv_url)
            st.session_state.df = df
            st.success("Données importées avec succès")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
