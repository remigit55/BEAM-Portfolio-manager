import streamlit as st
import pandas as pd
import datetime
import requests
import html
import streamlit.components.v1 as components

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

def afficher_taux_change():
    df = st.session_state.get("df")
    if df is None or "Devise" not in df.columns:
        st.info("Aucun portefeuille chargé.")
        return

    devise_cible = st.session_state.get("devise_cible", "EUR")
    devises_uniques = sorted(set(df["Devise"].dropna().unique()))

    if st.button("Actualiser les taux"):
        with st.spinner("Mise à jour des taux de change depuis Yahoo Finance..."):
            st.session_state.fx_rates = actualiser_taux_change(devise_cible, devises_uniques)
            if st.session_state.fx_rates:
                st.success(f"Taux de change actualisés pour {devise_cible}.")
            else:
                st.warning("Aucun taux de change valide récupéré.")

    fx_rates = st.session_state.get("fx_rates", {})
    if not fx_rates:
        st.info("Aucun taux encore chargé.")
        return

    # Construction du DataFrame
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
        # Format the rate conditionally
        taux = f"{row[1]:,.6f}" if pd.notnull(row[1]) else ""
        html_code += f"<tr><td>{html.escape(str(row[0]))}</td><td>{taux}</td></tr>"
    html_code += """
        </tbody>
      </table>
    </div>
    """

    components.html(html_code, height=250, scrolling=True)
    st.markdown(f"_Dernière mise à jour : {datetime.datetime.now().strftime('%H:%M:%S')}_")
