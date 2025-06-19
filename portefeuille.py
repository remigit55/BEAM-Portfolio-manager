import streamlit as st
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components
import yfinance as yf

# It's good practice to define constants at the top if they are widely used
TICKER_COL_NAMES = ["Ticker", "Tickers"]

def safe_escape(text):
    """Escape HTML characters safely."""
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

@st.cache_data(ttl=3600) # Cache FX rates for an hour
def fetch_fx_rates(base="EUR"):
    try:
        url = f"https://api.exchangerate.host/latest?base={base}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.get("rates", {})
        return data
    except Exception as e:
        print(f"Erreur lors de la récupération des taux : {e}")
        return {}

@st.cache_data(ttl=900) # Cache Yahoo data for 15 minutes
def fetch_yahoo_data(ticker):
    ticker = str(ticker).strip().upper()
    
    # Initialize cache in session_state if it doesn't exist
    if "ticker_names_cache" not in st.session_state:
        st.session_state.ticker_names_cache = {}

    # Check if data is already cached
    if ticker in st.session_state.ticker_names_cache:
        cached = st.session_state.ticker_names_cache[ticker]
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else: # Invalidate incomplete cache entries to re-fetch
            del st.session_state.ticker_names_cache[ticker]
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info 
        
        name = info.get("shortName", f"https://finance.yahoo.com/quote/{ticker}")
        current_price = info.get("regularMarketPrice", None)
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", None)
        
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        st.session_state.ticker_names_cache[ticker] = result
        time.sleep(0.05) 
        return result
    except Exception as e:
        print(f"Erreur lors de la récupération des données Yahoo pour {ticker}: {e}")
        return {"shortName": f"https://finance.yahoo.com/quote/{ticker}", "currentPrice": None, "fiftyTwoWeekHigh": None}

@st.cache_data(ttl=3600) # Cache Momentum data for an hour
def fetch_momentum_data(ticker, period="5y", interval="1wk"):
    try:
        data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
        if data.empty:
            return {
                "Momentum (%)": None,
                "Z-Score": None,
                "Signal": "",
                "Action": "",
                "Justification": ""
            }

        close = data['Close']
        df_m = pd.DataFrame({'Close': close})
        df_m['MA_39'] = df_m['Close'].rolling(window=39).mean()
        df_m['Momentum'] = (df_m['Close'] / df_m['MA_39']) - 1
        df_m['Z_Momentum'] = (df_m['Momentum'] - df_m['Momentum'].rolling(10).mean()) / df_m['Momentum'].rolling(10).std()

        latest = df_m.iloc[-1]
        z = latest.get('Z_Momentum')
        m = latest.get('Momentum', 0) * 100

        if pd.isna(z):
            return {
                "Momentum (%)": None,
                "Z-Score": None,
                "Signal": "",
                "Action": "",
                "Justification": ""
            }

        if z > 2:
            signal = "🔥 Surchauffe"
            action = "Alléger / Prendre profits"
            reason = "Momentum extrême, risque de retournement"
        elif z > 1.5:
            signal = "↗ Fort"
            action = "Surveiller"
            reason = "Momentum soutenu, proche de surchauffe"
        elif z > 0.5:
            signal = "↗ Haussier"
            action = "Conserver / Renforcer"
            reason = "Momentum sain"
        elif z > -0.5:
            signal = "➖ Neutre"
            action = "Ne rien faire"
            reason = "Pas de signal exploitable"
        elif z > -1.5:
            signal = "↘ Faible"
            action = "Surveiller / Réduire si confirmé"
            reason = "Dynamique en affaiblissement"
        else:
            signal = "🧊 Survendu"
            action = "Acheter / Renforcer (si signal technique)"
            reason = "Purge excessive, possible bas de cycle"

        return {
            "Momentum (%)": round(m, 2),
            "Z-Score": round(z, 2),
            "Signal": signal,
            "Action": action,
            "Justification": reason
        }
    except Exception as e:
        print(f"Erreur avec {ticker} pour l'analyse de momentum : {e}")
        return {
            "Momentum (%)": None,
            "Z-Score": None,
            "Signal": "",
            "Action": "",
            "Justification": ""
        }

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")

    if "fx_rates" not in st.session_state or st.session_state.get("last_devise_cible") != devise_cible:
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)
        st.session_state.last_devise_cible = devise_cible

    fx_rates = st.session_state.get("fx_rates", {})

    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]
    else:
        df["Valeur"] = None

    if df.shape[1] > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    ticker_col = next((col for col in TICKER_COL_NAMES if col in df.columns), None)

    if ticker_col:
        df[ticker_col] = df[ticker_col].astype(str).fillna('')
        unique_tickers = df[ticker_col].loc[df[ticker_col] != ''].unique()

        yahoo_data_dict = {t: fetch_yahoo_data(t) for t in unique_tickers}
        df["shortName"] = df[ticker_col].map(lambda x: yahoo_data_dict.get(x, {}).get("shortName"))
        df["currentPrice"] = df[ticker_col].map(lambda x: yahoo_data_dict.get(x, {}).get("currentPrice"))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda x: yahoo_data_dict.get(x, {}).get("fiftyTwoWeekHigh"))

        momentum_data_dict = {t: fetch_momentum_data(t) for t in unique_tickers}
        df["Momentum (%)"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Momentum (%)"))
        df["Z-Score"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Z-Score"))
        df["Signal"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Signal"))
        df["Action"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Action"))
        df["Justification"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Justification"))
    else:
        df["shortName"] = None
        df["currentPrice"] = None
        df["fiftyTwoWeekHigh"] = None
        df["Momentum (%)"] = None
        df["Z-Score"] = None
        df["Signal"] = None
        df["Action"] = None
        df["Justification"] = None

    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    else:
        df["Valeur_H52"] = None 
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    else:
        df["Valeur_Actuelle"] = None 

    if "Objectif_LT" not in df.columns:
        df["Objectif_LT"] = pd.NA
    else:
        df["Objectif_LT"] = (
            df["Objectif_LT"]
            .astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        df["Objectif_LT"] = pd.to_numeric(df["Objectif_LT"], errors="coerce")
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]
    
    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise) or val is None: return 0
        if devise.upper() == devise_cible.upper(): return val
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    if "Devise" in df.columns:
        df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
        df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
        df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
        df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)
    else:
        df["Valeur_conv"] = df["Valeur"].fillna(0)
        df["Valeur_Actuelle_conv"] = df["Valeur_Actuelle"].fillna(0)
        df["Valeur_H52_conv"] = df["Valeur_H52"].fillna(0)
        df["Valeur_LT_conv"] = df["Valeur_LT"].fillna(0)
        
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    def format_fr(x, dec):
        if pd.isnull(x) or x is None: return ""
        s = f"{x:,.{dec}f}"
        return s.replace(",", " ").replace(".", ",")

    for col, dec in [
        ("Quantité", 0),
        ("Acquisition", 4),
        ("Valeur", 2),
        ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4),
        ("Valeur_H52", 2),
        ("Valeur_Actuelle", 2),
        ("Objectif_LT", 4),
        ("Valeur_LT", 2),
        ("Momentum (%)", 2),
        ("Z-Score", 2)
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce') 
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))
        else:
            df[f"{col}_fmt"] = ""

    # Define all possible columns and their display labels
    # Use a dictionary to map internal column names to display labels for easier lookup
    full_columns_mapping = {
        ticker_col: "Ticker",
        "shortName": "Nom",
        "Catégorie": "Catégorie",
        "Devise": "Devise",
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Prix d'Acquisition",
        "Valeur_fmt": "Valeur",
        "currentPrice_fmt": "Prix Actuel",
        "Valeur_Actuelle_fmt": "Valeur Actuelle",
        "fiftyTwoWeekHigh_fmt": "Haut 52 Semaines",
        "Valeur_H52_fmt": "Valeur H52",
        "Objectif_LT_fmt": "Objectif LT",
        "Valeur_LT_fmt": "Valeur LT",
        "Momentum (%)_fmt": "Momentum (%)", 
        "Z-Score_fmt": "Z-Score",      
        "Signal": "Signal",           
        "Action": "Action",           
        "Justification": "Justification"     
    }

    # Create two lists: one for internal column names to select, one for display labels
    actual_display_cols_internal = [] # These are the keys from full_columns_mapping
    actual_labels = [] # These are the values (display names) from full_columns_mapping
    
    # Iterate through the desired display order and check if the underlying data exists
    for internal_col_key, display_label in full_columns_mapping.items():
        # Check if the raw column exists OR if it's a formatted column and its raw counterpart exists
        raw_col_name_for_fmt = internal_col_key.replace('_fmt', '')
        if internal_col_key in df.columns or raw_col_name_for_fmt in df.columns:
            actual_display_cols_internal.append(internal_col_key)
            actual_labels.append(display_label)

    # Now create df_disp using the filtered list of internal column names
    # This ensures df_disp only contains columns that actually exist in df
    df_disp = df[actual_display_cols_internal].copy()
    df_disp.columns = actual_labels # Set display labels as column names for df_disp

    # --- Tri du DataFrame pour l'affichage ---
    # --- Tri du DataFrame pour l'affichage ---
query_params = st.query_params
# Handle cases where get returns a list (Streamlit behavior)
sort_column_from_url = query_params.get("sort_column", [None])[0]
sort_direction_from_url = query_params.get("sort_direction", ["asc"])[0]

if sort_column_from_url in actual_labels:  # Validate against display labels
    sort_col_label = sort_column_from_url

    # Find the original column name in df for numeric sorting
    original_numeric_col_name = None
    for internal_col_key, label in full_columns_mapping.items():
        if label == sort_col_label:
            original_numeric_col_name = internal_col_key.replace('_fmt', '')
            break

    if original_numeric_col_name and original_numeric_col_name in df.columns:
        # Sort using the original numeric column from df
        df_disp = df_disp.sort_values(
            by=sort_col_label,
            ascending=(sort_direction_from_url == "asc"),
            key=lambda x: pd.to_numeric(
                df[original_numeric_col_name].reindex(df_disp.index, fill_value=float('nan')),
                errors='coerce'
            ).fillna(-float('inf'))
        )
    else:
        # Sort non-numeric columns as strings, handling None/NaN
        df_disp = df_disp.sort_values(
            by=sort_col_label,
            ascending=(sort_direction_from_url == "asc"),
            key=lambda x: x.fillna('').astype(str).str.lower()
        )
            
    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)
    
    safe_sort_column = safe_escape(str(sort_column_from_url if sort_column_from_url else ""))
safe_sort_direction = safe_escape(str(sort_direction_from_url))

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
    cursor: pointer;
  }}
  .portfolio-table th:hover {{
    background: #4a4a4a;
  }}
  .portfolio-table td {{
    padding: 6px;
    text-align: right;
    border: none;
    font-size: 11px;
    white-space: nowrap;
  }}
  .portfolio-table td:nth-child(1),
  .portfolio-table td:nth-child(2),
  .portfolio-table td:nth-child(3),
  .portfolio-table td:nth-child({len(actual_labels)-2}),
  .portfolio-table td:nth-child({len(actual_labels)-1}),
  .portfolio-table td:nth-child({len(actual_labels)}) {{
    text-align: left;
    white-space: normal;
  }}
  .portfolio-table th:nth-child(1), .portfolio-table td:nth-child(1) {{ width: 80px; }}
  .portfolio-table th:nth-child(2), .portfolio-table td:nth-child(2) {{ width: 200px; }}
  .portfolio-table th:nth-child(3), .portfolio-table td:nth-child(3) {{ width: 100px; }}
  .portfolio-table th:nth-child(4), .portfolio-table td:nth-child(4) {{ width: 60px; }}
  .portfolio-table th:nth-child(5), .portfolio-table td:nth-child(5) {{ width: 60px; }}
  .portfolio-table th:nth-child(6), .portfolio-table td:nth-child(6) {{ width: 80px; }}
  .portfolio-table th:nth-child(7), .portfolio-table td:nth-child(7) {{ width: 80px; }}
  .portfolio-table th:nth-child(8), .portfolio-table td:nth-child(8) {{ width: 80px; }}
  .portfolio-table th:nth-child(9), .portfolio-table td:nth-child(9) {{ width: 80px; }}
  .portfolio-table th:nth-child(10), .portfolio-table td:nth-child(10) {{ width: 80px; }}
  .portfolio-table th:nth-child(11), .portfolio-table td:nth-child(11) {{ width: 80px; }}
  .portfolio-table th:nth-child(12), .portfolio-table td:nth-child(12) {{ width: 80px; }}
  .portfolio-table th:nth-child(13), .portfolio-table td:nth-child(13) {{ width: 80px; }}
  .portfolio-table th:nth-child(14), .portfolio-table td:nth-child(14) {{ width: 80px; }}
  .portfolio-table th:nth-child(15), .portfolio-table td:nth-child(15) {{ width: 80px; }}
  .portfolio-table th:nth-child(16), .portfolio-table td:nth-child(16) {{ width: 150px; }}
  .portfolio-table th:nth-child(17), .portfolio-table td:nth-child(17) {{ width: 150px; }}
  .portfolio-table th:nth-child(18), .portfolio-table td:nth-child(18) {{ width: 150px; }}
  .portfolio-table tr:nth-child(even) {{ background: #efefef; }}
  .total-row td {{
    background: #A49B6D;
    color: white;
    font-weight: bold;
  }}
  .sort-asc::after {{ content: ' ▲'; }}
  .sort-desc::after {{ content: ' ▼'; }}
</style>
<script>
  const currentSort = "{safe_sort_column}";
  const currentDirection = "{safe_sort_direction}";

  function sortTable(column) {{
    let direction = 'asc';
    if (currentSort === column) {{
      direction = currentDirection === 'asc' ? 'desc' : 'asc';
    }}
    // Create a form to submit sorting parameters to Streamlit
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.pathname;
    // Add sort_column
    const inputColumn = document.createElement('input');
    inputColumn.type = 'hidden';
    inputColumn.name = 'sort_column';
    inputColumn.value = column;
    form.appendChild(inputColumn);
    // Add sort_direction
    const inputDirection = document.createElement('input');
    inputDirection.type = 'hidden';
    inputDirection.name = 'sort_direction';
    inputDirection.value = direction;
    form.appendChild(inputDirection);
    // Append form to body and submit
    document.body.appendChild(form);
    form.submit();
  }}

  window.onload = function() {{
    const headers = document.querySelectorAll('.portfolio-table th');
    headers.forEach(header => {{
      if (header.textContent === currentSort) {{
        header.classList.add(currentDirection === 'asc' ? 'sort-asc' : 'sort-desc');
      }} else {{
        header.classList.remove('sort-asc', 'sort-desc');
      }}
    }});
  }};
</script>
<div class="scroll-wrapper">
  <table class="portfolio-table">
    <thead><tr>
"""

# Add clickable headers with sort indicators
for lbl in actual_labels:
    sort_indicator = ""
    if sort_column_from_url == lbl:
        sort_indicator = f' class="sort-{"asc" if sort_direction_from_url == "asc" else "desc"}"'
    html_code += f'<th{sort_indicator} onclick="sortTable(\'{safe_escape(lbl)}\')">{safe_escape(lbl)}</th>'

html_code += """
    </tr></thead>
    <tbody>
"""

# Table body
for _, row in df_disp.iterrows():
    html_code += "<tr>"
    for lbl in actual_labels:
        val = row[lbl]
        val_str = safe_escape(str(val)) if pd.notnull(val) else ""
        html_code += f"<td>{val_str}</td>"
    html_code += "</tr>"

# TOTAL row, dynamically generated based on actual_labels
html_code += "<tr class='total-row'>"
for i, lbl in enumerate(actual_labels):
    if lbl == "Valeur" and total_valeur_str:
        html_code += f"<td>{safe_escape(total_valeur_str)}</td>"
    elif lbl == "Valeur Actuelle" and total_actuelle_str:
        html_code += f"<td>{safe_escape(total_actuelle_str)}</td>"
    elif lbl == "Valeur H52" and total_h52_str:
        html_code += f"<td>{safe_escape(total_h52_str)}</td>"
    elif lbl == "Valeur LT" and total_lt_str:
        html_code += f"<td>{safe_escape(total_lt_str)}</td>"
    elif i == 0:  # First column (Ticker)
        html_code += f"<td>TOTAL ({safe_escape(devise_cible)})</td>"
    else:
        html_code += "<td></td>"
html_code += "</tr></tbody></table></div>"

components.html(html_code, height=600, scrolling=True)
