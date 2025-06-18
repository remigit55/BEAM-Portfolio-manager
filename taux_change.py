# taux_change.py
import streamlit as st
import pandas as pd
import datetime
from forex_python.converter import CurrencyRates

def afficher_taux_change():
    st.header("Taux de change")

    devise_cible = st.session_state.get("devise_cible", "EUR")
    devises_sources = ["USD", "CAD", "JPY"]

    def maj_taux():
        try:
            c = CurrencyRates()
            for dev in devises_sources:
                if dev != devise_cible:
                    taux = c.get_rate(dev, devise_cible)
                    st.session_state.fx_rates[dev] = taux
            st.success(f"Taux mis à jour vers la devise cible : {devise_cible}")
        except Exception as e:
            st.error(f"Erreur lors de la récupération des taux : {e}")

    if st.button("🔄 Rafraîchir les taux"):
        maj_taux()

    if "fx_rates" in st.session_state and st.session_state.fx_rates:
        fx_df = pd.DataFrame(
            list(st.session_state.fx_rates.items()),
            columns=["Devise source → " + devise_cible, "Taux"]
        )
        st.markdown(f"Taux appliqués pour conversion en **{devise_cible}** au **{datetime.date.today()}** :")
        st.dataframe(fx_df, use_container_width=True)
    else:
        st.info("Aucun taux de change disponible. Cliquez sur le bouton ci-dessus pour les récupérer.")
