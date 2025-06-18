import streamlit as st
import pandas as pd
import requests

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

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

    # Récupération de shortName via Yahoo Finance (v8/chart)
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    if ticker_col:
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}

        def fetch_shortname(t):
            t = str(t).strip().upper()
            if t in st.session_state.ticker_names_cache:
                return st.session_state.ticker_names_cache[t]
        
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
                r = requests.get(url, timeout=5)
                name = ""
                if r.ok:
                    meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    name = meta.get("shortName", "")
                if not name:
                    # Si aucun nom trouvé, on met l’URL publique de Yahoo Finance
                    name = f"https://finance.yahoo.com/quote/{t}"
                st.session_state.ticker_names_cache[t] = name
                return name
            except:
                return f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"


        df["shortName"] = df[ticker_col].apply(fetch_shortname)

    # Formatage : français + création des colonnes *_fmt
    def format_fr(x, dec):
        if pd.isnull(x): return ""
        s = f"{x:,.{dec}f}"
        return s.replace(",", " ").replace(".", ",")

    for col, dec in [("Quantité", 0), ("Acquisition", 4), ("Valeur", 2)]:
        if col in df.columns:
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))

    # Préparer colonnes pour affichage
    cols = [ticker_col, "shortName", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt", "Devise"]
    labels = ["Ticker", "Nom", "Quantité", "Prix d'Acquisition", "Valeur", "Devise"]
    df_disp = df[cols].copy()
    df_disp.columns = labels

    total_str = format_fr(df["Valeur"].sum() if "Valeur" in df.columns else 0, 2)

    # Construction HTML
    html = f"""
    <style>
      .table-container {{ max-height:400px; overflow-y:auto; }}
      .portfolio-table {{ width:100%; border-collapse:collapse; }}
      .portfolio-table th {{
        background:#363636; color:white; padding:6px; text-align:center; border:none;
        position:sticky; top:0; z-index:2;
        font-family:"Aptos narrow",Helvetica; font-size:12px;
      }}
      .portfolio-table td {{
        padding:6px; text-align:right; border:none;
        font-family:"Aptos narrow",Helvetica; font-size:11px;
      }}
      .portfolio-table td:first-child {{ text-align:left; }}
      .portfolio-table tr:nth-child(even) {{ background:#efefef; }}
      .total-row td {{
        background:#A49B6D; color:white; font-weight:bold;
      }}
    </style>
    <div class="table-container">
      <table class="portfolio-table">
        <thead><tr>{''.join(f'<th>{lbl}</th>' for lbl in labels)}</tr></thead><tbody>
    """

    for _, row in df_disp.iterrows():
        html += "<tr>"
        for lbl in labels:
            html += f"<td>{row[lbl] or ''}</td>"
        html += "</tr>"

    # Ligne TOTAL
    html += "<tr class='total-row'><td>TOTAL</td>"
    html += "<td></td><td></td><td></td>"
    html += f"<td>{total_str}</td><td></td></tr>"
    html += "</tbody></table></div>"

    st.markdown(html, unsafe_allow_html=True)
