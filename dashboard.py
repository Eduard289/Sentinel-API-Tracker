import streamlit as st
import pandas as pd
import requests
import threading
import time
import socket
import ssl
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sentinel OSINT", page_icon="🛰️", layout="wide")

# Estilo Cardo
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cardo:ital,wght@0,400;0,700;1,400&display=swap');
    html, body, [class*="css"], .stText, .stMarkdown, p, h1, h2, h3 {
        font-family: 'Cardo', serif !important;
    }
    footer { font-family: 'Cardo', serif; color: #666; text-align: center; padding: 20px; font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

# --- MOTOR INTEGRADO (Lógica que antes estaba en engine.py) ---
if "targets" not in st.session_state:
    st.session_state.targets = [
        {"id": "github", "url": "https://api.github.com", "tags": ["Producción"]},
        {"id": "apple", "url": "https://apple.com", "tags": ["Demo"]}
    ]

if "monitor_data" not in st.session_state:
    st.session_state.monitor_data = {}

if "historial" not in st.session_state:
    st.session_state.historial = []

def get_geolocation(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
        data = r.json()
        if data.get("status") == "success":
            return f"{data.get('country')}, {data.get('city')} ({data.get('isp')})"
        return "Desconocida"
    except: return "No localizada"

def check_target(target):
    url = target["url"]
    host = url.replace("https://", "").replace("http://", "").split("/")[0]
    res = {"url": url, "status": "Error", "latencia": 0, "ip": "---", "geo": "---", "timestamp": datetime.now().strftime("%H:%M:%S")}
    try:
        start = time.time()
        r = requests.get(url, timeout=3)
        res["latencia"] = int((time.time() - start) * 1000)
        res["status"] = r.status_code
        res["ip"] = socket.gethostbyname(host)
        res["geo"] = get_geolocation(res["ip"])
    except: pass
    return res

# --- INTERFAZ ---
st.title("Sentinel OSINT Tracker")

# Panel de entrada
col_in1, col_in2 = st.columns([3, 1])
new_url = col_in1.text_input("Añadir URL para análisis:", placeholder="https://ejemplo.com")
if col_in2.button("Monitorizar") and new_url:
    new_id = str(time.time())
    st.session_state.targets.append({"id": new_id, "url": new_url, "tags": ["Dinámico"]})

# Ciclo de escaneo manual (Streamlit no permite hilos infinitos de escritura fácilmente)
# Actualizamos los datos cada vez que la página refresca
for t in st.session_state.targets:
    resultado = check_target(t)
    st.session_state.monitor_data[t["id"]] = resultado
    
    # Guardar en historial para la gráfica
    fila = {"Hora": resultado["timestamp"], "URL": resultado["url"], "Latencia": resultado["latencia"]}
    st.session_state.historial.append(fila)

# Mostrar Tarjetas
cols = st.columns(len(st.session_state.targets))
for i, (tid, info) in enumerate(st.session_state.monitor_data.items()):
    with cols[i]:
        color = "green" if info["status"] == 200 else "red"
        st.subheader(info["url"].split("//")[-1])
        st.markdown(f"**Estado:** :{color}[{info['status']}]")
        st.markdown(f"**Latencia:** {info['latencia']} ms")
        st.markdown(f"**IP:** {info['ip']}")
        st.markdown(f"**Geo:** {info['geo']}")

# Gráfica Histórica
if st.session_state.historial:
    st.divider()
    df = pd.DataFrame(st.session_state.historial)
    # Pivotamos para que cada URL sea una línea
    df_chart = df.pivot_table(index="Hora", columns="URL", values="Latencia").tail(20)
    st.line_chart(df_chart)

st.markdown("<footer>jose luis asenjo</footer>", unsafe_allow_html=True)

# Botón de refresco automático (Simulado)
if st.button("Actualizar métricas ahora"):
    st.rerun()
