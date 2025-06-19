// sort_table.js
document.addEventListener('DOMContentLoaded', function() {
    function sortTable(n) {
        var table = document.querySelector(".portfolio-table");
        if (!table) return; // Ensure table exists
        var tbody = table.querySelector("tbody");
        if (!tbody) return; // Ensure tbody exists

        // Get all rows, including the total row
        var rows = Array.from(tbody.rows);
        
        // Find and remove the total row from the sorting array temporarily
        let totalRow = null;
        const sortableRows = rows.filter(row => {
            if (row.classList.contains('total-row')) {
                totalRow = row;
                return false; // Exclude from sorting
            }
            return true; // Include in sorting
        });

        var currentHeader = table.querySelectorAll("th")[n];
        if (!currentHeader) return; // Ensure header exists
        
        var dir = currentHeader.getAttribute("data-dir") || "asc";
        dir = (dir === "asc") ? "desc" : "asc";
        
        table.querySelectorAll("th").forEach(th => {
            th.removeAttribute("data-dir");
            th.classList.remove("sort-asc", "sort-desc");
            th.innerHTML = th.innerHTML.replace(' ▲', '').replace(' ▼', '');
        });
        
        currentHeader.setAttribute("data-dir", dir);
        currentHeader.classList.add(dir === "asc" ? "sort-asc" : "sort-desc");
        currentHeader.innerHTML += (dir === "asc" ? " ▲" : " ▼");

        sortableRows.sort((a, b) => {
            var x = a.cells[n].textContent.trim();
            var y = b.cells[n].textContent.trim();
        
            var xNum = parseFloat(x.replace(/ /g, "").replace(",", "."));
            var yNum = parseFloat(y.replace(/ /g, "").replace(",", "."));
        
            if (!isNaN(xNum) && !isNaN(yNum)) {
                if (isNaN(xNum) && !isNaN(yNum)) return dir === "asc" ? 1 : -1;
                if (!isNaN(xNum) && isNaN(yNum)) return dir === "asc" ? -1 : 1;
                if (isNaN(xNum) && isNaN(yNum)) return 0;
                
                return dir === "asc" ? xNum - yNum : yNum - xNum;
            }
            return dir === "asc" ? x.localeCompare(y, undefined, {sensitivity: 'base'}) : y.localeCompare(x, undefined, {sensitivity: 'base'});
        });
        
        tbody.innerHTML = ""; // Clear existing rows
        sortableRows.forEach(row => tbody.appendChild(row)); // Add sorted rows
        if (totalRow) {
            tbody.appendChild(totalRow); // Add total row back at the end
        }
    }

    const headers = document.querySelectorAll('.portfolio-table th');
    headers.forEach(header => {
        header.addEventListener('click', function() {
            const colIndex = parseInt(this.getAttribute('data-column-index'));
            if (!isNaN(colIndex)) {
                sortTable(colIndex);
            }
        });
    });
});
