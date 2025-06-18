# Construction HTML
html = f"""
<style>
  .table-container {{ max-height:400px; overflow-y:auto; }}
  .portfolio-table {{ width:100%; border-collapse:collapse; table-layout:auto; }} /* Changé à auto pour largeur dynamique */
  .portfolio-table th {{
    background:#363636; color:white; padding:6px; text-align:center; border:none;
    position:sticky; top:0; z-index:2;
    font-family:"Aptos narrow",Helvetica; font-size:12px;
    cursor:pointer; /* Curseur pour indiquer que c'est cliquable */
  }}
  .portfolio-table td {{
    padding:6px; text-align:right; border:none;
    font-family:"Aptos narrow",Helvetica; font-size:11px;
  }}
  .portfolio-table td:first-child {{ text-align:left; }}
  .portfolio-table td:nth-child(2) {{ text-align:left; }} /* Alignement à gauche pour Nom */
  .portfolio-table td:nth-child(3) {{ text-align:left; }} /* Alignement à gauche pour Catégorie */
  /* Largeur fixe pour les colonnes numériques */
  .portfolio-table th:nth-child(4), .portfolio-table td:nth-child(4), /* Quantité */
  .portfolio-table th:nth-child(5), .portfolio-table td:nth-child(5), /* Prix d'Acquisition */
  .portfolio-table th:nth-child(6), .portfolio-table td:nth-child(6), /* Valeur */
  .portfolio-table th:nth-child(7), .portfolio-table td:nth-child(7), /* Prix Actuel */
  .portfolio-table th:nth-child(8), .portfolio-table td:nth-child(8), /* Valeur Actuelle */
  .portfolio-table th:nth-child(9), .portfolio-table td:nth-child(9), /* Haut 52 Semaines */
  .portfolio-table th:nth-child(10), .portfolio-table td:nth-child(10) {{ /* Valeur H52 */
    width: 9%;
  }}
  .portfolio-table tr:nth-child(even) {{ background:#efefef; }}
  .total-row td {{
    background:#A49B6D; color:white; font-weight:bold;
  }}
</style>
<div class="table-container">
  <table class="portfolio-table" id="portfolioTable">
    <thead>
      <tr>
        {''.join(f'<th onclick="sortTable({i})">{lbl}</th>' for i, lbl in enumerate(labels))}
      </tr>
    </thead>
    <tbody id="tableBody">
"""

# Ajout des lignes de données
for _, row in df_disp.iterrows():
    html += "<tr>"
    for lbl in labels:
        html += f"<td>{row[lbl] or ''}</td>"
    html += "</tr>"

# Ligne TOTAL
html += "<tr class='total-row'><td>TOTAL</td>"
html += "<td></td><td></td><td></td>"  # Pour Nom, Catégorie, Quantité
html += f"<td>{total_str}</td>"  # Prix d'Acquisition
html += "<td></td><td></td><td></td><td></td><td></td><td></td></tr>"  # Pour Valeur, Prix Actuel, Valeur Actuelle, Haut 52 Semaines, Valeur H52, Devise
html += """
    </tbody>
  </table>
</div>
<script>
function sortTable(n) {{
  var table = document.getElementById("portfolioTable");
  var tbody = document.getElementById("tableBody");
  var rows = Array.from(tbody.getElementsByTagName("tr")).slice(0, -1); // Exclure la ligne TOTAL
  var switching = true;
  var dir = "asc";
  var switchcount = 0;

  // Obtenir l'état de tri précédent pour cette colonne
  var prevDir = table.getElementsByTagName("TH")[n].getAttribute("data-sort-dir") || "asc";
  if (prevDir === "asc") {{
    dir = "desc";
  }} else if (prevDir === "desc") {{
    dir = "asc";
  }}
  table.getElementsByTagName("TH")[n].setAttribute("data-sort-dir", dir);

  while (switching) {{
    switching = false;
    for (var i = 0; i < rows.length - 1; i++) {{
      var shouldSwitch = false;
      var x = rows[i].getElementsByTagName("TD")[n];
      var y = rows[i + 1].getElementsByTagName("TD")[n];
      var xContent = x.innerHTML.trim();
      var yContent = y.innerHTML.trim();

      // Convertir en nombre si possible pour les colonnes numériques
      var xValue = isNaN(parseFloat(xContent.replace(/ /g, "").replace(",", "."))) ? xContent.toLowerCase() : parseFloat(xContent.replace(/ /g, "").replace(",", "."));
      var yValue = isNaN(parseFloat(yContent.replace(/ /g, "").replace(",", "."))) ? yContent.toLowerCase() : parseFloat(yContent.replace(/ /g, "").replace(",", "."));

      if (dir == "asc") {{
        if (xValue > yValue) {{
          shouldSwitch = true;
          break;
        }}
      }} else if (dir == "desc") {{
        if (xValue < yValue) {{
          shouldSwitch = true;
          break;
        }}
      }}
    }}
    if (shouldSwitch) {{
      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
      switching = true;
      switchcount++;
    }} else {{
      if (switchcount == 0 && dir == "asc") {{
        dir = "desc";
        switching = true;
      }}
    }}
  }}
}}
</script>
"""

st.markdown(html, unsafe_allow_html=True)
