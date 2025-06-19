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
        # st.error(f"Erreur lors de la récupération des taux de change : {e}") # Use st.error for user feedback
        print(f"Erreur lors de la récupération des taux : {e}") # Keep print for debugging in console
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
        # Ensure cached data is a valid dictionary with shortName
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else: # Invalidate incomplete cache entries to re-fetch
            del st.session_state.ticker_names_cache[ticker]
    
    try:
        # Use yfinance.Ticker to fetch information reliably
        # This is generally more robust than direct API calls for Yahoo
        stock = yf.Ticker(ticker)
        # Fetching info can be slow, caching is essential here
        info = stock.info 
        
        name = info.get("shortName", f"https://finance.yahoo.com/quote/{ticker}")
        current_price = info.get("regularMarketPrice", None)
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", None)
        
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        st.session_state.ticker_names_cache[ticker] = result
        time.sleep(0.05) # Small delay to be polite to APIs and avoid rate limiting
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

        # Determine Signal, Action, Justification based on Z-Score
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
    else:
        df["Valeur"] = None # Ensure column exists

    # Ajout de la colonne Catégorie depuis la colonne F du CSV (index 5)
    if df.shape[1] > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    # Get ticker column name
    ticker_col = next((col for col in TICKER_COL_NAMES if col in df.columns), None)

    if ticker_col:
        # Ensure ticker column values are strings and not NaN for Yahoo/Momentum lookup
        df[ticker_col] = df[ticker_col].astype(str).fillna('')
        
        # Collect all unique tickers to fetch data only once
        unique_tickers = df[ticker_col].loc[df[ticker_col] != ''].unique()

        # Fetch Yahoo data for unique tickers
        yahoo_data_dict = {t: fetch_yahoo_data(t) for t in unique_tickers}
        # Map fetched data back to the DataFrame
        df["shortName"] = df[ticker_col].map(lambda x: yahoo_data_dict.get(x, {}).get("shortName"))
        df["currentPrice"] = df[ticker_col].map(lambda x: yahoo_data_dict.get(x, {}).get("currentPrice"))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda x: yahoo_data_dict.get(x, {}).get("fiftyTwoWeekHigh"))

        # Fetch Momentum data for unique tickers
        momentum_data_dict = {t: fetch_momentum_data(t) for t in unique_tickers}
        # Map fetched momentum data back to the DataFrame
        df["Momentum (%)"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Momentum (%)"))
        df["Z-Score"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Z-Score"))
        df["Signal"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Signal"))
        df["Action"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Action"))
        df["Justification"] = df[ticker_col].map(lambda x: momentum_data_dict.get(x, {}).get("Justification"))
    else:
        # Initialize columns if no ticker column is found
        df["shortName"] = None
        df["currentPrice"] = None
        df["fiftyTwoWeekHigh"] = None
        df["Momentum (%)"] = None
        df["Z-Score"] = None
        df["Signal"] = None
        df["Action"] = None
        df["Justification"] = None

    # Calcul des colonnes Valeur H52 et Valeur Actuelle
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    else:
        df["Valeur_H52"] = None 
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    else:
        df["Valeur_Actuelle"] = None 

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
        # If 'Devise' column is missing, assume all values are in the target currency
        df["Valeur_conv"] = df["Valeur"].fillna(0) # Ensure no NaN for sum
        df["Valeur_Actuelle_conv"] = df["Valeur_Actuelle"].fillna(0)
        df["Valeur_H52_conv"] = df["Valeur_H52"].fillna(0)
        df["Valeur_LT_conv"] = df["Valeur_LT"].fillna(0)
        
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Formatage des colonnes numériques pour l'affichage
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
        if col in df.columns: # Only format if the column exists
            # Ensure the column is numeric before mapping for formatting
            df[col] = pd.to_numeric(df[col], errors='coerce') 
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))
        else: # Create an empty formatted column if the original doesn't exist
            df[f"{col}_fmt"] = ""

    # Préparer colonnes pour affichage et leurs labels
    # Important: s'assurer que ces colonnes sont celles qui existeront dans df_disp
    cols_to_display_raw = [
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
        "Momentum (%)_fmt", # Formatted column
        "Z-Score_fmt",      # Formatted column
        "Signal",           # Raw column, likely string
        "Action",           # Raw column, likely string
        "Justification"     # Raw column, likely string
    ]
    labels_raw = [
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
    
    # Filter out columns that might not exist in df before selecting
    # And create a mapping from internal column name to display label
    df_columns_available = df.columns.tolist() # Get actual columns in df

    actual_display_cols = []
    actual_labels = []
    
    for i, col_name in enumerate(cols_to_display_raw):
        if col_name in df_columns_available:
            actual_display_cols.append(col_name)
            actual_labels.append(labels_raw[i])
        elif col_name.replace('_fmt','') in df_columns_available and col_name.endswith('_fmt'):
             # If original non-formatted column exists, then the formatted one should too
            actual_display_cols.append(col_name)
            actual_labels.append(labels_raw[i])

    df_disp = df[actual_display_cols].copy()
    df_disp.columns = actual_labels

    # --- Tri du DataFrame pour l'affichage ---
    # Récupération des paramètres de tri (depuis l'URL)
    query_params = st.query_params
    sort_column_from_url = query_params.get("sort_column", None)
    sort_direction_from_url = query_params.get("sort_direction", "asc")
    
    # Appliquer le tri au DataFrame df_disp
    if sort_column_from_url in df_disp.columns:
        sort_col_label = sort_column_from_url
        
        # Try to find the original numeric column name for sorting if it's a formatted column
        original_numeric_col = None
        for raw_col, label in zip(cols_to_display_raw, labels_raw):
            if label == sort_col_label:
                original_numeric_col = raw_col.replace('_fmt', '')
                break

        if original_numeric_col and original_numeric_col in df.columns:
            # If it's a numeric column (like Quantité, Valeur, Momentum (%)), sort by its numeric value
            # Create a Series for sorting from the original DataFrame `df`
            sort_series = pd.to_numeric(df[original_numeric_col], errors="coerce")
            df_disp = df_disp.iloc[sort_series.argsort(
                ascending=(sort_direction_from_url == "asc"),
                na_position='last' # Puts NaN/None values at the end
            )]
        else:
            # For string or other columns, sort directly on the displayed string value
            df_disp = df_disp.sort_values(
                by=sort_col_label,
                ascending=(sort_direction_from_url == "asc"),
                key=lambda x: x.astype(str).str.lower() if x.dtype == 'object' else x # Case-insensitive sort for strings
            )
            
    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)
    
    # Injection JS sécurisée
    # IMPORTANT: The JavaScript here will trigger a full page reload by setting window.location.href.
    # This is the trade-off for having Python-driven sorting with custom HTML.
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
        min-width: 2200px; /* Adjusted min-width if needed */
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
      /* Adjust nth-child for left-aligned columns based on your current labels list */
      /* Ticker (1), Nom (2), Catégorie (3), Signal (16), Action (17), Justification (18) */
      .portfolio-table td:nth-child(1),
      .portfolio-table td:nth-child(2),
      .portfolio-table td:nth-child(3),
      .portfolio-table td:nth-child(16), 
      .portfolio-table td:nth-child(17), 
      .portfolio-table td:nth-child(18) {{
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
      const currentSort = "{safe_sort_column}";
      const currentDirection = "{safe_sort_direction}";
    
      function sortTable(column) {{
        let direction = 'asc';
        if (currentSort === column) {{
          direction = currentDirection === 'asc' ? 'desc' : 'asc';
        }}
        // This will cause a full page reload (and thus a Streamlit re-run).
        // This is necessary if Python handles the sorting logic on the server-side.
        const newPath = window.location.pathname + "?sort_column=" + encodeURIComponent(column) + "&sort_direction=" + direction;
        window.location.href = newPath;
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
                st.session_state.df = None # Clear df on error to prevent displaying old data

        st.header("Paramètres de Devise")
        st.session_state.devise_cible = st.selectbox(
            "Devise cible pour l'affichage",
            ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
            index=0 # Par défaut EUR
        )

    afficher_portefeuille()

if __name__ == "__main__":
    main()
