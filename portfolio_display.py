# portfolio_display.py

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import numpy as np
import json # Import json module

# Import des fonctions depuis les nouveaux modules
from utils import safe_escape, format_fr
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

def afficher_portefeuille():
    """
    Affiche le portefeuille de l'utilisateur, gère les calculs et l'affichage.
    Récupère les données externes via des fonctions dédiées.
    Retourne les totaux convertis pour la synthèse.
    """
    st.header("📈 Portefeuille Détaillé") # Added header for consistency

    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return None, None, None, None

    df = st.session_state.df.copy()

    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")

    fx_rates = st.session_state.get("fx_rates", {}) # Use fx_rates from session state

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
        try:
            taux_scalar = float(raw_taux)
        except (TypeError, ValueError):
            taux_scalar = np.nan # Si ce n'est pas convertible en float, considérez-le comme NaN

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

    # --- Tri côté Python basé sur st.session_state (initial ou après interaction JS) ---
    if "sort_column" not in st.session_state:
        st.session_state.sort_column = None
    if "sort_direction" not in st.session_state:
        st.session_state.sort_direction = "asc"

    if st.session_state.sort_column:
        sort_col_label = st.session_state.sort_column
        
        # Check if the column exists in df_disp
        if sort_col_label in df_disp.columns:
            # Attempt to find the original numeric column if it's a formatted one
            original_col_name = None
            try:
                idx = existing_labels.index(sort_col_label)
                original_col_name = existing_cols_in_df[idx]
                if original_col_name.endswith("_fmt"):
                    original_col_name = original_col_name[:-4] # Get the unformatted column name
            except ValueError:
                pass # Label not found, means it's not a direct mapping or an issue

            # Determine if the original column (before _fmt) is numeric
            if original_col_name and original_col_name in df.columns and pd.api.types.is_numeric_dtype(df[original_col_name]):
                # Sort numerically using the original (unformatted) data
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: pd.to_numeric(
                        # Convert back from formatted string to numeric for sorting
                        x.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.', regex=False),
                        errors='coerce'
                    ).fillna(-float('inf') if st.session_state.sort_direction == "asc" else float('inf'))
                )
            else:
                # Sort alphabetically for non-numeric or non-found original columns
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: x.astype(str).str.lower()
                )
        # else:
            # st.warning(f"Sort column '{sort_col_label}' not found in display DataFrame.")


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
        "Quantité": "90px",
        "Prix d'Acquisition": "110px",
        "Valeur": "100px",
        "Prix Actuel": "90px",
        "Valeur Actuelle": "100px",
        "Haut 52 Semaines": "120px",
        "Valeur H52": "100px",
        "Objectif LT": "100px",
        "Valeur LT": "100px",
        "Momentum (%)": "100px",
        "Z-Score": "80px",
    }
    
    left_aligned_labels = ["Ticker", "Nom", "Catégorie", "Signal", "Action", "Justification"]
    left_align_selectors = []

    for i, label in enumerate(df_disp.columns):
        col_idx = i + 1
        
        if label in width_specific_cols:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: {width_specific_cols[label]}; }}\n"
        else:
            # Default width if not specified
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: 100px; }}\n" 
            
        if label in left_aligned_labels:
            left_align_selectors.append(f"td:nth-child({col_idx})")

    if left_align_selectors:
        css_col_widths += f".portfolio-table {', '.join(left_align_selectors)} {{ text-align: left; white-space: normal; }}\n"

    # Add CSS for sort indicators
    css_col_widths += """
    .portfolio-table th {
        cursor: pointer;
        position: relative;
    }
    .portfolio-table th .sort-icon {
        margin-left: 5px;
        vertical-align: middle;
        font-size: 0.8em;
    }
    """

    # Generate table headers with sort icons
    header_html = ""
    for lbl in df_disp.columns:
        current_sort_icon = ""
        if st.session_state.sort_column == lbl:
            current_sort_icon = "▲" if st.session_state.sort_direction == "asc" else "▼"
        # The onClick event now calls sortColumn with the column label
        header_html += f'<th onclick="sortColumn(\'{safe_escape(lbl)}\')">{safe_escape(lbl)}<span class="sort-icon">{current_sort_icon}</span></th>'


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
          {header_html}
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

    # Find the first numeric column index to place the TOTAL label
    # This ensures "TOTAL" is always aligned to a relevant column, typically the first of the numeric blocks
    total_label_col_idx = 0 
    for i, label in enumerate(df_disp.columns):
        if label in ["Valeur", "Quantité", "Prix d'Acquisition", "Prix Actuel"]: # Adjust based on your preferred "first" numeric column
            total_label_col_idx = i
            break
    
    total_row_cells[total_label_col_idx] = f"TOTAL ({safe_escape(devise_cible)})"

    for display_label, total_value_str in total_cols_mapping.items():
        if display_label in df_disp.columns:
            idx = list(df_disp.columns).index(display_label)
            total_row_cells[idx] = safe_escape(total_value_str)

    html_code += "<tr class='total-row'>"
    for cell_content in total_row_cells:
        html_code += f"<td>{cell_content}</td>"
    html_code += "</tr>"

    html_code += """
        </tbody>
      </table>
    </div>
    <script>
        // Only re-declare if the component is re-rendered
        if (!window.sortColumn) {
            window.sortColumn = function(columnLabel) {
                const currentSortColumn = window.streamlitSortColumn;
                const currentSortDirection = window.streamlitSortDirection;
                
                let newSortDirection = 'asc';
                if (currentSortColumn === columnLabel && currentSortDirection === 'asc') {
                    newSortDirection = 'desc';
                }
                
                const payload = {
                    sort_column: columnLabel,
                    sort_direction: newSortDirection
                };

                // Send a JSON string as the payload
                const streamlitMessage = {
                    type: "streamlit:setComponentValue",
                    payload: JSON.stringify(payload)
                };
                window.parent.postMessage(streamlitMessage, "*");
            };
        }
        // Store current sort state in browser's window object for JavaScript
        // These values are injected by Python at render time
        window.streamlitSortColumn = "{{ st.session_state.sort_column if st.session_state.sort_column else '' }}";
        window.streamlitSortDirection = "{{ st.session_state.sort_direction if st.session_state.sort_direction else '' }}";
    </script>
    """

    # Use components.html to render and listen for messages
    component_value_raw = components.html(html_code, height=600, scrolling=True, key="portfolio_table_display")

    # Update session state if a message is received from JavaScript
    # Check if component_value_raw is a non-empty string before trying to parse
    if isinstance(component_value_raw, str) and component_value_raw.strip(): # Added check
        try:
            # Parse the JSON string received from JavaScript
            component_value = json.loads(component_value_raw)
            if "sort_column" in component_value and "sort_direction" in component_value:
                new_sort_column = component_value["sort_column"]
                new_sort_direction = component_value["sort_direction"]
                
                # Only trigger rerun if sort state actually changed
                if (new_sort_column != st.session_state.sort_column or 
                    new_sort_direction != st.session_state.sort_direction):
                    st.session_state.sort_column = new_sort_column
                    st.session_state.sort_direction = new_sort_direction
                    st.rerun() # Force rerun to re-render with new sort order
        except json.JSONDecodeError as e:
            st.error(f"Erreur lors de la lecture du message de tri depuis la table HTML : {e}. Message reçu: {component_value_raw}")
        except TypeError as e:
            st.error(f"Erreur de type lors du traitement du message de tri : {e}. Message reçu: {component_value_raw}")
    # else: # Optional: For debugging, you could print what component_value_raw is when it's not a string or empty
    #     st.warning(f"component_value_raw was not a string or was empty: {type(component_value_raw)} - {component_value_raw}")


    st.markdown("---")
    
    st.subheader("Totaux du Portefeuille")
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
    with col3:
        if total_valeur != 0 and pd.notna(total_valeur) and pd.notna(total_actuelle):
            gain_perte_abs = total_actuelle - total_valeur
            pourcentage_gain_perte = (gain_perte_abs / total_valeur) * 100
            st.metric(
                label="**Gain/Perte Total**",
                value=f"{format_fr(gain_perte_abs, 2)} {devise_cible}",
                delta=f"{format_fr(pourcentage_gain_perte, 2)}%"
            )
        else:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"N/A {devise_cible}"
            )
    with col4:
        st.metric(
            label=f"**Objectif Long Terme ({devise_cible})**",
            value=f"{format_fr(total_lt, 2)} {devise_cible}"
        )

    return total_valeur, total_actuelle, total_h52, total_lt

def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    """Affiche la synthèse globale du portefeuille."""
    st.header("📊 Synthèse Globale du Portefeuille")

    devise_cible = st.session_state.get("devise_cible", "EUR")

    # Assurez-vous que les totaux sont des nombres avant de les formater
    # Gérer les cas où les totaux pourraient être None (par exemple, si aucun fichier n'est chargé)
    total_valeur_display = f"{format_fr(total_valeur, 2)} {devise_cible}" if pd.notna(total_valeur) else "N/A"
    total_actuelle_display = f"{format_fr(total_actuelle, 2)} {devise_cible}" if pd.notna(total_actuelle) else "N/A"
    total_h52_display = f"{format_fr(total_h52, 2)} {devise_cible}" if pd.notna(total_h52) else "N/A"
    total_lt_display = f"{format_fr(total_lt, 2)} {devise_cible}" if pd.notna(total_lt) else "N/A"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Valeur d'Acquisition", total_valeur_display)
    with col2:
        st.metric("Valeur Actuelle", total_actuelle_display)
    with col3:
        if total_valeur != 0 and pd.notna(total_valeur) and pd.notna(total_actuelle):
            gain_perte_abs = total_actuelle - total_valeur
            pourcentage_gain_perte = (gain_perte_abs / total_valeur) * 100
            st.metric(
                label="**Gain/Perte Total**",
                value=f"{format_fr(gain_perte_abs, 2)} {devise_cible}",
                delta=f"{format_fr(pourcentage_gain_perte, 2)}%"
            )
        else:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"N/A {devise_cible}"
            )
    with col4:
        st.metric("Objectif Long Terme", total_lt_display) # Changed from "Plus-value / Moins-value" to "Objectif Long Terme"

    st.markdown("---")
