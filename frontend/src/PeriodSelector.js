import React, { useEffect, useState } from 'react';
import { Streamlit } from 'streamlit-component-lib';
import './PeriodSelector.css'; // Importe le fichier CSS

function PeriodSelector() {
  // Récupère les arguments passés depuis Python
  const periodLabels = Streamlit.args.period_labels;
  const initialSelectedLabel = Streamlit.args.selected_label;

  // État local pour gérer la période sélectionnée
  const [selectedLabel, setSelectedLabel] = useState(initialSelectedLabel);

  // Met à jour l'état local si la valeur initiale change (ex: via st.session_state en Python)
  useEffect(() => {
    setSelectedLabel(initialSelectedLabel);
  }, [initialSelectedLabel]);

  // Ajuste la hauteur de l'iframe Streamlit après le rendu
  useEffect(() => {
    Streamlit.setFrameHeight();
  }); // Pas de dépendances pour qu'il s'exécute après chaque rendu

  // Gère le clic sur une étiquette de période
  const handleClick = (label) => {
    setSelectedLabel(label); // Met à jour l'état local
    Streamlit.setComponentValue(label); // Envoie la valeur sélectionnée à Streamlit (Python)
  };

  return (
    <div className="period-selector-container">
      {periodLabels.map((label) => (
        <span
          key={label}
          className={`period-item ${selectedLabel === label ? 'selected' : ''}`}
          onClick={() => handleClick(label)}
        >
          {label}
        </span>
      ))}
    </div>
  );
}

export default PeriodSelector;
