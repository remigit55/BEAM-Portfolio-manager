import React from 'react';
import ReactDOM from 'react-dom/client';
import PeriodSelector from './PeriodSelector';
import { Streamlit } from 'streamlit-component-lib';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <PeriodSelector />
  </React.StrictMode>
);

Streamlit.setComponentReady();
