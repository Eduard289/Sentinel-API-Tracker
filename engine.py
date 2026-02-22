import time
import requests
import threading
import ssl
import socket
from datetime import datetime
from flask import Flask, jsonify, request
from waitress import serve

app = Flask(__name__)

# --- BASE DE DATOS SIMULADA (Añadimos el sistema de Tags) ---
TARGETS = [
    {
        "id": "github_api", 
        "url": "https://api.github.com", 
        "tags": ["Producción", "API Externa"]
    },
    {
        "id": "httpbin_test", 
        "url": "https://httpbin.org/get", 
        "tags": ["Desarrollo", "Test"]
    }
]

# Aquí guardaremos los resultados en tiempo real
MONITOR_DATA = {}

# --- FUNCIONES DE ANÁLISIS PROFUNDO ---

def check_ssl_expiry(hostname):
    """Extrae los días restantes para que caduque el certificado SSL"""
    try:
        # Quitamos el https:// para el socket
        host = hostname.replace("https://", "").split("/")[0]
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                # Formato: 'Oct 23 12:00:00 2024 GMT'
                expire_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
                dias_restantes = (expire_date - datetime.utcnow()).days
                return dias_restantes
    except Exception:
        return "Error/No SSL"

def hacer_ping(target):
    """Realiza la petición y extrae todas las métricas avanzadas"""
    url = target["url"]
    resultado = {
        "url": url,
        "tags": target["tags"],
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "Timeout",
        "latencia_ms": 0,
        "payload_kb": 0,
        "rate_limit_restante": "N/A",
        "ssl_dias": "N/A"
    }
    
    try:
        # Extraemos el SSL (solo si es https)
        if url.startswith("https"):
            resultado["ssl_dias"] = check_ssl_expiry(url)

        # Hacemos la petición real
        r = requests.get(url, timeout=5)
        
        # Recopilación de métricas
        resultado["status"] = r.status_code
        resultado["latencia_ms"] = int(r.elapsed.total_seconds() * 1000)
        resultado["payload_kb"] = round(len(r.content) / 1024, 2)
        
        # Lector de Límites (Rate Limit Tracker)
        # Muchas APIs usan X-RateLimit-Remaining o RateLimit-Remaining
        rate_limit = r.headers.get('X-RateLimit-Remaining') or r.headers.get('RateLimit-Remaining')
        if rate_limit:
            resultado["rate_limit_restante"] = int(rate_limit)

    except requests.exceptions.RequestException:
        resultado["status"] = "Caído/Error"
        
    return resultado

# --- EL CORAZÓN DEL MONITOR (HILO EN SEGUNDO PLANO) ---

def motor_monitorizacion():
    """Bucle infinito que actualiza los datos cada 5 segundos sin bloquear el servidor"""
    print("🚀 Motor de monitorización iniciado en segundo plano...")
    while True:
        for target in TARGETS:
            # En producción, esto se haría con un ThreadPool para escanear en paralelo
            MONITOR_DATA[target["id"]] = hacer_ping(target)
        
        # Espera 5 segundos antes de la siguiente ronda
        time.sleep(5)

# --- RUTAS DE LA API (FLASK) ---

@app.route('/api/status')
def get_status():
    """El frontend en JS llamará aquí cada 2 segundos para actualizar la pantalla"""
    return jsonify(MONITOR_DATA)

@app.route('/api/stress/<target_id>', methods=['POST'])
def stress_test(target_id):
    """Simulador de Estrés (Modo Ataque)"""
    target = next((t for t in TARGETS if t["id"] == target_id), None)
    if not target:
        return jsonify({"error": "Target no encontrado"}), 404
        
    def ataque(url, num_peticiones):
        print(f"🔥 Iniciando MODO ATAQUE a {url} con {num_peticiones} peticiones...")
        for _ in range(num_peticiones):
            try: requests.get(url, timeout=2)
            except: pass
        print(f"🛑 Ataque a {url} finalizado.")

    # Lanzamos el ataque en OTRO hilo para no bloquear a Waitress ni a los demás usuarios
    hilo_ataque = threading.Thread(target=ataque, args=(target["url"], 50))
    hilo_ataque.start()
    
    return jsonify({"mensaje": f"Modo estrés iniciado contra {target['url']} (50 peticiones)"})

# --- ARRANQUE CON WAITRESS ---
if __name__ == "__main__":
    # 1. Arrancamos el latido del monitor de URLs
    hilo_monitor = threading.Thread(target=motor_monitorizacion, daemon=True)
    hilo_monitor.start()
    
    # 2. Arrancamos el servidor de producción Waitress
    print("🌐 Servidor API levantado en el puerto 8080. Listo para recibir al Frontend.")
    serve(app, host='0.0.0.0', port=8080, threads=8)
