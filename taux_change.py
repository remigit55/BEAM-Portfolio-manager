import streamlit as st
import pandas as pd
import time
import datetime
import requests

def obtenir_taux(devise_source, devise_cible):
    if devise_source == devise_cible:
        return 1.0
    ticker = f"{devise_cible.upper()}={devise_source.upper()}" if devise_cible == "USD" else f"{devise_source.upper()}{devise_cible.upper()}=X"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = { "User-Agent": "Mozilla/5.0" }

    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        return float(meta.get("regularMarketPrice", 0))
    except Exception as e:
        st.warning(f"Taux non disponible pour {devise_source}/{devise_cible} : {e}")
        return None

def afficher_taux_change():
    df = st.session_state.get("df")
    if df is None or "Devise" not in df.columns:
        st.info("Aucun portefeuille chargé.")
        return

    devise_cible = st.session_state.get("devise_cible", "EUR")
    devises_uniques = sorted(set(df["Devise"].dropna().unique()))
    taux_dict = {}

    with st.spinner("Mise à jour des taux de change depuis Yahoo Finance..."):
        for d in devises_uniques:
            taux = obtenir_taux(d, devise_cible)
            if taux:
                taux_dict[d] = taux

    st.session_state.fx_rates = taux_dict

    if not taux_dict:
        st.warning("Aucun taux de change valide récupéré.")
        return

    st.markdown(f"Taux appliqués pour conversion en **{devise_cible}** – _{datetime.datetime.now().strftime('%H:%M:%S')}_")

    df_fx = pd.DataFrame(list(taux_dict.items()), columns=["Devise Source", f"Taux vers {devise_cible}"])
    st.dataframe(df_fx, use_container_width=True)

    # Rafraîchit toutes les 30 secondes automatiquement
    st.markdown("<meta http-equiv='refresh' content='30'>", unsafe_allow_html=True)
    time.sleep(30)
    st.experimental_rerun()
