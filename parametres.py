# parametres.py
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
    csv_url = st.text_input("Lien CSV")

    if csv_url:
        try:
            # Ajout vérification si lien Google Sheets, transformer en lien CSV si besoin
            if "docs.google.com" in csv_url and "output=csv" not in csv_url:
                if "/edit" in csv_url:
                    csv_url = csv_url.split("/edit")[0] + "/export?format=csv"
                elif "?usp=sharing" in csv_url:
                    csv_url = csv_url.split("?usp=sharing")[0] + "export?format=csv"

            df = pd.read_csv(csv_url)
            st.session_state.df = df
            st.success("Données importées avec succès")
            st.write(df.head())  # DEBUG uniquement
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
