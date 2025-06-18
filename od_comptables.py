# od_comptables.py
import streamlit as st
import pandas as pd
import datetime
import requests
import time

def afficher_od_comptables():

 # Si les données de portefeuille sont chargées
    if "df" in st.session_state and st.session_state.df is not None:
        df = st.session_state.df.copy()

        # Placeholder : on affiche juste les colonnes disponibles
        st.markdown("Voici un aperçu brut des données importées :")
        st.dataframe(df.head(), use_container_width=True)

    else:
        st.info("Aucune donnée de portefeuille disponible. Veuillez l'importer via l'onglet Paramètres.")

