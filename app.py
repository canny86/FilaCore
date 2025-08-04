from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import json
import requests
import threading
import paho.mqtt.client as mqtt
import time
import ssl
import shutil
import subprocess
import logging
import random

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), "static")
PRINTERS_FILE = os.path.join(STATIC_FOLDER, "printers.json")
ACTIVE_PRINTER_FILE = os.path.join(STATIC_FOLDER, "active_printer.json")

def fetch_certificate(ip: str, save_path: str) -> bool:
    print(f"[fetch_certificate] Starte Zertifikatsabruf für IP: {ip}")
    try:
        cmd = [
            "openssl", "s_client", "-showcerts", "-connect", f"{ip}:8883"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        print(f"[fetch_certificate] OpenSSL Rückgabe-Code: {result.returncode}")
        if result.stderr:
            print(f"[fetch_certificate] OpenSSL STDERR: {result.stderr.strip()}")
        if not result.stdout:
            print("[fetch_certificate] Keine OpenSSL STDOUT Ausgabe erhalten")
            return False

        certs = []
        capture = False
        for line in result.stdout.splitlines():
            if "-----BEGIN CERTIFICATE-----" in line:
                capture = True
                certs.append(line)
            elif "-----END CERTIFICATE-----" in line:
                certs.append(line)
                capture = False
            elif capture:
                certs.append(line)

        if not certs:
            print("[fetch_certificate] Keine Zertifikate im Output gefunden!")
            return False

        with open(save_path, "w") as f:
            f.write("\n".join(certs))

        print(f"[fetch_certificate] Zertifikat erfolgreich gespeichert unter: {save_path}")
        return True
    except subprocess.TimeoutExpired:
        print(f"[fetch_certificate] Fehler: OpenSSL-Befehl für {ip} hat zu lange gedauert")
        return False
    except Exception as e:
        print(f"[fetch_certificate] Ausnahmefehler beim Zertifikat holen für {ip}: {e}")
        return False

def load_printers():
    if not os.path.exists(PRINTERS_FILE):
        return []
    with open(PRINTERS_FILE, "r") as f:
        return json.load(f)

def save_printers(printers):
    with open(PRINTERS_FILE, "w") as f:
        json.dump(printers, f, indent=2)

@app.route("/")
def index():
    return "FilaCore läuft"
@app.route("/filacore")
def filacore_ui():
    return send_from_directory(app.static_folder, "filacore.html")

@app.route("/api/filamente", methods=["GET"])
def get_filamente():
    return jsonify([])  # später JSON-Datei einlesen

@app.route("/api/druckerstatus", methods=["GET"])
def drucker_status():
    return jsonify({"status": "bereit", "verbindung": True})  # später WebSocket


@app.route("/add_printer", methods=["POST"])
def add_printer():
    data = request.json
    serial = data.get("serial")
    access_code = data.get("access_code")
    ip = data.get("ip")
    name = data.get("name", f"Drucker {serial}")

    if not (serial and access_code and ip):
        return jsonify({"error": "serial, access_code und ip sind erforderlich"}), 400

    printers = load_printers()
    if any(p["serial"] == serial for p in printers):
        return jsonify({"error": "Drucker mit dieser Serial existiert bereits"}), 400
    if any(p["name"] == name for p in printers):
        return jsonify({"error": "Name wird bereits verwendet"}), 400

    printers.append({
        "serial": serial,
        "access_code": access_code,
        "ip": ip,
        "name": name
    })
    save_printers(printers)

    # Zertifikat-Ordner anlegen
    cert_dir = os.path.join(STATIC_FOLDER, "printers", name)
    os.makedirs(cert_dir, exist_ok=True)

    # Zertifikat asynchron holen
    cert_path = os.path.join(cert_dir, "blcert.pem")
    threading.Thread(target=fetch_certificate, args=(ip, cert_path), daemon=True).start()

    return jsonify({"success": True, "message": "Drucker hinzugefügt, Zertifikat wird erstellt"})

@app.route("/delete_printer", methods=["POST"])
def delete_printer():
    try:
        data = request.json
        serial = data.get("serial")

        if not serial:
            return jsonify({"error": "serial ist erforderlich"}), 400

        printers = load_printers()
        printer_to_delete = next((p for p in printers if p["serial"] == serial), None)

        if not printer_to_delete:
            return jsonify({"error": "Kein Drucker mit dieser Serial gefunden"}), 404

        new_list = [p for p in printers if p["serial"] != serial]
        save_printers(new_list)

        # Ordner des Druckers löschen, wenn vorhanden
        printer_name = printer_to_delete.get("name")
        if printer_name:
            cert_dir = os.path.join(app.static_folder, "printers", printer_name)
            if os.path.exists(cert_dir) and os.path.isdir(cert_dir):
                shutil.rmtree(cert_dir)

        return jsonify({"success": True, "message": "Drucker gelöscht"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_printers", methods=["GET"])
def get_printers():
    try:
        printers = load_printers()
        return jsonify(printers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/set_active_printer", methods=["POST"])
def set_active_printer():
    data = request.json
    serial = data.get("serial")
    if not serial:
        return jsonify({"error": "serial ist erforderlich"}), 400

    printers = load_printers()
    found = None

    # Nur einer darf aktiv sein
    for p in printers:
        if p["serial"] == serial:
            p["active"] = True
            found = p
        else:
            p["active"] = False

    if not found:
        return jsonify({"error": "Drucker nicht gefunden"}), 404

    # Save updated printers.json
    with open(PRINTERS_FILE, "w") as f:
        json.dump(printers, f, indent=2)

    # Zertifikat wie gehabt prüfen/besorgen:
    cert_folder = os.path.join(STATIC_FOLDER, "printers", found["name"])
    cert_path = os.path.join(cert_folder, "blcert.pem")
    if not os.path.exists(cert_path):
        os.makedirs(cert_folder, exist_ok=True)
        threading.Thread(target=fetch_certificate, args=(found["ip"], cert_path), daemon=True).start()
        return jsonify({"success": True, "message": "Aktiver Drucker gesetzt. Zertifikat wird angefordert."})
    else:
        return jsonify({"success": True, "message": "Aktiver Drucker gesetzt. Zertifikat ist vorhanden."})
@app.route("/create_cert/<printer_name>", methods=["POST"])
def create_cert(printer_name):
    try:
        printers = load_printers()
        printer = next((p for p in printers if p["name"] == printer_name), None)
        if not printer:
            return jsonify({"error": "Drucker nicht gefunden"}), 404

        ip = printer.get("ip")
        if not ip:
            return jsonify({"error": "IP-Adresse im Druckereintrag fehlt"}), 400

        cert_dir = os.path.join(app.static_folder, "printers", printer_name)
        os.makedirs(cert_dir, exist_ok=True)
        cert_path = os.path.join(cert_dir, "blcert.pem")

        success = fetch_certificate(ip, cert_path)
        if not success:
            return jsonify({"error": "Zertifikat konnte nicht erstellt werden"}), 500

        return jsonify({"success": True, "message": "Zertifikat erfolgreich erstellt"})
    except Exception as e:
        # Ausgabe des genauen Fehlers im Log
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Interner Serverfehler: {str(e)}"}), 500
@app.route("/printer_state", methods=["GET"])
def printer_state():
    try:
        active_path = os.path.join(app.static_folder, "active_printer.json")
        if not os.path.exists(active_path):
            return jsonify({"error": "Kein aktiver Drucker gesetzt"}), 400
        with open(active_path, "r") as f:
            printer = json.load(f)

        serial = printer.get("serial")
        access_code = printer.get("access_code")

        if not serial or not access_code:
            return jsonify({"error": "Druckerdaten unvollständig"}), 400

        url = "https://api.bambulab.com/v1/printer/state"
        payload = {
            "serial": serial,
            "access_code": access_code
        }
        headers = {"Content-Type": "application/json"}

        res = requests.post(url, json=payload, headers=headers, timeout=8)
        if res.status_code != 200:
            return jsonify({"error": "Fehler beim Abrufen", "status": res.status_code}), 500

        return jsonify(res.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/read_mqtt_state", methods=["GET"])
def read_mqtt_state():
    try:
        # 1. Drucker mit active:true aus printers.json suchen
        printers_path = os.path.join(app.static_folder, "printers.json")
        if not os.path.exists(printers_path):
            return jsonify({"error": "Kein printers.json gefunden"}), 400

        with open(printers_path, "r") as f:
            printers = json.load(f)

        printer = next((p for p in printers if p.get("active")), None)
        if not printer:
            return jsonify({"error": "Kein aktiver Drucker"}), 400

        serial = printer.get("serial")
        access_code = printer.get("access_code")
        broker_ip = printer.get("ip")
        broker_port = 8883
        username = "bblp"
        password = access_code
        drucker_name = printer.get("name")

        if not serial or not access_code or not broker_ip or not drucker_name:
            return jsonify({"error": "Fehlende Druckerdaten"}), 400

        topic = f"device/{serial}/report"
        messages = []

        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                client.subscribe(topic)
            else:
                print(f"MQTT-Verbindungsfehler: {rc}")

        def on_message(client, userdata, msg):
            messages.append(msg.payload.decode())
            client.disconnect()  # sofort nach erster Nachricht trennen

        client = mqtt.Client()
        client.username_pw_set(username, password)
        client.on_connect = on_connect
        client.on_message = on_message

        # Zertifikat jetzt im jeweiligen Druckerordner unter printers/
        cert_path = os.path.join(app.static_folder, "printers", drucker_name, "blcert.pem")
        client.tls_set(ca_certs=cert_path)
        client.tls_insecure_set(True)  # Nur für Test/Self-Signed

        client.connect(broker_ip, broker_port, 10)
        client.loop_start()

        timeout = time.time() + 5
        while time.time() < timeout and not messages:
            time.sleep(0.1)

        client.loop_stop()

        if messages:
            return jsonify({"data": json.loads(messages[0])})
        else:
            return jsonify({"error": "Kein MQTT-Datenempfang"}), 504

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/druckprofile', methods=['GET'])
def get_druckprofile():
    try:
        path = os.path.join(app.static_folder, 'druckprofile.json')
        if not os.path.exists(path):
            return jsonify({"error": "Druckprofile nicht gefunden"}), 404
        with open(path, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
FILAMENT_FILE = os.path.join(os.path.dirname(__file__), "static", "filacore_spools.json")

def load_filaments():
    if not os.path.exists(FILAMENT_FILE):
        return []
    with open(FILAMENT_FILE, "r") as f:
        return json.load(f)

def save_filaments(filaments):
    with open(FILAMENT_FILE, "w") as f:
        json.dump(filaments, f, indent=2)

@app.route('/api/save_filament', methods=['POST'])
def save_filament():
    try:
        data = request.json
        fcid = data.get('fcid')
        material = data.get('material')
        druckprofil = data.get('druckprofil')
        farbe = data.get('farbe')
        hersteller = data.get('hersteller')
        preis = data.get('preis')
        temp_min = data.get('tempMin') or data.get('temp_min') or data.get('tempMin')
        temp_max = data.get('tempMax') or data.get('temp_max') or data.get('tempMax')

        if not all([material, druckprofil, farbe, hersteller, preis, temp_min, temp_max]):
            return jsonify({"error": "Alle Felder sind erforderlich"}), 400

        filaments = load_filaments()

        # Neue FCID erzeugen, falls nicht gesetzt
        if not fcid:
            import uuid
            fcid = str(uuid.uuid4())

        # Neues Filament-Dict mit ID an erster Stelle (OrderedDict könnte optional sein)
        new_filament = {
            "fcid": fcid,
            "material": material,
            "druckprofil": druckprofil,
            "farbe": farbe,
            "hersteller": hersteller,
            "preis": preis,
            "temp_min": temp_min,
            "temp_max": temp_max
        }

        filaments.append(new_filament)

        save_filaments(filaments)

        return jsonify({"success": True, "message": "Filament gespeichert", "fcid": fcid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/delete_filament', methods=['POST'])
def delete_filament():
    try:
        data = request.json
        fcid = data.get("fcid")
        if not fcid:
            return jsonify({"error": "FCID ist erforderlich"}), 400

        filaments = load_filaments()
        new_filaments = [f for f in filaments if f.get("fcid") != fcid]

        if len(new_filaments) == len(filaments):
            return jsonify({"error": "Filament mit dieser FCID nicht gefunden"}), 404

        save_filaments(new_filaments)
        return jsonify({"success": True, "message": "Filament erfolgreich gelöscht"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/debug_mqtt_stream")
def debug_mqtt_stream():
    try:
        printers_path = os.path.join(app.static_folder, "printers.json")
        if not os.path.exists(printers_path):
            return jsonify({"error": "Kein printers.json gefunden"}), 400

        with open(printers_path, "r") as f:
            printers = json.load(f)
        printer = next((p for p in printers if p.get("active")), None)
        if not printer:
            return jsonify({"error": "Kein aktiver Drucker"}), 400

        serial = printer.get("serial")
        access_code = printer.get("access_code")
        broker_ip = printer.get("ip")
        broker_port = 8883
        username = "bblp"
        password = access_code
        drucker_name = printer.get("name")
        if not serial or not access_code or not broker_ip or not drucker_name:
            return jsonify({"error": "Fehlende Druckerdaten"}), 400

        topic = f"device/{serial}/report"
        log_path = "/tmp/mqtt_debug.log"  # oder z.B. os.path.join(app.static_folder, "mqtt_debug.log")

        def on_connect(client, userdata, flags, rc, properties=None):
            with open(log_path, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] MQTT connected {rc}\n")
            client.subscribe(topic)

        def on_message(client, userdata, msg):
            with open(log_path, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] MQTT [{msg.topic}] {msg.payload.decode(errors='replace')}\n")

        client = mqtt.Client()
        client.username_pw_set(username, password)
        client.on_connect = on_connect
        client.on_message = on_message

        cert_path = os.path.join(app.static_folder, "printers", drucker_name, "blcert.pem")
        client.tls_set(ca_certs=cert_path)
        client.tls_insecure_set(True)

        client.connect(broker_ip, broker_port, 10)
        client.loop_start()

        # 20 Sekunden lang alle MQTT-Nachrichten mitloggen:
        time.sleep(20)
        client.loop_stop()

        return jsonify({"ok": True, "info": "MQTT-Stream für 20 Sekunden geloggt – siehe /tmp/mqtt_debug.log"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/set_filament_mqtt", methods=["POST"])
def set_filament_mqtt():
    try:
        data = request.json
        slot = int(data.get("slot", -1))
        fcid = data.get("fcid")

        if slot not in [1, 2, 3, 4]:
            return jsonify({"error": "Slot muss 1-4 sein"}), 400
        if not fcid:
            return jsonify({"error": "FCID erforderlich"}), 400

        # Filaments laden
        filaments_path = os.path.join(app.static_folder, "filacore_spools.json")
        if not os.path.exists(filaments_path):
            return jsonify({"error": "filacore_spools.json nicht gefunden"}), 500
        with open(filaments_path, "r", encoding="utf-8") as f:
            filaments = json.load(f)

        filament = next((f for f in filaments if f.get("fcid") == fcid), None)
        if not filament:
            return jsonify({"error": "Filament nicht gefunden"}), 404

        material = filament.get("material")
        druckprofil = filament.get("druckprofil")
        temp_min = int(filament.get("tempMin", 220))
        temp_max = int(filament.get("tempMax", 240))
        farbe = filament.get("farbe", "000000FF")
        ams_id = 0

        # Druckerliste laden
        printers_path = os.path.join(app.static_folder, "printers.json")
        if not os.path.exists(printers_path):
            return jsonify({"error": "printers.json nicht gefunden"}), 500

        with open(printers_path, "r") as f:
            printers = json.load(f)

        printer = next((p for p in printers if p.get("active")), None)
        if not printer:
            return jsonify({"error": "Kein aktiver Drucker"}), 400

        serial = printer.get("serial")
        access_code = printer.get("access_code")
        broker_ip = printer.get("ip")
        drucker_name = printer.get("name")
        broker_port = 8883
        username = "bblp"
        password = access_code

        if not all([serial, access_code, broker_ip, drucker_name]):
            return jsonify({"error": "Fehlende Druckerdaten"}), 500

        cert_path = os.path.join(app.static_folder, "printers", drucker_name, "blcert.pem")
        if not os.path.exists(cert_path):
            return jsonify({"error": f"Zertifikat {cert_path} nicht gefunden"}), 500

        response_received = False
        response_message = None

        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                client.subscribe(f"device/{serial}/report")
                payload = {
                    "print": {
                        "command": "ams_filament_setting",
                        "ams_id": ams_id,
                        "tray_id": slot - 1,
                        "tray_info_idx": druckprofil,
                        "tray_color": farbe,
                        "tray_type": material,
                        "nozzle_temp_min": temp_min,
                        "nozzle_temp_max": temp_max
                    }
                }
                client.publish(f"device/{serial}/request", json.dumps(payload))
            else:
                print(f"MQTT-Verbindung fehlgeschlagen mit Code {rc}")

        def on_message(client, userdata, msg):
            nonlocal response_received, response_message
            try:
                payload = json.loads(msg.payload.decode())
                if payload.get("print", {}).get("command") == "ams_filament_setting":
                    response_message = payload
                    response_received = True
                    client.disconnect()
            except Exception as e:
                print("Fehler beim Verarbeiten der MQTT-Nachricht:", e)

        client = mqtt.Client()
        client.username_pw_set(username, password)
        client.tls_set(ca_certs=cert_path)
        client.tls_insecure_set(True)
        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(broker_ip, broker_port, 10)
        client.loop_start()

        timeout = time.time() + 10
        while not response_received and time.time() < timeout:
            time.sleep(0.1)

        client.loop_stop()

        if response_received:
            return jsonify({"ok": True, "response": response_message})
        else:
            return jsonify({"error": "Keine Antwort vom Drucker"}), 504

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/generate_fcid")
def generate_fcid():
    try:
        # Beispiel: zufällige ID im Format 8 hex Zeichen, z.B. "1a2b3c4d"
        fcid = ''.join(random.choices('0123456789abcdef', k=8))
        return jsonify({"fcid": fcid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)