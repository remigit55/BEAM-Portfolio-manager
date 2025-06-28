# utils.py (exemple, assurez-vous que votre fonction est similaire)

def format_fr(number, decimals=2):
    """
    Formate un nombre pour l'affichage français (virgule décimale, espace pour milliers).
    """
    if pd.isna(number):
        return ""
    try:
        # Convertir en chaîne avec le bon nombre de décimales
        s_number = f"{number:.{decimals}f}"
        
        # Remplacer le point décimal par une virgule
        s_number = s_number.replace('.', ',')
        
        # Ajouter les espaces pour les milliers
        parts = s_number.split(',')
        integer_part = parts[0]
        
        # Insérer les espaces tous les 3 chiffres à partir de la fin pour la partie entière
        formatted_integer = ""
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                formatted_integer = " " + formatted_integer
            formatted_integer = digit + formatted_integer
            
        if len(parts) > 1:
            return f"{formatted_integer},{parts[1]}"
        else:
            return formatted_integer
    except (ValueError, TypeError):
        return str(number) # Fallback if formatting fails

def safe_escape(text):
    """
    Échappe les caractères HTML spéciaux pour éviter les problèmes d'affichage.
    N'est plus strictement nécessaire pour st.dataframe, mais peut être utile ailleurs.
    """
    if not isinstance(text, str):
        text = str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#039;")
