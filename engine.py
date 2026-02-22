
import time
import requests
import threading
import ssl
import socket
from datetime import datetime
from flask import Flask, jsonify, request, render_template
from waitress import serve

app = Flask(__name__)

# --- BASE DE DATOS EN MEMORIA ---
TARGETS = [
    {"id": "github_api", "url": "https://api.github.com", "tags": ["Producción", "API"]},
    {"id": "apple_test", "url": "https://apple.com", "tags": ["Corporativo", "Demo"]}
]

MONITOR_DATA = {}

# --- FUNCIONES DE ANÁLISIS OSINT & GEOLOCALIZACIÓN ---
def check_port(host, port):
    """Escáner de puertos rápido"""
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return "⚠️ ABIERTO"
    except:
        return "🔒 Cerrado"

def get_mx_record(domain):
    """Obtiene el servidor de correo vía API de DNS pública"""
    try:
        r = requests.get(f"https://dns.google/resolve?name={domain}&type=MX", timeout=2)
        data = r.json()
        if 'Answer' in data:
            mx = data['Answer'][0]['data'].split(' ')[-1]
            return mx.strip('.')
        return "No configurado"
    except:
        return "Desconocido"

def get_geolocation(ip):
    """Resuelve la ubicación física y el ISP de la dirección IP"""
    if ip in ["Buscando...", "Oculta"]: 
        return "Desconocida"
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
        data = r.json()
        if data.get("status") == "success":
            country = data.get("country", "")
            city = data.get("city", "")
            isp = data.get("isp", "")
            return f"{country}, {city} ({isp})"
        return "Ubicación oculta"
    except:
        return "No localizada"

def hacer_ping(target):
    """Ejecuta toda la batería de pruebas contra la URL"""
    url = target["url"]
    host_limpio = url.replace("https://", "").replace("http://", "").split("/")[0]
    
    resultado = {
        "url": url, "tags": target["tags"], "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "Timeout", "latencia_ms": 0, "payload_kb": 0, "ip": "Buscando...", "geo": "Buscando...",
        "server": "Desconocido", "rate_limit_restante": "N/A", "ssl_dias": "N/A",
        "puertos": "Escaneando...", "seguridad": "Analizando...", 
        "enlaces": "Crawleando...", "mx": "Buscando..."
    }
    
    try:
        # 1. IP, Puertos y GEOLOCALIZACIÓN
        try:
            resultado["ip"] = socket.gethostbyname(host_limpio)
            resultado["geo"] = get_geolocation(resultado["ip"])
            port_22 = check_port(resultado["ip"], 22)
            port_3306 = check_port(resultado["ip"], 3306)
            resultado["puertos"] = f"22:{port_22} | 3306:{port_3306}"
        except:
            resultado["ip"] = "Oculta"
            resultado["geo"] = "Desconocida"
            resultado["puertos"] = "Bloqueado por firewall"

        # 2. Correo MX
        resultado["mx"] = get_mx_record(host_limpio)

        # 3. SSL
        if url.startswith("https"): 
            try:
                context = ssl.create_default_context()
                with socket.create_connection((host_limpio, 443), timeout=1) as sock:
                    with context.wrap_socket(sock, server_hostname=host_limpio) as ssock:
                        cert = ssock.getpeercert()
                        expire_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
                        resultado["ssl_dias"] = (expire_date - datetime.utcnow()).days
            except: pass
            
        # 4. Petición HTTP principal (Latencia, Cabeceras y Spider HTML)
        r = requests.get(url, timeout=4)
        resultado["status"] = r.status_code
        resultado["latencia_ms"] = int(r.elapsed.total_seconds() * 1000)
        resultado["payload_kb"] = round(len(r.content) / 1024, 2)
        resultado["server"] = r.headers.get('Server', 'Oculto')
        
        # Auditoría de Cabeceras
        hsts = "✅" if "Strict-Transport-Security" in r.headers else "❌"
        xframe = "✅" if "X-Frame-Options" in r.headers else "❌"
        resultado["seguridad"] = f"HSTS: {hsts} | X-Frame: {xframe}"
        
        # Spider de Enlaces
        html = r.text.lower()
        ext_links = html.count('href="http') - html.count(f'href="https://{host_limpio}')
        int_links = html.count('href="/') + html.count(f'href="https://{host_limpio}')
        resultado["enlaces"] = f"Int: {max(0, int_links)} | Ext: {max(0, ext_links)}"

    except requests.exceptions.RequestException:
        resultado["status"] = "Caído/Error"
        
    return resultado

# --- EL CORAZÓN DEL MONITOR ---
def motor_monitorizacion():
    """Hilo en segundo plano que refresca los datos constantemente"""
    print("Motor OSINT iniciado. Escaneando URLs...")
    while True:
        for target in list(TARGETS):
            MONITOR_DATA[target["id"]] = hacer_ping(target)
        time.sleep(5)

# --- RUTAS DE LA API (Flask) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    return jsonify(MONITOR_DATA)

@app.route('/api/add', methods=['POST'])
def add_target():
    data = request.json
    url = data.get('url', '').strip()
    if url:
        if not url.startswith('http'): url = 'https://' + url
        new_id = url.replace('https://', '').replace('http://', '').split('/')[0]
        if not any(t['id'] == new_id for t in TARGETS):
            TARGETS.append({"id": new_id, "url": url, "tags": ["Análisis", "Dinámico"]})
        return jsonify({"status": "ok"})
    return jsonify({"error": "URL vacía"}), 400

@app.route('/api/stress/<target_id>', methods=['POST'])
def stress_test(target_id):
    target = next((t for t in TARGETS if t["id"] == target_id), None)
    if not target: return jsonify({"error": "Target no encontrado"}), 404
    
    def ataque(url):
        for _ in range(50):
            try: requests.get(url, timeout=2)
            except: pass
            
    threading.Thread(target=ataque, args=(target["url"],)).start()
    return jsonify({"mensaje": "Ataque en curso"})

# --- ARRANQUE CON WAITRESS ---
if __name__ == "__main__":
    # Arrancamos el motor de escaneo en un hilo independiente
    threading.Thread(target=motor_monitorizacion, daemon=True).start()
    
    print("Levantando servidor de producción Waitress en el puerto 8080...")
    serve(app, host='0.0.0.0', port=8080, threads=8)8)
