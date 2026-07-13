# Deploy ChickHub ke VPS — Panduan Step by Step

## Persiapan

VPS: **103.253.212.182** (AlmaLinux 8.9)
Akses: SSH via root

---

## Step 1 — Install Docker + Docker Compose di VPS

SSH ke VPS dulu:

```bash
ssh root@103.253.212.182
```

Jalankan ini satu per satu:

```bash
# Install Docker
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install -y docker-ce docker-ce-cli containerd.io

# Start & enable Docker
systemctl start docker
systemctl enable docker

# Install Docker Compose plugin
dnf install -y docker-compose-plugin

# Cek versi
docker --version
docker compose version
```

---

## Step 2 — Kirim project ke VPS

Dari laptop (PowerShell/CMD), ganti `<isi>` dengan path folder project:

```powershell
scp -r D:\Artificial\ and\ Learning\UAS root@103.253.212.182:/root/chickhub
```

Atau kalau pakai Git:

```bash
# Di VPS
git clone <repo-url> /root/chickhub
```

---

## Step 3 — Build & Jalankan

```bash
cd /root/chickhub

# Build image server
docker compose build

# Jalankan semua service
docker compose up -d

# Cek status
docker compose ps
```

---

## Step 4 — Buka Firewall VPS

```bash
firewall-cmd --add-port=1883/tcp --permanent   # MQTT
firewall-cmd --add-port=3000/tcp --permanent   # Web
firewall-cmd --reload
```

---

## Step 5 — Update ESP32

Di firmware `inkubator.ino`, ubah MQTT host dari IP lokal ke IP VPS:

```cpp
// Sebelum
const char MQTT_HOST_DEFAULT[] = "192.168.254.102";

// Sesudah
const char MQTT_HOST_DEFAULT[] = "103.253.212.182";
```

Upload ulang firmware ke ESP32.

---

## Step 6 — Tes

- Buka browser: `http://103.253.212.182:3000`
- Cek log: `docker compose logs -f`

---

## Perintah Berguna

```bash
# Lihat log realtime
docker compose logs -f

# Restart semua service
docker compose restart

# Stop semua service
docker compose down

# Update setelah ada perubahan kode
docker compose build server
docker compose up -d

# Hapus semua container + volume (data hilang!)
docker compose down -v
```

---

## Struktur File

```
UAS/
├── Dockerfile                  ← Build server Node.js
├── docker-compose.yml          ← Orchestrate Mosquitto + Server
├── .dockerignore               ← File yang di-skip saat build
├── mosquitto.chickhub.conf     ← Config MQTT khusus ChickHub (port 1883)
├── server/                     ← Kode backend Node.js
└── inkubator/                  ← Firmware ESP32
```
