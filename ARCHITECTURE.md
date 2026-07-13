# Architecture — ChickHub

## Struktur Folder

```
UAS/
├── PRD.md                          # ← ini
├── ARCHITECTURE.md                 # ← ini
├── TemplateIndex/                  # Hasil export Google Stitch
│   ├── Home.html
│   ├── History.html
│   ├── Settings.html
│   └── Logo.png
├── inkubator/                      # ESP32 Arduino code (existing)
│   ├── inkubator.ino               # Main + MQTT + PID
│   ├── inkubator.h                 # Shared header
│   ├── dt_model.h                  # Decision Tree model
│   ├── web.ino                     # Web server (PROGMEM) — legacy
│   └── ...
├── web/                            # Web files (existing, nanti di-refactor)
│   ├── index.html
│   ├── web_server.h
│   └── web_server.cpp
├── server/                         # 🆕 Backend server
│   ├── package.json
│   ├── index.js                    # Entry point
│   ├── mqtt.js                     # MQTT client wrapper
│   ├── db.js                       # SQLite init + queries
│   ├── ws.js                       # WebSocket broadcast
│   ├── routes.js                   # Express routes
│   └── public/                     # Static files (dari Stitch)
│       ├── index.html              # Home.html → index.html
│       ├── history.html
│       ├── settings.html
│       ├── css/
│       └── js/
│           ├── app.js              # Main app logic
│           ├── mqtt-client.js      # WebSocket client (ke server)
│           ├── chart.js            # Chart rendering
│           └── utils.js            # Helpers
├── dt_control.cpp
├── dt_control.h
├── inkubator_train.py
├── ...
```

---

## Server Flow Detail

```
  ESP32                          SERVER (Node.js)                    BROWSER
   │                                  │                                │
   │──MQTT publish ──────────────▶  mqtt.js                           │
   │   inkubator/status              │                                │
   │                                 │──store──▶ SQLite                │
   │                                 │                                │
   │                                 │──broadcast──▶ ws.js            │
   │                                 │                   │            │
   │                                 │                   │──WS send──▶│
   │                                 │                               🔄 Update UI
   │                                 │                                │
   │◀──MQTT subscribe ──────────────┤                                │
   │   inkubator/set/param          │◀────── REST/WS ────────────────│
   │   inkubator/set/mode           │    POST /api/set                │
   │                                │    POST /api/mode               │
   │                                │    GET  /api/history            │
```

---

## Server API

### REST Endpoints

| Method | Path | Desc |
|---|---|---|
| GET | `/api/status` | Status terkini (latest dari MQTT) |
| GET | `/api/history` | History (query: `?from=&to=&limit=`) |
| GET | `/api/history/export` | Download CSV |
| POST | `/api/set` | Set param `{key, value}` |
| POST | `/api/mode` | Set mode `{mode: "AUTO"|"MANUAL"}` |
| GET | `/api/settings` | Get saved settings |
| POST | `/api/settings` | Save settings |

### WebSocket Events

| Event | Arah | Data |
|---|---|---|
| `status` | Server → Client | JSON status (sama kayak MQTT) |
| `history` | Server → Client | Array history records |
| `set:param` | Client → Server | `{key, value}` |
| `set:mode` | Client → Server | `{mode}` |

---

## Integrasi Stitch ke Server

1. Copy file dari `TemplateIndex/` ke `server/public/`
   - `Home.html` → `server/public/index.html`
   - `History.html` → `server/public/history.html`
   - `Settings.html` → `server/public/settings.html`

2. **Inline data** di Stitch diganti dengan JS yang ambil data dari WebSocket
   - Angka statis `37.8°C` → `document.getElementById('suhu').textContent = data.suhu + '°C'`
   - Mode statis → ambil dari WebSocket message

3. **Interaksi** (tombol mode, slider) → kirim WebSocket/MQTT

---

## Cara Jalanin Server

```bash
# 1. Install dependencies
cd server
npm install

# 2. Pastikan Mosquitto jalan (biasanya udah)
#    Cek: netstat -an | findstr :1883

# 3. Start server
node index.js

# 4. Buka browser
#    http://localhost:3000
```

### Dependencies (server/package.json)

```json
{
  "dependencies": {
    "express": "^4",
    "mqtt": "^5",
    "ws": "^8",
    "better-sqlite3": "^11"
  }
}
```

---

## Catatan Implementasi

1. **ESP32 sudah siap MQTT** — gak perlu perubahan berarti, cuma setup WiFi & MQTT host di `inkubator.ino`
2. **Stitch design dibaca sebagai template** — gak perlu Tailwind build step karena pake CDN
3. **History chart** — bisa pake canvas manual atau Chart.js dari CDN biar ringan
4. **Mode toggle** di web sync dengan ESP32 — via MQTT dua arah
5. **ESP32 web.ino (PROGMEM)** tetap bisa dipake sebagai fallback kalo server mati
