import streamlit as st
import pandas as pd
import datetime
import requests
import html
import streamlit.components.v1 as components

def obtenir_taux(devise_source, devise_cible):
    if devise_source == devise_cible:
        return 1.0
    ticker = f"{devise_cible.upper()}={devise_source.upper()}" if devise_cible == "USD" else f"{devise_source.upper()}{devise_cible.upper()}=X"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = { "User-Agent": "Mozilla/5.0" }

    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        return float(meta.get("regularMarketPrice", 0))
    except Exception as e:
        st.warning(f"Taux non disponible pour {devise_source}/{devise_cible} : {e}")
        return None

def afficher_taux_change():
    df = st.session_state.get("df")
    if df is None or "Devise" not in df.columns:
        st.info("Aucun portefeuille chargé.")
        return

    devise_cible = st.session_state.get("devise_cible", "EUR")
    devises_uniques = sorted(set(df["Devise"].dropna().unique()))
    taux_dict = {}

    with st.spinner("Mise à jour des taux de change depuis Yahoo Finance..."):
        for d in devises_uniques:
            taux = obtenir_taux(d, devise_cible)
            if taux:
                taux_dict[d] = taux

    st.session_state.fx_rates = taux_dict

    if not taux_dict:
        st.warning("Aucun taux de change valide récupéré.")
        return

    taux_df = pd.DataFrame(list(taux_dict.items()), columns=["Devise Source", f"Taux vers {devise_cible}"])
    taux_df[f"Taux vers {devise_cible}"] = taux_df[f"Taux vers {devise_cible}"].map(lambda x: f"{x:,.4f}".replace(",", " ").replace(".", ","))

    # Génération HTML harmonisée
    labels = list(taux_df.columns)
    html_code = f"""
<style>
  .table-container {{ max-height: 500px; overflow-y: auto; }}
  .portfolio-table {{ width: 100%; border-collapse: collapse; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
  .portfolio-table th {{
    background: #363636; color: white; padding: 6px; text-align: center; border: none;
    position: sticky; top: 0; z-index: 2; font-size: 12px; cursor: pointer;
  }}
  .portfolio-table td {{
    padding: 6px; text-align: center; border: none; font-size: 12px;
  }}
  .portfolio-table tr:nth-child(even) {{ background: #efefef; }}
</style>
<div class="table-container">
  <table class="portfolio-table">
    <thead><tr>
"""
    for i, label in enumerate(labels):
        html_code += f'<th onclick="sortTable({i})">{html.escape(label)}</th>'
    html_code += "</tr></thead><tbody>"

    for _, row in taux_df.iterrows():
        html_code += "<tr>"
        for val in row:
            val_str = str(val) if pd.notnull(val) else ""
            html_code += f"<td>{html.escape(val_str)}</td>"
        html_code += "</tr>"

    html_code += """
    </tbody>
  </table>
</div>
<script>
function sortTable(n) {
  var table = document.querySelector(".portfolio-table");
  var tbody = table.querySelector("tbody");
  var rows = Array.from(tbody.rows);
  var dir = table.querySelectorAll("th")[n].getAttribute("data-dir") || "asc";
  dir = (dir === "asc") ? "desc" : "asc";
  table.querySelectorAll("th").forEach(th => {
    th.removeAttribute("data-dir");
    th.innerHTML = th.innerHTML.replace(/ ▲| ▼/g, "");
  });
  table.querySelectorAll("th")[n].setAttribute("data-dir", dir);
  table.querySelectorAll("th")[n].innerHTML += dir === "asc" ? " ▲" : " ▼";

  rows.sort((a, b) => {
    var x = a.cells[n].textContent.trim().replace(",", ".");
    var y = b.cells[n].textContent.trim().replace(",", ".");
    var xNum = parseFloat(x.replace(/ /g, ""));
    var yNum = parseFloat(y.replace(/ /g, ""));
    if (!isNaN(xNum) && !isNaN(yNum)) {
      return dir === "asc" ? xNum - yNum : yNum - xNum;
    }
    return dir === "asc" ? x.localeCompare(y) : y.localeCompare(x);
  });
  tbody.innerHTML = "";
  rows.forEach(row => tbody.appendChild(row));
}
</script>
"""

    st.markdown(f"#### Taux de change appliqués vers la devise de référence **{devise_cible}** – _{datetime.datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}_")
    components.html(html_code, height=500, scrolling=True)
