import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import App from './App'
import { ProveedorAuth } from './auth'
import { ProveedorTiempoReal } from './tiempo-real'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ProveedorAuth>
        <ProveedorTiempoReal>
          <App />
        </ProveedorTiempoReal>
      </ProveedorAuth>
    </BrowserRouter>
  </React.StrictMode>,
)
