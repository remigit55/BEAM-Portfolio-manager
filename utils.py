# utils.py
import pandas as pd
import numpy as np
from babel.numbers import format_decimal

def safe_escape(text):
    """Escapes HTML special characters in a string."""
    if text is None:
        return ""
    return str(text).replace("&", "&").replace("<", "<").replace(">", ">").replace('"', """).replace("'", "'")

def format_fr(number, decimal_places=2):
    """
    Formats a number to French locale (1 000,00) with specified decimal places.
    Handles NaN, None, and non-numeric values robustly.
    """
    if number is None or pd.isna(number):
        return "N/A"
    if not isinstance(number, (int, float, np.number)):
        return "N/A"  # Return "N/A" for non-numeric types
    try:
        return format_decimal(float(number), locale='fr_FR', format=f'#,##0.{ "0" * decimal_places if decimal_places > 0 else "" }')
    except (ValueError, TypeError) as e:
        return "N/A"  # Fallback for formatting errors
