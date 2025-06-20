# utils.py

import html
import pandas as pd

def safe_escape(text):
    """Escape HTML characters safely."""
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

def format_fr(x, dec):
    """
    Formate un nombre en chaîne de caractères avec la virgule comme séparateur décimal
    et l'espace comme séparateur de milliers (format français).
    """
    if pd.isnull(x):
        return ""
    s = f"{x:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",")
