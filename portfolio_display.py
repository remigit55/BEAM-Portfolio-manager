import streamlit as st
import pandas as pd
import numpy as np
from utils import format_fr, convertir

def afficher_portefeuille():
    df = st.session_state.get("df")

    if df is None or df.empty:
        st.warning("Aucun portefeuille à afficher.")
        return None, None, None, None

    devise_cible = st.session_state.get("devise_cible", "EUR")
    fx_rates = st.session_state.get("fx_rates", {})

    if not fx_rates or devise_cible not in fx_rates.values():
        st.info("Taux de change non disponibles. Le portefeuille sera affiché dans les devises d’origine.")
        taux_change = {}
    else:
        taux_change = fx_rates

    # Application du taux de change pour chaque ligne
    df["Taux de change"] = df["Devise"].apply(lambda x: taux_change.get(x, 1))
    df["Valeur"] = df["Prix achat"] * df["Quantité"]
    df["Valeur actuelle"] = df["Prix actuel"] * df["Quantité"]
    df["Valeur H52"] = df["Prix H52"] * df["Quantité"]
    df["Valeur LT"] = df["Prix LT"] * df["Quantité"]

    # Conversion dans la devise cible
    df["Valeur (cible)"] = df["Valeur"] * df["Taux de change"]
    df["Valeur actuelle (cible)"] = df["Valeur actuelle"] * df["Taux de change"]
    df["Valeur H52 (cible)"] = df["Valeur H52"] * df["Taux de change"]
    df["Valeur LT (cible)"] = df["Valeur LT"] * df["Taux de change"]

    # Sélection des colonnes à afficher
    colonnes_affichees = [
        "Nom", "Ticker", "Quantité", "Prix achat", "Prix actuel", "Prix H52", "Prix LT",
        "Valeur (cible)", "Valeur actuelle (cible)", "Valeur H52 (cible)", "Valeur LT (cible)", "Devise"
    ]

    df_affiche = df[colonnes_affichees].copy()
    st.dataframe(df_affiche, use_container_width=True)

    # Totaux
    total_valeur = df["Valeur (cible)"].sum()
    total_actuelle = df["Valeur actuelle (cible)"].sum()
    total_h52 = df["Valeur H52 (cible)"].sum()
    total_lt = df["Valeur LT (cible)"].sum()

    st.metric("Valeur totale (achat)", f"{format_fr(total_valeur, 0)} {devise_cible}")
    st.metric("Valeur actuelle", f"{format_fr(total_actuelle, 0)} {devise_cible}")
    st.metric("Valeur H52", f"{format_fr(total_h52, 0)} {devise_cible}")
    st.metric("Valeur LT", f"{format_fr(total_lt, 0)} {devise_cible}")

    return total_valeur, total_actuelle, total_h52, total_lt
