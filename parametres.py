import streamlit as st
import pandas as pd

def afficher_parametres():
    st.markdown("### Paramètres généraux")

    # Initialiser la devise si absente
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    # Sélection de la devise
    devises_disponibles = ["USD", "EUR", "CAD", "CHF"]
    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence",
        devises_disponibles,
        index=devises_disponibles.index(st.session_state.devise_cible)
    )

    # URL CSV
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"📂 **Source des données** : [Google Sheets CSV]({csv_url})")

    # Rafraîchissement manuel
    if st.button("🔄 Rafraîchir les données"):
        try:
            df = pd.read_csv(csv_url)

            if df.empty or df.shape[1] < 2:
                st.warning("⚠️ Le fichier est vide ou incorrectement structuré.")
            else:
                st.session_state.df = df
                st.success("✅ Données importées avec succès.")
                with st.expander("🔍 Aperçu des données importées (10 premières lignes)"):
                    st.dataframe(df.head(10), use_container_width=True)

        except Exception as e:
            st.error(f"❌ Erreur lors de l'import : {e}")
