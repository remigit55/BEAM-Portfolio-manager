import React from 'react';
import ReactDOM from 'react-dom/client'; // Utilisation de createRoot pour React 18+
import PeriodSelector from './PeriodSelector';
import { Streamlit } from 'streamlit-component-lib';

// Utilisation de createRoot pour le rendu concurrent (React 18+)
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <PeriodSelector />
  </React.StrictMode>
);

// Initialisation de Streamlit après le rendu initial
Streamlit.setComponentReady();
