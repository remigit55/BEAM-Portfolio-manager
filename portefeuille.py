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
        data = response.json()
        return data.get("rates", {})
    except Exception as e:
        # print(f"Erreur lors de la récupération des taux : {e}") # Debugging print removed for cleaner output
        return {}

@st.cache_data(ttl=900) # Cache Yahoo data for 15 minutes
def fetch_yahoo_data(ticker):
    ticker = str(ticker).strip().upper()
    # Use session_state for a simple, in-memory cache for Yahoo data
    if "ticker_names_cache" not in st.session_state:
        st.session_state.ticker_names_cache = {}

    if ticker in st.session_state.ticker_names_cache:
        cached = st.session_state.ticker_names_cache[ticker]
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else: # Invalidate incomplete cache entries to re-fetch
            del st.session_state.ticker_names_cache[ticker]

    try:
        # Using yfinance.Ticker to fetch information
        stock = yf.Ticker(ticker)
        info = stock.info # This call fetches a lot of data, and can take time.
                          # The @st.cache_data decorator helps here.

        name = info.get("shortName", f"https://finance.yahoo.com/quote/{ticker}")
        current_price = info.get("regularMarketPrice", None)
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", None)

        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        st.session_state.ticker_names_cache[ticker] = result
        time.sleep(0.05) # Small delay to be polite to APIs and avoid rate limiting
        return result
    except Exception as e:
        # print(f"Erreur lors de la récupération des données Yahoo pour {ticker}: {e}") # Debugging print removed
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
        # print(f"Erreur avec {ticker} pour l'analyse de momentum : {e}") # Debugging print removed
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

    # Harmoniser le nom de la colonne pour l’objectif long terme
    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")

    # Fetch FX rates only if the target currency changes or if not already fetched
    if "fx_rates" not in st.session_state or st.session_state.get("last_devise_cible") != devise_cible:
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)
        st.session_state.last_devise_cible = devise_cible

    fx_rates = st.session_state.get("fx_rates", {})

    # Normalisation numérique
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcul de la valeur
    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Ajout de la colonne Catégorie depuis la colonne F du CSV (index 5)
    if df.shape[1] > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    # Get ticker column name
    ticker_col = next((col for col in TICKER_COL_NAMES if col in df.columns), None)

    if ticker_col:
        # Apply Yahoo Finance data fetching
        yahoo_data_results = df[ticker_col].apply(fetch_yahoo_data)
        df["shortName"] = yahoo_data_results.apply(lambda x: x["shortName"])
        df["currentPrice"] = yahoo_data_results.apply(lambda x: x["currentPrice"])
        df["fiftyTwoWeekHigh"] = yahoo_data_results.apply(lambda x: x["fiftyTwoWeekHigh"])

        # Apply momentum analysis
        # Create a temporary DataFrame from momentum results to merge
        momentum_results_list = [fetch_momentum_data(t) for t in df[ticker_col].dropna().unique()]
        momentum_df = pd.DataFrame(momentum_results_list).set_index(df[ticker_col].dropna().unique())
        
        # Add momentum data by mapping from the main DataFrame's ticker
        # Ensure that the index for mapping is consistent
        df["Momentum (%)"] = df[ticker_col].map(momentum_df["Momentum (%)"])
        df["Z-Score"] = df[ticker_col].map(momentum_df["Z-Score"])
        df["Signal"] = df[ticker_col].map(momentum_df["Signal"])
        df["Action"] = df[ticker_col].map(momentum_df["Action"])
        df["Justification"] = df[ticker_col].map(momentum_df["Justification"])

    # Calcul des colonnes Valeur H52 et Valeur Actuelle
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    else:
        df["Valeur_H52"] = None # Initialize if columns don't exist
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    else:
        df["Valeur_Actuelle"] = None # Initialize if columns don't exist

    # Conversion Objectif_LT et calcul de Valeur_LT
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
    
    # Conversion en devise cible
    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise): return 0
        if devise.upper() == devise_cible.upper(): return val
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    if "Devise" in df.columns:
        df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
        df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
        df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
        df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)
    else:
        # If 'Devise' column is missing, assume all values are in the target currency
        df["Valeur_conv"] = df["Valeur"]
        df["Valeur_Actuelle_conv"] = df["Valeur_Actuelle"]
        df["Valeur_H52_conv"] = df["Valeur_H52"]
        df["Valeur_LT_conv"] = df["Valeur_LT"]
        
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Formatage des colonnes numériques pour l'affichage
    def format_fr(x, dec):
        if pd.isnull(x): return ""
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
        if col in df.columns: # Only format if the column exists
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))
        else: # Create an empty formatted column if the original doesn't exist
            df[f"{col}_fmt"] = ""

    # Préparer colonnes pour affichage et leurs labels
    cols_to_display = [
        ticker_col,
        "shortName",
        "Catégorie",
        "Devise",
        "Quantité_fmt",
        "Acquisition_fmt",
        "Valeur_fmt",
        "currentPrice_fmt",
        "Valeur_Actuelle_fmt",
        "fiftyTwoWeekHigh_fmt",
        "Valeur_H52_fmt",
        "Objectif_LT_fmt",
        "Valeur_LT_fmt",
        "Momentum (%)_fmt",
        "Z-Score_fmt",
        "Signal",
        "Action",
        "Justification"
    ]
    labels = [
        "Ticker",
        "Nom",
        "Catégorie",
        "Devise",
        "Quantité",
        "Prix d'Acquisition",
        "Valeur",
        "Prix Actuel",
        "Valeur Actuelle",
        "Haut 52 Semaines",
        "Valeur H52",
        "Objectif LT",
        "Valeur LT",
        "Momentum (%)",
        "Z-Score",
        "Signal",
        "Action",
        "Justification"
    ]
    
    # Filter out columns that don't exist in df to prevent errors
    actual_cols_to_display = [col for col in cols_to_display if col in df.columns or col.replace('_fmt','') in df.columns]
    actual_labels = [labels[cols_to_display.index(col)] for col in actual_cols_to_display]

    df_disp = df[actual_cols_to_display].copy()
    df_disp.columns = actual_labels

    # --- Tri du DataFrame pour l'affichage ---
    if "sort_column" not in st.session_state:
        st.session_state.sort_column = None
    if "sort_direction" not in st.session_state:
        st.session_state.sort_direction = "asc"

    # Convert query parameters to session_state
    # This is crucial for Streamlit to know how to sort on subsequent runs
    query_params = st.query_params
    if "sort_column" in query_params:
        st.session_state.sort_column = query_params["sort_column"]
    if "sort_direction" in query_params:
        st.session_state.sort_direction = query_params["sort_direction"]

    if st.session_state.sort_column:
        sort_col_label = st.session_state.sort_column
        # Find the original numeric column name if it's a formatted one
        original_col_name = None
        for k, v in dict(zip(cols_to_display, labels)).items():
            if v == sort_col_label:
                original_col_name = k.replace('_fmt', '')
                break

        if original_col_name in df.columns:
            # For numeric columns, use the original numeric data for sorting
            # Handle potential non-numeric data in original columns (e.g., initial CSV import)
            df_disp = df_disp.sort_values(
                by=sort_col_label,
                ascending=(st.session_state.sort_direction == "asc"),
                key=lambda x: pd.to_numeric(
                    df[original_col_name], errors="coerce"
                ).fillna(-float('inf'))
            )
        else:
            # For string columns, sort directly
            df_disp = df_disp.sort_values(
                by=sort_col_label,
                ascending=(st.session_state.sort_direction == "asc")
            )
            
    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)
    
    # Injection JS sécurisée
    # The JavaScript will now update query parameters, which then trigger a Streamlit rerun
    # Streamlit will then sort based on these updated query parameters
    safe_sort_column = safe_escape(str(st.session_state.get("sort_column", "")))
    safe_sort_direction = safe_escape(str(st.session_state.get("sort_direction", "asc")))
    
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
      .portfolio-table td:nth-child(16), /* Signal */
      .portfolio-table td:nth-child(17), /* Action */
      .portfolio-table td:nth-child(18) {{ /* Justification */
        text-align: left;
        white-space: normal;
      }}
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
      function sortTable(column) {{
        const currentSort = "{safe_sort_column}";
        const currentDirection = "{safe_sort_direction}";
        let direction = 'asc';
        if (currentSort === column) {{
          direction = currentDirection === 'asc' ? 'desc' : 'asc';
        }}
        // Use Streamlit's query parameters to trigger a rerun with sorting info
        // This avoids full page reload issues.
        window.parent.postMessage({{
          type: 'streamlit:setFrameHeight',
          height: document.body.scrollHeight
        }}, '*');
        window.parent.history.pushState({{}}, '', window.location.pathname + "?sort_column=" + encodeURIComponent(column) + "&sort_direction=" + direction);
      }}
    
      window.onload = function() {{
        const headers = document.querySelectorAll('.portfolio-table th');
        headers.forEach(header => {{
          if (header.textContent === currentSort) {{
            header.classList.add(currentDirection === 'asc' ? 'sort-asc' : 'sort-desc');
          }}
        }});
      }};
    </script>
    
    <div class="scroll-wrapper">
      <table class="portfolio-table">
        <thead><tr>
    """
    
    # Ajouter les en-têtes avec tri cliquable
    for lbl in actual_labels:
        html_code += f'<th onclick="sortTable(\'{safe_escape(lbl)}\')">{safe_escape(lbl)}</th>'
    
    html_code += """
        </tr></thead>
        <tbody>
    """
    
    # Corps du tableau
    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in actual_labels:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"
    
    # Ligne total
    html_code += f"""
        <tr class='total-row'>
          <td>TOTAL ({safe_escape(devise_cible)})</td>
          <td></td><td></td><td></td><td></td><td></td>
          <td>{safe_escape(total_valeur_str)}</td>
          <td></td>
          <td>{safe_escape(total_actuelle_str)}</td>
          <td></td>
          <td>{safe_escape(total_h52_str)}</td>
          <td></td>
          <td>{safe_escape(total_lt_str)}</td>
          <td></td><td></td><td></td><td></td><td></td>
        </tr>
        </tbody>
      </table>
    </div>
    """
    
    components.html(html_code, height=600, scrolling=True)

# --- Structure de l'application principale (exemple) ---
def main():
    st.set_page_config(layout="wide", page_title="Mon Portefeuille")
    st.title("Gestion de Portefeuille d'Investissement")

    # Sidebar pour l'importation de fichiers et les paramètres
    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("Choisissez un fichier CSV", type=["csv"])
        if uploaded_file is not None:
            try:
                df_uploaded = pd.read_csv(uploaded_file)
                st.session_state.df = df_uploaded
                st.success("Fichier importé avec succès !")
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier : {e}")
                st.session_state.df = None # Clear df on error

        st.header("Paramètres de Devise")
        st.session_state.devise_cible = st.selectbox(
            "Devise cible pour l'affichage",
            ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
            index=0 # Par défaut EUR
        )

    afficher_portefeuille()

if __name__ == "__main__":
    main()
