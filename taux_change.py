import streamlit as st
import pandas as pd
import datetime
import requests

def obtenir_taux(devise_source, devise_cible):
    if devise_source == devise_cible:
        return 1.0

    ticker = (
        f"{devise_cible.upper()}={devise_source.upper()}"
        if devise_cible == "USD"
        else f"{devise_source.upper()}{devise_cible.upper()}=X"
    )
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

    if st.button("Mettre à jour les taux de change"):
        taux_dict = {}
        with st.spinner("Mise à jour des taux de change depuis Yahoo Finance..."):
            for d in devises_uniques:
                taux = obtenir_taux(d, devise_cible)
                if taux:
                    taux_dict[d] = taux

        if taux_dict:
            st.session_state.fx_rates = taux_dict
            st.success(f"Taux mis à jour à {datetime.datetime.now().strftime('%H:%M:%S')}")
        else:
            st.warning("Aucun taux de change valide récupéré.")

    fx_rates = st.session_state.get("fx_rates", {})
    if fx_rates:
        df_fx = pd.DataFrame(list(fx_rates.items()), columns=["Devise Source", f"Taux vers {devise_cible}"])
        st.dataframe(df_fx, use_container_width=True)
