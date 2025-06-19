import streamlit as st
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed

def obtenir_taux(devise_source, devise_cible):
    if devise_source == devise_cible:
        return 1.0
    ticker = f"{devise_source.upper()}{devise_cible.upper()}=X"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        return float(meta.get("regularMarketPrice", 0))
    except Exception as e:
        st.warning(f"Taux non disponible pour {devise_source}/{devise_cible} : {e}")
        return None

def actualiser_taux_change(devise_cible, devises_uniques):
    """Fonction pour actualiser les taux de change pour une devise cible donnée."""
    taux_dict = {}
    for d in devises_uniques:
        try:
            taux = obtenir_taux(d, devise_cible)
            if taux:
                taux_dict[d] = taux
        except Exception as e:
            st.warning(f"Taux non disponible pour {d}/{devise_cible} : {e}")
            taux_dict[d] = None
    return taux_dict

def afficher_parametres():
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    st.markdown("#### Paramètres généraux")

    # Stocker la devise précédente pour détecter un changement
    previous_devise = st.session_state.devise_cible

    # Sélection de la devise
    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence",
        ["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    # Si la devise a changé, actualiser les taux
    if st.session_state.devise_cible != previous_devise:
        if "df" in st.session_state and st.session_state.df is not None and "Devise" in st.session_state.df.columns:
            devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
            with st.spinner("Mise à jour des taux de change pour la nouvelle devise..."):
                st.session_state.fx_rates = actualiser_taux_change(st.session_state.devise_cible, devises_uniques)
                st.success(f"Taux de change actualisés pour {st.session_state.devise_cible}.")
        else:
            st.warning("Aucun portefeuille chargé, impossible d'actualiser les taux.")

    # URL Google Sheets du portefeuille (CSV)
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"#### Source des données : [Google Sheets CSV]({csv_url})")

    if st.button("Rafraîchir les données du portefeuille"):
        try:
            df = pd.read_csv(csv_url)
            st.session_state.df = df
            # Actualiser les taux après le chargement du portefeuille
            if "Devise" in df.columns:
                devises_uniques = sorted(set(df["Devise"].dropna().unique()))
                with st.spinner("Mise à jour des taux de change..."):
                    st.session_state.fx_rates = actualiser_taux_change(st.session_state.devise_cible, devises_uniques)
                    st.success(f"Taux de change actualisés pour {st.session_state.devise_cible}.")
            st.success("Données importées avec succès.")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
