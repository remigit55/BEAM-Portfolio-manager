import streamlit as st
import pandas as pd

def afficher_parametres():
    st.subheader("Paramètres")

    # Devise cible par défaut
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    st.session_state.devise_cible = st.selectbox(
        "Devise de référence",
        ["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    st.markdown("#### Lien Google Sheets exporté en CSV (public)")
    csv_url = st.text_input("Lien CSV", key="csv_url_input")

    if csv_url:
        # Vérifier si le lien a déjà été traité
        if "last_csv_url" not in st.session_state:
            st.session_state.last_csv_url = None

        # Traiter uniquement si le lien est nouveau
        if csv_url != st.session_state.last_csv_url:
            try:
                # Transformer lien Google Sheets en lien CSV si besoin
                if "docs.google.com" in csv_url and "output=csv" not in csv_url:
                    if "/edit" in csv_url:
                        csv_url = csv_url.split("/edit")[0] + "/export?format=csv"
                    elif "?usp=sharing" in csv_url:
                        csv_url = csv_url.split("?usp=sharing")[0] + "/export?format=csv"

                df = pd.read_csv(csv_url)
                st.session_state.df = df
                st.session_state.last_csv_url = csv_url  # Mettre à jour le dernier lien traité
                st.success("Données importées avec succès")
                # Réinitialiser le champ de saisie
                st.session_state.csv_url_input = ""
                st.rerun()  # Relancer pour mettre à jour l'affichage
            except Exception as e:
                st.error(f"Erreur lors de l'import : {e}")
                st.session_state.last_csv_url = None  # Permettre une nouvelle tentative
