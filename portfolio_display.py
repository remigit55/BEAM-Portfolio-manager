# portfolio_display.py

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import numpy as np

# Import des fonctions depuis les nouveaux modules
from utils import safe_escape, format_fr
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

def afficher_portefeuille():
    """
    Affiche le portefeuille de l'utilisateur, gère les calculs et l'affichage.
    Récupère les données externes via des fonctions dédiées.
    Retourne les totaux convertis pour la synthèse.
    """
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return None, None, None, None

    df = st.session_state.df.copy()

    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")

    fx_rates = fetch_fx_rates(devise_cible)

    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]
    else:
        df["Valeur"] = np.nan

    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    if "ticker_data_cache" not in st.session_state:
        st.session_state.ticker_data_cache = {}

    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers = df[ticker_col].dropna().unique()
        for ticker in unique_tickers:
            if ticker not in st.session_state.ticker_data_cache:
                st.session_state.ticker_data_cache[ticker] = fetch_yahoo_data(ticker)
        
        df["shortName"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("shortName", f"https://finance.yahoo.com/quote/{t}"))
        df["currentPrice"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("currentPrice", np.nan))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("fiftyTwoWeekHigh", np.nan))
    else:
        df["shortName"] = ""
        df["currentPrice"] = np.nan
        df["fiftyTwoWeekHigh"] = np.nan

    df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

    if "Objectif_LT" not in df.columns:
        df["Objectif_LT"] = np.nan
    else:
        df["Objectif_LT"] = (
            df["Objectif_LT"]
              .astype(str)
              .str.replace(" ", "", regex=False)
              .str.replace(",", ".", regex=False)
        )
        df["Objectif_LT"] = pd.to_numeric(df["Objectif_LT"], errors="coerce")
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]

    if "momentum_results_cache" not in st.session_state:
        st.session_state.momentum_results_cache = {}
            
    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers_for_momentum = df[ticker_col].dropna().unique()
        for ticker in unique_tickers_for_momentum:
            if ticker not in st.session_state.momentum_results_cache:
                st.session_state.momentum_results_cache[ticker] = fetch_momentum_data(ticker)
        
        df["Last Price"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Last Price", np.nan))
        df["Momentum (%)"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Momentum (%)", np.nan))
        df["Z-Score"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Z-Score", np.nan))
        df["Signal"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Signal", ""))
        df["Action"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Action", ""))
        df["Justification"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Justification", ""))
    else:
        df["Last Price"] = np.nan
        df["Momentum (%)"] = np.nan
        df["Z-Score"] = np.nan
        df["Signal"] = ""
        df["Action"] = ""
        df["Justification"] = ""


    for col_name, dec_places in [
        ("Quantité", 0), ("Acquisition", 4), ("Valeur", 2), ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4), ("Valeur_H52", 2), ("Valeur_Actuelle", 2),
        ("Objectif_LT", 4), ("Valeur_LT", 2), 
        ("Momentum (%)", 2), ("Z-Score", 2)
    ]:
        if col_name in df.columns:
            df[f"{col_name}_fmt"] = df[col_name].map(lambda x: format_fr(x, dec_places))
    
    # --- DÉBUT DE LA CORRECTION DE LA FONCTION convertir ---
    def convertir(val, source_devise):
        if pd.isnull(val):
            return np.nan # Si la valeur est NaN, retournez NaN directement

        source_devise = str(source_devise).upper() # Assurer que c'est une chaîne
        
        if source_devise == devise_cible:
            return val # Pas de conversion nécessaire

        raw_taux = fx_rates.get(source_devise)
        
        # Convertir raw_taux en un float pour une vérification robuste avec pd.isna
        # Si raw_taux est None, float(None) donnera un TypeError, donc un bloc try-except est nécessaire.
        try:
            taux_scalar = float(raw_taux)
        except (TypeError, ValueError):
            taux_scalar = np.nan # Si ce n'est pas convertible en float, considérez-le comme NaN

        # Vérifiez explicitement si le taux est None ou NaN après la tentative de conversion
        if pd.isna(taux_scalar): 
            # st.warning(f"Taux de change pour {source_devise}/{devise_cible} non trouvé. Utilisation de 1:1 pour {source_devise}.")
            return val # Retourne la valeur non convertie si le taux est manquant
        
        return val * taux_scalar
    # --- FIN DE LA CORRECTION DE LA FONCTION convertir ---


    df["Devise"] = df["Devise"].fillna("EUR").astype(str).str.upper()

    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
    df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)

    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    cols = [
        ticker_col, "shortName", "Catégorie", "Devise",
        "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt",
        "currentPrice_fmt", "Valeur_Actuelle_fmt", "fiftyTwoWeekHigh_fmt",
        "Valeur_H52_fmt", "Objectif_LT_fmt", "Valeur_LT_fmt",
        "Momentum (%)_fmt", "Z-Score_fmt",
        "Signal", "Action", "Justification"
    ]
    labels = [
        "Ticker", "Nom", "Catégorie", "Devise",
        "Quantité", "Prix d'Acquisition", "Valeur",
        "Prix Actuel", "Valeur Actuelle", "Haut 52 Semaines",
        "Valeur H52", "Objectif LT", "Valeur LT",
        "Momentum (%)", "Z-Score",
        "Signal", "Action", "Justification"
    ]

    existing_cols_in_df = []
    existing_labels = []
    for i, col_name in enumerate(cols):
        if col_name == ticker_col and ticker_col is not None and ticker_col in df.columns:
            existing_cols_in_df.append(ticker_col)
            existing_labels.append(labels[i])
        elif col_name.endswith("_fmt"):
            base_col_name = col_name[:-4]
            if base_col_name in df.columns:
                existing_cols_in_df.append(col_name)
                existing_labels.append(labels[i])
        elif col_name in df.columns:
             existing_cols_in_df.append(col_name)
             existing_labels.append(labels[i])
    
    if not existing_cols_in_df:
        st.warning("Aucune colonne de données valide à afficher.")
        return total_valeur, total_actuelle, total_h52, total_lt

    df_disp = df[existing_cols_in_df].copy()
    df_disp.columns = existing_labels

    if "sort_column" not in st.session_state:
        st.session_state.sort_column = None
    if "sort_direction" not in st.session_state:
        st.session_state.sort_direction = "asc"

    if st.session_state.sort_column:
        sort_col_label = st.session_state.sort_column
        if sort_col_label in df_disp.columns:
            original_col_name = None
            try:
                idx = existing_labels.index(sort_col_label)
                original_col_name = existing_cols_in_df[idx]
                if original_col_name.endswith("_fmt"):
                    original_col_name = original_col_name[:-4] 
            except ValueError:
                pass

            if original_col_name and original_col_name in df.columns and pd.api.types.is_numeric_dtype(df[original_col_name]):
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: pd.to_numeric(
                        x.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.', regex=False),
                        errors='coerce'
                    ).fillna(-float('inf') if st.session_state.sort_direction == "asc" else float('inf'))
                )
            else:
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: x.astype(str).str.lower()
                )
    
    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)

    css_col_widths = ""
    width_specific_cols = {
        "Ticker": "80px",
        "Nom": "200px",
        "Catégorie": "100px",
        "Devise": "60px",
        "Signal": "100px",
        "Action": "150px",
        "Justification": "200px",
    }
    
    left_aligned_labels = ["Ticker", "Nom", "Catégorie", "Signal", "Action", "Justification"]
    left_align_selectors = []

    for i, label in enumerate(df_disp.columns):
        col_idx = i + 1
        
        if label in width_specific_cols:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: {width_specific_cols[label]}; }}\n"
        else:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: 100px; }}\n"
        
        if label in left_aligned_labels:
            left_align_selectors.append(f"td:nth-child({col_idx})")

    if left_align_selectors:
        css_col_widths += f".portfolio-table {', '.join(left_align_selectors)} {{ text-align: left; white-space: normal; }}\n"


    html_code = f"""
    <style>
      .scroll-wrapper {{
        overflow-x: auto !important;
        overflow-y: auto;
        max-height: 500px;
        max-width: none !important;
        width: auto;
        display: block;
        position: relative;
      }}
      .portfolio-table {{
        min-width: 2200px;
        border-collapse: collapse;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      }}
      .portfolio-table th {{
        background: #363636;
        color: white;
        padding: 8px;
        text-align: center;
        border: none;
        position: sticky;
        top: 0;
        z-index: 2;
        font-size: 12px;
        box-sizing: border-box;
      }}
      .portfolio-table td {{
        padding: 6px;
        text-align: right;
        border: none;
        font-size: 11px;
        white-space: nowrap;
      }}
      {css_col_widths}

      .portfolio-table tr:nth-child(even) {{ background: #efefef; }}
      .total-row td {{
        background: #A49B6D;
        color: white;
        font-weight: bold;
      }}
    </style>
    <div class="scroll-wrapper">
      <table class="portfolio-table">
        <thead><tr>
    """

    for lbl in df_disp.columns:
        html_code += f'<th>{safe_escape(lbl)}</th>'

    html_code += """
        </tr></thead>
        <tbody>
    """

    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in df_disp.columns:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"

    num_cols_displayed = len(df_disp.columns)
    total_row_cells = [""] * num_cols_displayed
    
    total_cols_mapping = {
        "Valeur": total_valeur_str,
        "Valeur Actuelle": total_actuelle_str,
        "Valeur H52": total_h52_str,
        "Valeur LT": total_lt_str
    }

    for display_label, total_value_str in total_cols_mapping.items():
        if display_label in df_disp.columns:
            idx = list(df_disp.columns).index(display_label)
            total_row_cells[idx] = safe_escape(total_value_str)

    total_row_cells[0] = f"TOTAL ({safe_escape(devise_cible)})"

    html_code += "<tr class='total-row'>"
    for cell_content in total_row_cells:
        html_code += f"<td>{cell_content}</td>"
    html_code += "</tr>"


    html_code += """
        </tbody>
      </table>
    </div>
    """

    components.html(html_code, height=600, scrolling=True)

    return total_valeur, total_actuelle, total_h52, total_lt

def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    st.subheader("Synthèse Globale du Portefeuille")

    devise_cible = st.session_state.get("devise_cible", "EUR")

    if total_valeur is None:
        st.info("Veuillez importer un fichier Excel pour voir la synthèse de votre portefeuille.")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label=f"**Valeur d'Acquisition ({devise_cible})**",
            value=f"{format_fr(total_valeur, 2)} {devise_cible}"
        )
    with col2:
        st.metric(
            label=f"**Valeur Actuelle ({devise_cible})**",
            value=f"{format_fr(total_actuelle, 2)} {devise_cible}"
        )
    
    if total_valeur != 0 and pd.notna(total_valeur) and pd.notna(total_actuelle):
        gain_perte_abs = total_actuelle - total_valeur
        pourcentage_gain_perte = (gain_perte_abs / total_valeur) * 100
        with col3:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"{format_fr(gain_perte_abs, 2)} {devise_cible}",
                delta=f"{format_fr(pourcentage_gain_perte, 2)}%"
            )
    else:
        with col3:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"N/A {devise_cible}"
            )
    
    with col4:
        st.metric(
            label=f"**Objectif Long Terme ({devise_cible})**",
            value=f"{format_fr(total_lt, 2)} {devise_cible}"
        )
