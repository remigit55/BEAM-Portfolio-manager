import streamlit as st
import pandas as pd
from portefeuille import afficher_portefeuille

def main():
    st.set_page_config(layout="wide", page_title="Mon Portefeuille")
    st.title("Gestion de Portefeuille d'Investissement")

    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("Choisissez un fichier CSV", type=["csv"])
        if uploaded_file is not None:
            try:
                df_uploaded = pd.read_csv(uploaded_file)
                st.session_state.df = df_uploaded
                st.success("Fichier importé avec succès !")
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier : {e}")
                st.session_state.df = None

        st.header("Paramètres de Devise")
        st.session_state.devise_cible = st.selectbox(
            "Devise cible pour l'affichage",
            ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
            index=0
        )

        # Example of possible additional filter
        st.header("Filtres")
        category_filter = st.multiselect(
            "Filtrer par catégorie",
            options=["Tech", "Finance", "Health"],  # Adjust based on your data
            default=[]
        )
        if category_filter:
            if st.session_state.get("df") is not None:
                st.session_state.df = st.session_state.df[st.session_state.df["Catégorie"].isin(category_filter)]

    # Example of additional UI elements
    st.subheader("Aperçu du Portefeuille")
    if st.session_state.get("df") is not None:
        st.write(f"Nombre de lignes : {len(st.session_state.df)}")

    afficher_portefeuille()

if __name__ == "__main__":
    main()
