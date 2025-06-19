import streamlit.components.v1 as components
import time # Ensure time is imported if you use it for the key

def afficher_portefeuille():
    # ... (rest of your existing code to process data, but DON'T generate the large HTML yet)

    # Temporary: Test with a small, static HTML string
    test_html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Table</title>
    </head>
    <body>
        <h1>Hello from Streamlit!</h1>
        <table border="1">
            <thead>
                <tr><th>Header 1</th><th>Header 2</th></tr>
            </thead>
            <tbody>
                <tr><td>Data 1</td><td>Data 2</td></tr>
                <tr><td>Data 3</td><td>Data 4</td></tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    components.html(test_html_code, height=600, scrolling=True, key=f"portfolio_table_component_test_{time.time()}")

    # ... (rest of your existing code, maybe related to displaying other elements)
