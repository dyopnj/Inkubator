# PRD — ChickHub: Smart Egg Incubator (IKI-3B)

**Versi:** 2.1
**Tanggal:** 2026-06-22
**Project:** `UAS/`

---

## 1. Ringkasan

ChickHub (IKI-3B) adalah sistem monitoring dan kontrol inkubator telur berbasis ESP32 dengan akses lokal (tombol fisik + OLED opsional) maupun web. System menggunakan MQTT backbone, Node.js server middleware, dan SQLite untuk history. ESP32 menggunakan **ML model + PID** sebagai kontrol otomatis — mendukung 12 model (LR, Ridge, Lasso, Huber, GLM, SVR, RF, ET, GB, Ada, DT, MLP) yang bisa dipilih via hardcode.

---

## 2. Tujuan

- Kontrol suhu & kelembaban inkubator otomatis (ML model + PID, 12 opsi model)
- Monitor & kontrol real-time dari web (Tailwind CSS)
- History logging + export CSV
- Mode AUTO (ML+PID) dan MANUAL (manual slider)
- Kontrol motor (rak telur) ON/OFF dari OLED & web
- Feedback buzzer untuk interaksi tombol

---

## 3. Arsitektur

```
┌──────────────────┐   MQTT    ┌───────────┐   MQTT    ┌──────────────┐
│  ESP32 (IKI-3B)  │◄────────►│ Mosquitto │◄────────►│  Node.js     │
│                  │  1883     │  Broker   │  1883     │  Server      │
│ - DHT22 (pin 17) │           └───────────┘           │  (Express)   │
│ - AC Dimmer      │                                    │  + SQLite    │
│   (ZC=18, TRG=5) │                                    └──────┬───────┘
│ - Fan PWM (26)   │                                           │HTTP+WS
│ - Motor (25)     │                                           ▼
│ - Buzzer (27)    │                                    ┌──────────────┐
│ - OLED 128x64    │                                    │   Browser    │
│ - Tombol (32,19) │                                    │  (Tailwind)  │
└──────────────────┘                                    └──────────────┘
```

### Komponen

| Komponen | Tech | Fungsi |
|---|---|---|
| **ESP32** | Arduino + PubSubClient | Baca DHT22, ML+PID, AC Dimmer heater, PWM fan, relay motor, OLED, buzzer, tombol |
| **Server** | Node.js + Express + mqtt.js + ws + better-sqlite3 | Middleware, history storage, WebSocket broadcast, auth |
| **Web UI** | HTML + Tailwind CSS (Google Stitch) | Dashboard realtime, login, settings, history |

---

## 4. Pin Mapping ESP32

| Fungsi | Pin | Aktuator/Sensor |
|---|---|---|
| DHT22 | 17 | Suhu & kelembaban |
| TRIAC trigger | 5 | AC Dimmer (heater) |
| ZC detector | 18 | Zero-crossing |
| Fan PWM | 26 | DC fan |
| Relay motor | 25 | Motor rak telur ON/OFF |
| Buzzer | 27 | Feedback suara (active HIGH) |
| Button UP | 32 | Tombol navigasi (active LOW) |
| Button DOWN | 19 | Tombol navigasi (active LOW) |
| I2C SDA | 21 | OLED |
| I2C SCL | 22 | OLED |

---

## 5. Topik MQTT

| Topik | Arah | Format | Deskripsi |
|---|---|---|---|
| `inkubator/status` | ESP32 → Server | JSON | Status realtime tiap 2 detik |
| `inkubator/set/param` | Server → ESP32 | `key=value` | Set parameter PID / manual / motor |
| `inkubator/set/mode` | Server → ESP32 | `AUTO` / `MANUAL` | Ganti mode kontrol |

### Format JSON `inkubator/status`

```json
{
  "mode": "AUTO",
  "suhu": 37.8,
  "humi": 58.0,
  "heater": 65,
  "kipas": 30,
  "motor": "OFF",
  "pid_h": { "kp": 8.0, "ki": 0.5, "kd": 2.0, "sp": 37.5 },
  "pid_f": { "kp": 6.0, "ki": 0.3, "kd": 1.5, "sp": 60.0 },
  "manual": { "heater": 0, "fan": 40 }
}
```

### Parameter `inkubator/set/param`

| Key | Value | Efek |
|---|---|---|
| `h_kp`, `h_ki`, `h_kd`, `h_sp` | float | PID Heater (default: Kp=8, Ki=0.5, Kd=2, SP=37.5) |
| `f_kp`, `f_ki`, `f_kd`, `f_sp` | float | PID Fan (default: Kp=6, Ki=0.3, Kd=1.5, SP=60%) |
| `m_heater`, `m_fan` | 0-100 | Manual override |
| `motor` | `ON` / `OFF` | Motor relay |

---

## 6. ESP32 — Firmware (inkubator.ino)

### 6.1 Kontrol Otomatis
- **ML Model** (`*_model.h`): output base heater/fan % dari suhu & humi
  - 12 model tersedia: `lr`, `ridge`, `lasso`, `huber`, `glm`, `svr`, `rf`, `et`, `gb`, `ada`, `dt`, `mlp`
  - **Cara ganti model**: cukup 2 perubahan di `inkubator.ino`:
    1. Ganti `#include "dt_model.h"` → `#include "{nama}_model.h"`
    2. Ganti `dt_predict(...)` → `{nama}_predict(...)`
  - Contoh ganti dari DT ke RF:
    ```cpp
    // BEFORE (DT)
    #include "dt_model.h"
    dt_predict(st, sh, &hp, &fp);

    // AFTER (RF)
    #include "rf_model.h"
    rf_predict(st, sh, &hp, &fp);
    ```
  - Semua model pakai format fungsi identik: `{pfx}_predict(suhu, humi, &heater, &fan)`
  - Wrapper opsional: `{Pfx}Output {pfx}Control(suhu, humi)` return struct
  - Tabel mapping:
    | Pilihan | Include | Fungsi Predict | Fungsi Control |
    |---------|---------|----------------|----------------|
    | `lr` | `lr_model.h` | `lr_predict()` | `LROutput lrControl()` |
    | `ridge` | `ridge_model.h` | `ridge_predict()` | `RidgeOutput ridgeControl()` |
    | `lasso` | `lasso_model.h` | `lasso_predict()` | `LassoOutput lassoControl()` |
    | `huber` | `huber_model.h` | `huber_predict()` | `HuberOutput huberControl()` |
    | `glm` | `glm_model.h` | `glm_predict()` | `GLMOutput glmControl()` |
    | `svr` | `svr_model.h` | `svr_predict()` | `SVROutput svrControl()` |
    | `rf` | `rf_model.h` | `rf_predict()` | `RFOutput rfControl()` |
    | `et` | `et_model.h` | `et_predict()` | `ETOutput etControl()` |
    | `gb` | `gb_model.h` | `gb_predict()` | `GBOutput gbControl()` |
    | `ada` | `ada_model.h` | `ada_predict()` | `AdaOutput adaControl()` |
    | `dt` | `dt_model.h` | `dt_predict()` | `DTOutput dtControl()` |
    | `mlp` | `nn_model.h` | `nn_predict()` | `NNOutput nnControl()` |
- **PID** (`_pid()`): koreksi halus dari error setpoint. Bekerja di atas output ML model — ML kasih base, PID halusin error. Tidak perlu diubah saat ganti model.
- Safety cutoff: suhu > 42°C → heater=0, fan=100

### 6.2 Output Hardware
- **Heater**: AC Dimmer via zero-crossing ISR + `esp_timer`. Trigger TRIAC dengan delay `30*(255-brightness)+400` µs
- **Fan**: DC PWM via `analogWrite()` dengan kick start 250ms di duty 255, lalu map 0-100% → 70-255
- **Motor**: Relay ON/OFF via `digitalWrite()`

### 6.3 OLED UI (128x64 I2C)
- Intro screen "INKUBATOR IKI-3B" (2 detik)
- Home: TEMP, HUMI, MODE (AUTO/MAN), HEAT %, FAN %, MOTOR (ON/OFF), safety status, EGG type
- EDIT HEATER / EDIT FAN (manual mode): adjust nilai dengan tombol
- Blink kursor pada card aktif
- OLED opsional — kode tetap jalan walau OLED tidak terpasang

### 6.4 Tombol
- **UP (32)**: short=move down/+, long=tidak ada efek
- **DOWN (19)**: short=select/toggle, long=back dari edit mode
- Debounce 25ms, long press threshold 1000ms

### 6.5 Buzzer
- 1x beep (80ms) tiap short press
- 2x beep saat ganti mode (AUTO↔MANUAL)
- Active HIGH

### 6.6 WiFi
- **WiFiManager**: captive portal pertama kali dengan custom field MQTT Server IP
- SSID AP: `Inkubator-IKI3B`
- Credentials tersimpan di NVRAM

### 6.7 Safety
- Suhu > 42°C → heater=0, fan=100
- DHT22 read error → guard dengan valid flag (fallback suhu=37.5, humi=60)

---

## 7. Server (server/index.js)

### 7.1 Tech
- Express (port 3000)
- MQTT client (mqtt.js) connect ke Mosquitto
- WebSocket (ws) untuk real-time broadcast ke browser
- SQLite (better-sqlite3) untuk history

### 7.2 API Endpoints

| Endpoint | Method | Deskripsi |
|---|---|---|
| `/api/login` | POST | Login user |
| `/api/register` | POST | Register user baru |
| `/api/profile/update` | POST | Update password |
| `/api/status` | GET | Latest status JSON |
| `/api/history` | GET | History data (query: from, to, limit) |
| `/api/history/export` | GET | Export CSV history |
| `/api/set` | POST | Publish param `{key, value}` ke MQTT |
| `/api/mode` | POST | Publish mode `{mode: AUTO/MANUAL}` ke MQTT |

### 7.3 WebSocket
- Broadcast `{type: "status", data: latestStatus}` ke semua client
- Terima action `set_param` dan `set_mode` dari client

### 7.4 Database
- Tabel `history`: id, timestamp, suhu, humi, heater, kipas, mode
- Auto-prune data > 30 hari
- Default user: admin/admin (seed otomatis)

---

## 8. Halaman Web (Tailwind CSS + Google Stitch)

### 8.1 Login (`/login.html`)
- Username & password
- Link register
- Design: Stitch dengan warna emas (#795900)

### 8.2 Home / Dashboard (`/index.html`)
- Sidebar navigasi (Home, History, Settings, Logout)
- Top bar: hari inkubasi, jam realtime, koneksi status, mode toggle
- Notification bar: status sensor
- KPI cards:
  - Suhu (°C) — setpoint 37.5°C
  - Kelembaban (% RH) — setpoint 60%
  - Heater Output (%) — mode PID Auto
  - Kipas (ON/OFF + kecepatan %)
  - Rak Telur (motor ON/OFF + timer)
- Grafik suhu & kelembaban

### 8.3 History (`/history.html`)
- Tabel data historis
- Filter date range
- Export CSV
- Chart suhu & kelembaban

### 8.4 Settings (`/settings.html`)
- PID default parameters
- MQTT broker info
- User management

---

## 9. Fitur & Status

| Fitur | Prioritas | Status |
|---|---|---|
| Monitoring realtime suhu & humi | P0 | ✅ |
| Kontrol mode AUTO/MANUAL | P0 | ✅ |
| DHT22 sensor (suhu + humi) | P0 | ✅ |
| ML Model + PID kontrol (12 model) | P0 | ✅ |
| AC Dimmer (heater) via ZC + TRIAC | P0 | ✅ |
| Fan PWM + kick start | P0 | ✅ |
| Motor relay ON/OFF | P0 | ✅ |
| Buzzer feedback | P0 | ✅ |
| OLED 128x64 UI | P0 | ✅ |
| Tombol navigasi (UP/DOWN) | P0 | ✅ |
| WiFiManager (captive portal) | P0 | ✅ |
| MQTT publish/subscribe | P0 | ✅ |
| Dashboard web real-time | P0 | ✅ |
| User login/register | P0 | ✅ |
| History logging + chart | P1 | ✅ |
| Manual override heater/fan | P0 | ✅ |
| Export CSV | P1 | ✅ |
| Safety cutoff >42°C | P0 | ✅ |
| Settings page (PID, broker) | P1 | ✅ |
| Motor kontrol dari web | P1 | ✅ |
| Egg mode (display only) | P2 | ✅ |

---

## 10. Data Flow

```
ESP32 sensor read (DHT22 tiap 3s)
    │
    ├──→ ML predict(base) + PID(koreksi) → heater%, fan%
    ├──→ applyDimmer() + applyFanPWM() → hardware
    └──→ MQTT publish (inkubator/status) tiap 2s
              │
              ▼
         Mosquitto Broker (:1883)
              │
              ▼
         Node.js Server (mqtt.subscribe)
              │
              ├──→ Store ke SQLite (history)
              ├──→ Broadcast via WebSocket ke browser
              └──→ Response HTTP API (/api/status)
```

Untuk kontrol:
```
Browser → (HTTP POST /api/set) → Server → MQTT publish → ESP32 → aksi
Browser → (WebSocket) → Server → MQTT publish → ESP32 → aksi
ESP32 button → aksi langsung (tanpa MQTT)
OLED ← update dari state (sinkron via shared variables)
```

**Sinkronisasi**: semua state (PID params, mode, manual values, motor) di-share antara button handler dan MQTT callback dalam satu thread loop(). Tidak ada race condition.

---

## 11. Cara Setup & Jalankan

### 11.1 Training Model (Python)
```bash
python inkubator_train.py
# Output: *_model.h, *_control.h/.cpp, training_report.png, training_report.txt
```
Set `MODEL_TYPE` di `inkubator_train.py` untuk pilih model:
- `"dt"` (default, R²=0.9997), `"rf"`, `"mlp"`, `"lr"`, dll
- `"all"` → train semua 12 model + simpan comparison ke `model_comparison.txt`

### 11.2 ESP32 — Ganti Model (Hardcode)

Model dipilih dengan **hardcode** — ganti 2 baris di `inkubator.ino`:

```cpp
// Step 1: Ganti include
#include "dt_model.h"      // ← ganti jadi model pilihan
// Contoh: #include "rf_model.h"
// Contoh: #include "lr_model.h"
// Contoh: #include "nn_model.h"

// Step 2: Ganti fungsi predict
dt_predict(st, sh, &hp, &fp);   // ← ganti jadi model pilihan
// Contoh: rf_predict(st, sh, &hp, &fp);
// Contoh: lr_predict(st, sh, &hp, &fp);
// Contoh: nn_predict(st, sh, &hp, &fp);
```

Langkah lengkap:
1. Copy file `{pfx}_model.h` hasil training ke folder `inkubator/`
2. Buka `inkubator/inkubator.ino` di Arduino IDE
3. Ganti `#include` dan fungsi predict sesuai model di tabel 6.1
4. Install library via Library Manager:
   - DHT sensor library (Adafruit)
   - Adafruit GFX
   - Adafruit SSD1306
   - WiFiManager (tzapu)
   - PubSubClient (Knolleary)
5. Compile & upload ke ESP32
6. Portal WiFiManager `Inkubator-IKI3B` muncul
7. Konek ke portal, isi SSID/password WiFi + MQTT Server IP

### 11.3 Server
```bash
cd server
npm install
node index.js
# → http://localhost:3000
```

### 11.4 Mosquitto
Pastikan Mosquitto broker berjalan (default port 1883).
Di Windows: service `mosquitto` harus running.

---

## 12. Tech Stack

| Lapisan | Teknologi |
|---|---|
| ML Training | Python scikit-learn (pandas, numpy, matplotlib) |
| Mikrokontroler | ESP32, DHT22, OLED SSD1306, AC Dimmer, Arduino framework |
| Komunikasi | MQTT (Mosquitto broker :1883) |
| Backend | Node.js, Express, mqtt.js, ws, better-sqlite3 |
| Frontend | HTML, Tailwind CSS, Material Symbols, vanilla JS |
| Database | SQLite (file-based, auto-prune 30 hari) |
| Autentikasi | SHA256 hash, database users |

---

## 13. Non-Functional

- **Realtime**: Latency < 500ms dari sensor ke browser (MQTT + WebSocket)
- **Reliability**: Server auto-reconnect ke MQTT (retry 5 detik)
- **Reliability**: ESP32 MQTT auto-reconnect di loop
- **Storage**: History disimpan max 30 hari, auto-prune via SQL
- **Security**: Hanya di jaringan lokal (LAN)
- **Portability**: Server Windows/Linux, ESP32 universal
- **OLED opsional**: Firmware tetap jalan tanpa OLED
