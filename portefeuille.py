import streamlit as st
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components
import yfinance as yf

def safe_escape(text):
    """Escape HTML characters safely."""
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")


