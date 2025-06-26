# utils.py

import pandas as pd
import numpy as np
from babel.numbers import format_decimal

def safe_escape(text):
    """Escapes HTML special characters in a string."""
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#039;")

def format_fr(number, decimal_places=2):
    """
    Formats a number to French locale (1 000,00) with specified decimal places.
    Handles NaN values.
    """
    if pd.isna(number):
        return "N/A" # Or an empty string, or '-' depending on preference
    try:
        # Use Babel for proper locale-aware formatting
        return format_decimal(number, locale='fr_FR', format=f'#,##0.{ "0" * decimal_places if decimal_places > 0 else "" }')
    except Exception:
        # Fallback for non-numeric or other issues
        return str(number)

def format_fr(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) else x

# You might have other utility functions here as well
