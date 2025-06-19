# test_streamlit.py
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide") # Conservez le layout wide pour la cohérence
st.title("Mon Application de Test Simple")

st.write("Ceci est un texte simple.")

# Test avec components.html
simple_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Test HTML</title>
</head>
<body>
    <h1>Bonjour, Monde !</h1>
    <p>Ceci est un test pour components.html.</p>
</body>
</html>
"""
try:
    components.html(simple_html, height=200, scrolling=False, key="simple_html_test")
    st.success("components.html a fonctionné !")
except Exception as e:
    st.error(f"Erreur lors de l'affichage de components.html: {e}")

# Test avec st.dataframe (pour référence future)
import pandas as pd
data_test = pd.DataFrame({'Col A': [1, 2], 'Col B': ['X', 'Y']})
st.dataframe(data_test)
