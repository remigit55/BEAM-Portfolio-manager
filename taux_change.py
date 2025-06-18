import streamlit as st
import pandas as pd
import datetime
import requests
import html
import streamlit.components.v1 as components

def obtenir_taux(devise_source, devise_cible):
    if devise_source == devise_cible:
        return 1.0
    ticker = f"{devise_source.upper()}{devise_cible.upper()}=X"
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

    if st.button("Actualiser les taux"):
        taux_dict = {}
        with st.spinner("Mise à jour des taux de change depuis Yahoo Finance..."):
            for d in devises_uniques:
                taux = obtenir_taux(d, devise_cible)
                if taux:
                    taux_dict[d] = taux

        if taux_dict:
            st.session_state.fx_rates = taux_dict
        else:
            st.warning("Aucun taux de change valide récupéré.")
            return

    fx_rates = st.session_state.get("fx_rates", {})
    if not fx_rates:
        st.info("Aucun taux encore chargé.")
        return

    # Affichage stylisé du tableau
    df_fx = pd.DataFrame(list(fx_rates.items()), columns=["Devise source", f"Taux vers {devise_cible}"])
    df_fx = df_fx.sort_values(by="Devise source")

    # HTML stylisé
    html_code = f"""
<style>
  .table-container {{ max-height: 300px; overflow-y: auto; }}
  .fx-table {{ width: 100%; border-collapse: collapse; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
  .fx-table th {{
    background: #363636; color: white; padding: 6px; text-align: center; border: none;
    position: sticky; top: 0; z-index: 2; font-size: 12px;
  }}
  .fx-table td {{
    padding: 6px; text-align: right; border: none; font-size: 11px;
  }}
  .fx-table td:first-child {{ text-align: left; }}
  .fx-table tr:nth-child(even) {{ background: #efefef; }}
</style>
<div class="table-container">
  <table class="fx-table">
    <thead><tr><th>Devise source</th><th>Taux vers {devise_cible}</th></tr></thead>
    <tbody>
"""
    for _, row in df_fx.iterrows():
        html_code += f"<tr><td>{html.escape(str(row[0]))}</td><td>{row[1]:,.6f}</td></tr>"
    html_code += """
    </tbody>
  </table>
  st.markdown(f"_Dernière mise à jour : {datetime.datetime.now().strftime('%H:%M:%S')}_")
</div>
"""
components.html(html_code, height=400, scrolling=True)    


