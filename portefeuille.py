import streamlit as st
import pandas as pd
import requests
import time

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

    # Ajout de la colonne Catégorie depuis la colonne F du CSV
    if len(df.columns) > 5:  # Vérifier si la colonne F (index 5) existe
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")  # Convertir en string, gérer NaN
    else:
        df["Catégorie"] = ""  # Colonne vide si F n'existe pas

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
    html_parts = []

    # JavaScript (placé en premier pour être chargé avant le tableau)
    html_parts.append("""
<script>
function sortTable(n) {
  try {
    console.log("sortTable called with column: " + n);
    var table = document.getElementById("portfolioTable");
    var tbody = document.getElementById("tableBody");
    if (!table || !tbody) {
      console.error("Table or tbody not found");
      return;
    }
    var rows = Array.from(tbody.getElementsByTagName("tr")).slice(0, -1);
    console.log("Rows found: " + rows.length);
    var dir = table.getElementsByTagName("TH")[n].getAttribute("data-sort-dir") || "asc";
    dir = (dir === "asc") ? "desc" : "asc";
    table.getElementsByTagName("TH")[n].setAttribute("data-sort-dir", dir);
    var headers = table.getElementsByTagName("TH");
    for (var i = 0; i < headers.length; i++) {
      headers[i].innerHTML = headers[i].innerHTML.replace(/ ▼| ▲/, "");
    }
    headers[n].innerHTML += (dir === "asc") ? " ▲" : " ▼";
    rows.sort((rowA, rowB) => {
      var x = rowA.getElementsByTagName("TD")[n].innerHTML.trim();
      var y = rowB.getElementsByTagName("TD")[n].innerHTML.trim();
      console.log("Comparing: " + x + " vs " + y);
      if (x === "" && y === "") return 0;
      if (x === "") return dir === "asc" ? -1 : 1;
      if (y === "") return dir === "asc" ? 1 : -1;
      var xValue = parseFloat(x.replace(/ /g, "").replace(",", "."));
      var yValue = parseFloat(y.replace(/ /g, "").replace(",", "."));
      if (!isNaN(xValue) && !isNaN(yValue)) {
        return dir === "asc" ? xValue - yValue : yValue - xValue;
      }
      xValue = x.toLowerCase();
      yValue = y.toLowerCase();
      return dir === "asc" ? xValue.localeCompare(yValue) : yValue.localeCompare(xValue);
    });
    tbody.innerHTML = "";
    rows.forEach(row => tbody.appendChild(row));
    var totalRow = tbody.getElementsByTagName("tr")[rows.length] || table.querySelector("tr.total-row");
    if (totalRow) {
      tbody.appendChild(totalRow);
    } else {
      console.error("Total row not found");
    }
  } catch (e) {
    console.error("Error in sortTable: " + e.message);
  }
}
</script>
""")

    # CSS
    html_parts.append("""
<style>
  .table-container { max-height:400px; overflow-y:auto; }
  .portfolio-table { width:100%; border-collapse:collapse; table-layout:auto; }
  .portfolio-table th {
    background:#363636; color:white; padding:6px; text-align:center; border:none;
    position:sticky; top:0; z-index:2;
    font-family:"Aptos narrow",Helvetica; font-size:12px;
    cursor:pointer;
  }
  .portfolio-table th:hover {
    background:#4a4a4a;
  }
  .portfolio-table td {
    padding:6px; text-align:right; border:none;
    font-family:"Aptos narrow",Helvetica; font-size:11px;
  }
  .portfolio-table td:first-child { text-align:left; }
  .portfolio-table td:nth-child(2) { text-align:left; }
  .portfolio-table td:nth-child(3) { text-align:left; }
  .portfolio-table th:nth-child(4), .portfolio-table td:nth-child(4),
  .portfolio-table th:nth-child(5), .portfolio-table td:nth-child(5),
  .portfolio-table th:nth-child(6), .portfolio-table td:nth-child(6),
  .portfolio-table th:nth-child(7), .portfolio-table td:nth-child(7),
  .portfolio-table th:nth-child(8), .portfolio-table td:nth-child(8),
  .portfolio-table th:nth-child(9), .portfolio-table td:nth-child(9),
  .portfolio-table th:nth-child(10), .portfolio-table td:nth-child(10) {
    width: 9%;
  }
  .portfolio-table tr:nth-child(even) { background:#efefef; }
  .total-row td {
    background:#A49B6D; color:white; font-weight:bold;
  }
</style>
""")

    # Début du tableau
    html_parts.append("""
<div class="table-container">
  <table class="portfolio-table" id="portfolioTable">
    <thead>
      <tr>
""")

    # En-têtes
    for i, label in enumerate(labels):
        html_parts.append(f'<th onclick="sortTable({i})">{label}</th>')

    # Fin des en-têtes et début du corps
    html_parts.append("""
      </tr>
    </thead>
    <tbody id="tableBody">
""")

    # Lignes de données
    for _, row in df_disp.iterrows():
        html_parts.append("<tr>")
        for label in labels:
            cell_value = row[label] if pd.notnull(row[label]) else ''
            html_parts.append(f"<td>{cell_value}</td>")
        html_parts.append("</tr>")

    # Ligne TOTAL
    html_parts.append(f"""
      <tr class="total-row">
        <td>TOTAL</td>
        <td></td><td></td><td></td>
        <td>{total_str}</td>
        <td></td><td></td><td></td><td></td><td></td><td></td>
      </tr>
    </tbody>
  </table>
</div>
""")

    # Combiner toutes les parties
    html = "".join(html_parts)

    st.markdown(html, unsafe_allow_html=True)
