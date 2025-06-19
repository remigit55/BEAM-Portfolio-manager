import streamlit as st
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()
    devise_cible = st.session_state.get("devise_cible", "EUR")
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

    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

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
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
                headers = { "User-Agent": "Mozilla/5.0" }
                r = requests.get(url, headers=headers, timeout=5)
                r.raise_for_status()
                data = r.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                name = meta.get("shortName", f"https://finance.yahoo.com/quote/{t}")
                current_price = meta.get("regularMarketPrice", None)
                fifty_two_week_high = meta.get("fiftyTwoWeekHigh", None)
                result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
                st.session_state.ticker_names_cache[t] = result
                time.sleep(0.5)
                return result
            except Exception:
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

        yahoo_data = df[ticker_col].apply(fetch_yahoo_data)
        df["shortName"] = yahoo_data.apply(lambda x: x["shortName"])
        df["currentPrice"] = yahoo_data.apply(lambda x: x["currentPrice"])
        df["fiftyTwoWeekHigh"] = yahoo_data.apply(lambda x: x["fiftyTwoWeekHigh"])

    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

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
    ]:
        if col in df.columns:
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))

    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise): return 0
        if devise == devise_cible: return val
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)

    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()

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
        "Objectif_LT_fmt",
        "Valeur_LT_fmt",
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
        "Objectif LT",
        "Valeur LT",
        "Devise"
    ]

    df_disp = df[cols].copy()
    df_disp.columns = labels

    html_code = f"""<style>
  .table-container {{ max-height: 500px; overflow-y: auto; }}
  .portfolio-table {{ width: 100%; border-collapse: collapse; table-layout: auto; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
  .portfolio-table th {{
    background: #363636; color: white; padding: 6px; text-align: center; border: none;
    position: sticky; top: 0; z-index: 2; font-size: 12px; cursor: pointer;
  }}
  .portfolio-table td {{
    padding: 6px; text-align: right; border: none; font-size: 11px;
  }}
  .portfolio-table td:first-child,
  .portfolio-table td:nth-child(2),
  .portfolio-table td:nth-child(3) {{
    text-align: left;
  }}
  .portfolio-table tr:nth-child(even) {{ background: #efefef; }}
  .total-row td {{
    background: #A49B6D; color: white; font-weight: bold;
  }}
</style>
<div class="table-container">
  <table class="portfolio-table">
    <thead><tr>"""
    for i, label in enumerate(labels):
        html_code += f'<th onclick="sortTable({i})">{html.escape(label)}</th>'
    html_code += "</tr></thead><tbody>"

    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in labels:
            val = row[lbl]
            val_str = str(val) if pd.notnull(val) else ""
            html_code += f"<td>{html.escape(val_str)}</td>"
        html_code += "</tr>"

    html_code += f"""
    </tbody>
    <tfoot>
      <tr class="total-row">
        <td>TOTAL ({devise_cible})</td><td></td><td></td><td></td><td></td>
        <td>{format_fr(total_valeur, 2)}</td>
        <td></td>
        <td>{format_fr(total_actuelle, 2)}</td>
        <td></td>
        <td>{format_fr(total_h52, 2)}</td>
        <td></td><td></td><td></td>
      </tr>
    </tfoot>
  </table>
</div>
<script>
function sortTable(n) {{
  var table = document.querySelector(".portfolio-table");
  var tbody = table.querySelector("tbody");
  var rows = Array.from(tbody.rows);
  var dir = table.querySelectorAll("th")[n].getAttribute("data-dir") || "asc";
  dir = (dir === "asc") ? "desc" : "asc";
  table.querySelectorAll("th").forEach(th => {{
    th.removeAttribute("data-dir");
    th.innerHTML = th.innerHTML.replace(/ ▲| ▼/g, "");
  }});
  table.querySelectorAll("th")[n].setAttribute("data-dir", dir);
  table.querySelectorAll("th")[n].innerHTML += dir === "asc" ? " ▲" : " ▼";

  rows.sort((a, b) => {{
    var x = a.cells[n].textContent.trim();
    var y = b.cells[n].textContent.trim();
    var xNum = parseFloat(x.replace(/ /g, "").replace(",", "."));
    var yNum = parseFloat(y.replace(/ /g, "").replace(",", "."));
    if (!isNaN(xNum) && !isNaN(yNum)) {{
      return dir === "asc" ? xNum - yNum : yNum - xNum;
    }}
    return dir === "asc" ? x.localeCompare(y) : y.localeCompare(x);
  }});
  tbody.innerHTML = "";
  rows.forEach(row => tbody.appendChild(row));
}}
</script>"""

    components.html(html_code, height=600, scrolling=True)
