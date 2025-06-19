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
        st.error(f"Erreur lors de la récupération des taux de change : {e}")
        return {}

@st.cache_data(ttl=900) # Cache Yahoo data for 15 minutes
def fetch_yahoo_data(ticker):
    ticker = str(ticker).strip().upper()
    if ticker in st.session_state.get("ticker_names_cache", {}):
        cached = st.session_state.ticker_names_cache[ticker]
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else: # Invalidate incomplete cache entries
            del st.session_state.ticker_names_cache[ticker]
            
    try:
        # Using yfinance directly for data fetching is more robust than manual requests to Yahoo API for chart data
        # For meta info, a direct call is often quicker if the yf.Ticker object is well-populated
        # However, for robustness with caching, sometimes simple direct requests are better to avoid
        # multiple calls from yfinance's internal methods. Your current request logic is okay.
        
        # Let's use yfinance.Ticker for more reliable access to info
        stock = yf.Ticker(ticker)
        info = stock.info # This fetches a lot of data, and can be slow if not cached properly
        
        name = info.get("shortName", f"https://finance.yahoo.com/quote/{ticker}")
        current_price = info.get("regularMarketPrice", None)
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", None)
        
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        
        # Initialize cache if it doesn't exist
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}
        st.session_state.ticker_names_cache[ticker] = result
        time.sleep(0.1) # Small delay to be polite to APIs
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
                "Last Price": None,
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
                "Last Price": round(latest['Close'], 2) if not pd.isna(latest['Close']) else None,
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
            "Last Price": round(latest['Close'], 2),
            "Momentum (%)": round(m, 2),
            "Z-Score": round(z, 2),
            "Signal": signal,
            "Action": action,
            "Justification": reason
        }
    except Exception as e:
        print(f"Erreur avec {ticker} pour l'analyse de momentum : {e}")
        return {
            "Last Price": None,
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
    # Ensure there are enough columns before trying to access index 5
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
        momentum_results = df[ticker_col].apply(fetch_momentum_data)
        # Convert list of dicts to a DataFrame
        momentum_df = pd.DataFrame(momentum_results.tolist(), index=df.index)
        
        # Merge momentum data back to the main DataFrame
        # Ensure the column names are consistent if you merge using specific columns
        df = pd.concat([df, momentum_df], axis=1)

    # Calcul des colonnes Valeur H52 et Valeur Actuelle
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

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
        if devise == devise_cible: return val
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
    
    # Prepare columns for display and formatting
    # Ensure all columns exist before trying to format them
    columns_to_format = {
        "Quantité": 0, "Acquisition": 4, "Valeur": 2, "currentPrice": 4,
        "fiftyTwoWeekHigh": 4, "Valeur_H52": 2, "Valeur_Actuelle": 2,
        "Objectif_LT": 4, "Valeur_LT": 2, "Momentum (%)": 2, "Z-Score": 2,
        "Last Price": 2 # Add Last Price for formatting
    }

    for col, dec in columns_to_format.items():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce') # Ensure numeric for formatting
            df[f"{col}_fmt"] = df[col].apply(lambda x: f"{x:,.{dec}f}".replace(",", " ").replace(".", ",") if pd.notnull(x) else "")
        else:
            # Create placeholder formatted columns if the original doesn't exist
            df[f"{col}_fmt"] = ""

    # Define columns to display and their labels
    display_cols_mapping = {
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
        "Last Price_fmt": "Last Price", # Ensure this column is mapped
        "Momentum (%)_fmt": "Momentum (%)",
        "Z-Score_fmt": "Z-Score",
        "Signal": "Signal",
        "Action": "Action",
        "Justification": "Justification"
    }

    # Filter out keys where the original column doesn't exist in df
    final_display_cols = [k for k, v in display_cols_mapping.items() if k.replace('_fmt', '') in df.columns or k in df.columns]
    final_labels = [display_cols_mapping[k] for k in final_display_cols]

    # Create the DataFrame for display with formatted columns
    df_disp = df[final_display_cols].copy()
    df_disp.columns = final_labels

    st.subheader(f"Portefeuille Actuel ({devise_cible})")

    # Use st.data_editor for interactive sorting
    # Key is important to uniquely identify the widget
    # The 'num_rows' parameter is important for performance if you have many rows.
    # Set it to 'dynamic' for auto-scrolling behavior.
    
    # Display the table using st.dataframe which offers built-in sorting
    st.dataframe(
        df_disp,
        height=400, # Control initial height
        use_container_width=True, # Make it fill the container
        hide_index=True # Hides the pandas DataFrame index
    )

    # Display totals below the table
    st.markdown(f"""
        ---
        **Totaux en {devise_cible}:**
        * Valeur d'Acquisition : **{total_valeur:.2f} {devise_cible}**
        * Valeur Actuelle : **{total_actuelle:.2f} {devise_cible}**
        * Valeur Haut 52 Semaines : **{total_h52:.2f} {devise_cible}**
        * Valeur Objectif Long Terme : **{total_lt:.2f} {devise_cible}**
    """)

    # Removed the custom HTML and JavaScript for sorting as st.dataframe handles it.
    # You no longer need the components.html call for the table itself.

# --- Main app structure (assuming you have a main part of your app) ---
# Example of how you might call this function:
# def main():
#     st.set_page_config(layout="wide", page_title="Mon Portefeuille")
#     st.title("Gestion de Portefeuille d'Investissement")
#
#     # Sidebar for file upload
#     with st.sidebar:
#         st.header("Importation de Données")
#         uploaded_file = st.file_uploader("Choisissez un fichier CSV", type=["csv"])
#         if uploaded_file is not None:
#             try:
#                 df_uploaded = pd.read_csv(uploaded_file)
#                 st.session_state.df = df_uploaded
#                 st.success("Fichier importé avec succès !")
#             except Exception as e:
#                 st.error(f"Erreur lors de la lecture du fichier : {e}")
#
#         st.header("Paramètres de Devise")
#         st.session_state.devise_cible = st.selectbox(
#             "Devise cible pour l'affichage",
#             ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
#             index=0 # Default to EUR
#         )
#
#     afficher_portefeuille()
#
# if __name__ == "__main__":
#     main()
