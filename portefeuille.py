import streamlit as st
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components
import yfinance as yf # Keep imports for now

def safe_escape(text):
    """Escape HTML characters safely."""
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

# ... (keep fetch_fx_rates and other functions as they are, but they won't be fully exercised with this test)

def afficher_portefeuille():
    # TEMPORARY TEST: Render a very simple HTML table
    test_html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Minimal Test Table</title>
        <style>
            table, th, td {
                border: 1px solid black;
                border-collapse: collapse;
                padding: 8px;
                text-align: left;
            }
        </style>
    </head>
    <body>
        <h1>Simple Portfolio Test</h1>
        <p>This is a test table to check Streamlit HTML component.</p>
        <div class="scroll-wrapper" style="overflow: auto; max-height: 300px;">
            <table class="portfolio-table">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Quantity</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>AAPL</td>
                        <td>10</td>
                        <td>$1800</td>
                    </tr>
                    <tr>
                        <td>GOOG</td>
                        <td>5</td>
                        <td>$800</td>
                    </tr>
                    <tr>
                        <td>MSFT</td>
                        <td>12</td>
                        <td>$2500</td>
                    </tr>
                     <tr>
                        <td>TSLA</td>
                        <td>3</td>
                        <td>$450</td>
                    </tr>
                     <tr>
                        <td>AMZN</td>
                        <td>7</td>
                        <td>$1100</td>
                    </tr>
                </tbody>
            </table>
        </div>
        </body>
    </html>
    """
    st.write("Attempting to render a minimal HTML table...")
    components.html(test_html_code, height=600, scrolling=True, key="minimal_test_portfolio_table")
    st.write("Minimal HTML table rendering attempt finished.")

# --- Structure de l'application principale ---
def main():
    st.set_page_config(layout="wide", page_title="Mon Portefeuille")
    st.title("Gestion de Portefeuille d'Investissement")

    # Sidebar for file upload and settings (keep these, they don't affect the HTML test directly)
    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("Choisissez un fichier CSV", type=["csv"])
        if uploaded_file is not None:
            try:
                df_uploaded = pd.read_csv(uploaded_file)
                st.session_state.df = df_uploaded # Still store it, but afficher_portefeuille won't use it for HTML rendering in this test
                st.success("Fichier importé avec succès !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier : {e}")
                st.session_state.df = None

        st.header("Paramètres de Devise")
        selected_devise = st.selectbox(
            "Devise cible pour l'affichage",
            ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
            index=["EUR", "USD", "GBP", "JPY", "CAD", "CHF"].index(st.session_state.get("devise_cible", "EUR"))
        )
        if selected_devise != st.session_state.get("devise_cible", "EUR"):
            st.session_state.devise_cible = selected_devise
            st.rerun()

    afficher_portefeuille()

if __name__ == "__main__":
    main()
