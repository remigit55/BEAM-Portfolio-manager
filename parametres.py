import streamlit as st
import pandas as pd
import time

def afficher_parametres():
    st.subheader("Paramètres")

    # Activer le rafraîchissement automatique toutes les 30 secondes
    st_autorefresh(interval=30_000)  # 30 seconds in milliseconds

    # Devise cible par défaut
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    st.session_state.devise_cible = st.selectbox(
        "Devise de référence",
        ["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    # URL fixe du Google Sheets CSV
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"

    st.markdown(f"#### Source des données : [Google Sheets CSV]({csv_url})")
    st.write("Les données sont rafraîchies automatiquement toutes les 30 secondes.")

    # Vérifier si le lien a déjà été traité
    if "last_csv_url" not in st.session_state:
        st.session_state.last_csv_url = None
    if "last_fetch_time" not in st.session_state:
        st.session_state.last_fetch_time = 0

    # Fetch data only if it's a new URL or 30 seconds have passed
    current_time = time.time()
    if csv_url != st.session_state.last_csv_url or (current_time - st.session_state.last_fetch_time) >= 30:
        try:
            df = pd.read_csv(csv_url)
            st.session_state.df = df
            st.session_state.last_csv_url = csv_url
            st.session_state.last_fetch_time = current_time
            st.success("Données importées avec succès")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
            st.session_state.last_csv_url = None  # Allow retry on next refresh

def st_autorefresh(interval=30_000, key="auto_refresh"):
    """Custom autorefresh implementation to avoid conflicts."""
    if key not in st.session_state:
        st.session_state[key] = True
    st.rerun()
