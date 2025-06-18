import streamlit as st
import pandas as pd
import requests
import time

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Debug: Display CSV columns
    st.write(f"CSV columns: {df.columns.tolist()}")

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

    # Ajout de la colonne Catégorie depuis la colonne F du CSV
    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    # Récupération de shortName, Current Price et 52 Week High via Yahoo Finance
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    if ticker_col:
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}

        def fetch_yahoo_data(t):
            t = str(t).strip().upper()
            if t in st.session_state.ticker_names_cache:
                cached = st.session_state.ticker_names_cache[t]
                if isinstance(cached, dict) and "shortName" in cached:
                    return cached
                else:
                    del st.session_state.ticker_names_cache[t]

            if not t or not t.replace(".", "").isalnum():
                print(f"Ticker invalide ignoré : {t}")
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}
        
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                r = requests.get(url, headers=headers, timeout=5)
                r.raise_for_status()

                data = r.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                name = meta.get("shortName", "")
                current_price = meta.get("regularMarketPrice", None)
                fifty_two_week_high = meta.get("fiftyTwoWeekHigh", None)
                
                if not name:
                    name = f"https://finance.yahoo.com/quote/{t}"
                
                result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
                st.session_state.ticker_names_cache[t] = result
                time.sleep(0.5)
                return result
            except Exception as e:
                print(f"Erreur pour {t}: {e}")
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

        yahoo_data = df[ticker_col].apply(fetch_yahoo_data)
        df["shortName"] = yahoo_data.apply(lambda x: x["shortName"] if isinstance(x, dict) else f"https://finance.yahoo.com/quote/{t}")
        df["currentPrice"] = yahoo_data.apply(lambda x: x["currentPrice"] if isinstance(x, dict) else None)
        df["fiftyTwoWeekHigh"] = yahoo_data.apply(lambda x: x["fiftyTwoWeekHigh"] if isinstance(x, dict) else None)

    # Calcul des colonnes Valeur H52 et Valeur Actuelle
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

    # Formatage : français + création des colonnes *_fmt
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
        ("Valeur_Actuelle", 2)
    ]:
        if col in df.columns:
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))

    # Préparer colonnes pour affichage
    cols = [
        ticker_col,
        "shortName",
        "Catégorie",
        "Quantité_fmt",
        "Acquisition_fmt",
        "Valeur_fmt",
        "currentPrice_fmt",
        "Valeur_Actuelle_fmt",
        "fiftyTwoWeekHigh_fmt",
        "Valeur_H52_fmt",
        "Devise"
    ]
    labels = [
        "Ticker",
        "Nom",
        "Catégorie",
        "Quantité",
        "Prix d'Acquisition",
        "Valeur",
        "Prix Actuel",
        "Valeur Actuelle",
        "Haut 52 Semaines",
        "Valeur H52",
        "Devise"
    ]
    df_disp = df[cols].copy()
    df_disp.columns = labels

    total_str = format_fr(df["Valeur"].sum() if "Valeur" in df.columns else 0, 2)

    # Construction HTML
    html = f"""
    <style>
      .table-container {{ 
        max-height: 500px; /* Increased to ensure TOTAL row visibility */
        overflow-y: auto; 
        overflow-x: auto; 
        width: 100%;
        position: relative;
      }}
      .portfolio-table {{ 
        min-width: 1500px; /* Large width to trigger horizontal scroll */
        border-collapse: collapse; 
        table-layout: fixed; 
      }}
      .portfolio-table th {{
        background: #363636; 
        color: white; 
        padding: 6px; 
        text-align: center; 
        border: 1px solid #ddd; /* Debug border */
        position: sticky; 
        top: 0; 
        z-index: 10; /* Headers above content */
        font-family: "Aptos narrow", Helvetica; 
        font-size: 12px;
      }}
      .portfolio-table td {{
        padding: 6px; 
        text-align: right; 
        border: 1px solid #ddd; /* Debug border */
        font-family: "Aptos narrow", Helvetica; 
        font-size: 11px;
        background: #fff;
      }}
      .portfolio-table tr:nth-child(even) td {{ background: #efefef; }}
      /* Figer les colonnes Ticker et Nom */
      .portfolio-table th:nth-child(1), .portfolio-table td:nth-child(1) {{ /* Ticker */
        position: sticky; 
        left: 0; 
        text-align: left; 
        width: 50px; /* Narrow Ticker */
        z-index: 5; /* Below headers */
        background: #fff;
      }}
      .portfolio-table th:nth-child(2), .portfolio-table td:nth-child(2) {{ /* Nom */
        position: sticky; 
        left: 50px; /* Match Ticker width */
        text-align: left; 
        width: 200px; /* Wider for names */
        z-index: 5;
        background: #fff;
      }}
      /* Ensure headers stay above */
      .portfolio-table th:nth-child(1) {{ z-index: 15; }}
      .portfolio-table th:nth-child(2) {{ z-index: 15; }}
      /* Match even row background */
      .portfolio-table tr:nth-child(even) td:nth-child(1),
      .portfolio-table tr:nth-child(even) td:nth-child(2) {{ background: #efefef; }}
      .portfolio-table td:nth-child(3) {{ text-align: left; width: 100px; }} /* Catégorie */
      /* Largeur fixe pour colonnes numériques */
      .portfolio-table th:nth-child(4), .portfolio-table td:nth-child(4), /* Quantité */
      .portfolio-table th:nth-child(5), .portfolio-table td:nth-child(5), /* Prix d'Acquisition */
      .portfolio-table th:nth-child(6), .portfolio-table td:nth-child(6), /* Valeur */
      .portfolio-table th:nth-child(7), .portfolio-table td:nth-child(7), /* Prix Actuel */
      .portfolio-table th:nth-child(8), .portfolio-table td:nth-child(8), /* Valeur Actuelle */
      .portfolio-table th:nth-child(9), .portfolio-table td:nth-child(9), /* Haut 52 Semaines */
      .portfolio-table th:nth-child(10), .portfolio-table td:nth-child(10) {{ /* Valeur H52 */
        width: 100px;
      }}
      .total-row td {{
        background: #A49B6D; 
        color: white; 
        font-weight: bold;
        position: sticky; /* Ensure TOTAL row is visible */
        bottom: 0; /* Stick to bottom if scrolling */
        z-index: 5;
      }}
    </style>
    <div class="table-container">
      <table class="portfolio-table">
        <thead><tr>{''.join(f'<th>{lbl}</th>' for lbl in labels)}</tr></thead>
        <tbody>
    """

    for _, row in df_disp.iterrows():
        html += "<tr>"
        for lbl in labels:
            html += f"<td>{row[lbl] or ''}</td>"
        html += "</tr>"

    # Ligne TOTAL
    html += "<tr class='total-row'>"
    html += "<td>TOTAL</td><td></td><td></td><td></td>"  # Ticker, Nom, Catégorie, Quantité
    html += f"<td>{total_str}</td>"  # Valeur
    html += "<td></td><td></td><td></td><td></td><td></td><td></td>"  # Prix d'Acquisition, Prix Actuel, Valeur Actuelle, Haut 52 Semaines, Valeur H52, Devise
    html += "</tr>"
    html += "</tbody></table></div>"

    # Debug: Display raw HTML
    # st.text("Raw HTML:")
    # st.code(html)

    st.markdown(html, unsafe_allow_html=True)
