import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sentinel Analytics", 
    page_icon="🛰️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilo para forzar la fuente Cardo y colores oscuros
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cardo:ital,wght@0,400;0,700;1,400&display=swap');
    html, body, [class*="css"] {
        font-family: 'Cardo', serif;
    }
    h1, h2, h3 { color: #58a6ff !important; font-family: 'Cardo', serif; }
    </style>
""", unsafe_allow_html=True)

st.title("🛰️ Sentinel OSINT - Centro de Análisis en Tiempo Real")
st.markdown("Monitorización de latencia y estabilidad de objetivos.")

# --- CONEXIÓN AL MOTOR ---
API_URL = "http://127.0.0.1:8080/api/status"

# Inicializamos la memoria del gráfico si es la primera vez que carga
if "historial" not in st.session_state:
    st.session_state.historial = []

# Espacios vacíos que actualizaremos en bucle
kpi_placeholder = st.empty()
chart_placeholder = st.empty()

st.caption("💡 *Nota: Si lanzas un Test de Estrés desde el panel de control, verás el pico de latencia reflejado aquí en unos segundos.*")

# --- BUCLE DE TIEMPO REAL ---
while True:
    try:
        # 1. Preguntamos al motor de Python cómo están las webs
        respuesta = requests.get(API_URL, timeout=2)
        datos = respuesta.json()
        
        # 2. Preparamos la fila de datos con la hora actual
        hora_actual = datetime.now().strftime("%H:%M:%S")
        fila = {"Hora": hora_actual}
        
        # 3. Extraemos la latencia de cada web
        for id_objetivo, info in datos.items():
            nombre_limpio = info['url'].replace('https://', '').replace('http://', '')
            fila[nombre_limpio] = info['latencia_ms']
            
        # 4. Guardamos en la memoria y borramos los datos antiguos (mantenemos últimos 50 puntos)
        st.session_state.historial.append(fila)
        if len(st.session_state.historial) > 50:
            st.session_state.historial.pop(0)
            
        # 5. Convertimos a tabla de Pandas para dibujar
        df = pd.DataFrame(st.session_state.historial).set_index("Hora")
        
        # --- DIBUJAMOS LA INTERFAZ ---
        with kpi_placeholder.container():
            columnas = st.columns(len(datos))
            for i, (id_objetivo, info) in enumerate(datos.items()):
                nombre_limpio = info['url'].replace('https://', '').replace('http://', '')
                estado = "🟢 ONLINE" if info['status'] == 200 else "🔴 OFFLINE"
                columnas[i].metric(
                    label=f"{nombre_limpio} ({estado})", 
                    value=f"{info['latencia_ms']} ms",
                    delta=f"{info['payload_kb']} KB"
                )
        
        with chart_placeholder.container():
            st.subheader("Evolución de Latencia (ms)")
            st.line_chart(df, height=400, use_container_width=True)
            
    except Exception as e:
        st.error("⚠️ Buscando conexión con el motor Sentinel... Asegúrate de ejecutar primero engine.py")
        
    # Esperamos 3 segundos antes de actualizar la gráfica
    time.sleep(3)
