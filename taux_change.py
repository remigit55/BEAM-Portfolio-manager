# taux_change.py
import streamlit as st
import pandas as pd
import datetime

st.subheader("Taux de change utilisés")

if "fx_rates" in st.session_state and st.session_state.fx_rates:
    st.markdown(f"Taux appliqués pour conversion en {st.session_state.devise_cible} au {datetime.date.today()}")
    fx_df = pd.DataFrame(list(st.session_state.fx_rates.items()), columns=["Conversion", "Taux"])
    st.dataframe(fx_df, use_container_width=True)
else:
    st.info("Aucun taux de change disponible. Veuillez charger un portefeuille d'abord.")

