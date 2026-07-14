/**
 * ChickHub Server — Express + MQTT + WebSocket + SQLite
 *
 * Arsitektur:
 *   ESP32 ──MQTT──▶ Mosquitto ──MQTT──▶ Server ──WS──▶ Browser
 *
 * Cara jalan:
 *   cd server && npm install && node index.js
 *   Buka http://localhost:3000
 */

const express = require('express');
const http = require('http');
const { WebSocketServer } = require('ws');
const mqtt = require('mqtt');
const path = require('path');
const crypto = require('crypto');
const Database = require('better-sqlite3');

// ===== Config =====
const HTTP_PORT = 3000;
const MQTT_HOST = process.env.MQTT_HOST || '10.213.71.48';
const MQTT_PORT = process.env.MQTT_PORT || 1883;
const MQTT_URL = `mqtt://${MQTT_HOST}:${MQTT_PORT}`;

const TOPIC_STATUS = 'inkubator/status';
const TOPIC_PARAM = 'inkubator/set/param';
const TOPIC_MODE = 'inkubator/set/mode';

// ===== State =====
let latestStatus = null;

// ===== Database =====
const db = new Database(path.join(__dirname, 'data', 'chickhub.db'));
db.pragma('journal_mode = WAL');
db.exec(`
  CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    suhu REAL,
    humi REAL,
    heater INTEGER,
    kipas INTEGER,
    mode TEXT,
    aktivitas TEXT DEFAULT 'Monitoring',
    detail TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_history_ts ON history(timestamp);
`);
// Tambah kolom kalo belum ada (migrasi)
try { db.exec('ALTER TABLE history ADD COLUMN aktivitas TEXT DEFAULT \'Monitoring\''); } catch {}
try { db.exec('ALTER TABLE history ADD COLUMN detail TEXT'); } catch {}

// Hapus data lama pake aktivitas
db.exec(`DELETE FROM history WHERE timestamp < datetime('now', '-30 days')`);

const insertStmt = db.prepare(`INSERT INTO history (suhu, humi, heater, kipas, mode, aktivitas, detail) VALUES (?, ?, ?, ?, ?, ?, ?)`);
let lastSensorLog = 0;

// ===== Users =====
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
  );
`);

// Seed default admin
const hash = crypto.createHash('sha256').update('admin').digest('hex');
const existing = db.prepare('SELECT id FROM users WHERE username = ?').get('admin');
if (!existing) {
  db.prepare('INSERT INTO users (username, password) VALUES (?, ?)').run('admin', hash);
  console.log('Default user seeded: admin / admin');
}

// ===== Express =====
const app = express();
const server = http.createServer(app);

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// API endpoints
app.post('/api/login', (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) return res.status(400).json({ error: 'Username dan password diperlukan' });
    
    const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
    if (!user) return res.status(401).json({ error: 'Username atau password salah' });
    
    const hash = crypto.createHash('sha256').update(password).digest('hex');
    if (user.password !== hash) return res.status(401).json({ error: 'Username atau password salah' });
    
    db.prepare("INSERT INTO history (aktivitas, detail) VALUES ('Login', ?)").run('User ' + username + ' login');
    broadcast({ aktivitas: 'Login', detail: 'User ' + username + ' login', suhu: null });
    res.json({ ok: true, username: user.username });
});

app.post('/api/register', (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) return res.status(400).json({ error: 'Username dan password diperlukan' });
    if (username.length < 3) return res.status(400).json({ error: 'Username minimal 3 karakter' });
    if (password.length < 4) return res.status(400).json({ error: 'Password minimal 4 karakter' });

    const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
    if (existing) return res.status(409).json({ error: 'Username sudah terdaftar' });

    const hash = crypto.createHash('sha256').update(password).digest('hex');
    db.prepare('INSERT INTO users (username, password) VALUES (?, ?)').run(username, hash);
    db.prepare("INSERT INTO history (aktivitas, detail) VALUES ('Register', ?)").run('User ' + username + ' registered');
    
    res.json({ ok: true, username });
});

app.post('/api/profile/update', (req, res) => {
    const { username, currentPassword, newPassword, displayName } = req.body;
    if (!username) return res.status(400).json({ error: 'Username diperlukan' });

    const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
    if (!user) return res.status(404).json({ error: 'User tidak ditemukan' });

    // Verify current password if changing password
    if (newPassword) {
        if (!currentPassword) return res.status(400).json({ error: 'Password saat ini diperlukan' });
        const hash = crypto.createHash('sha256').update(currentPassword).digest('hex');
        if (user.password !== hash) return res.status(401).json({ error: 'Password saat ini salah' });
        if (newPassword.length < 4) return res.status(400).json({ error: 'Password baru minimal 4 karakter' });
        
        const newHash = crypto.createHash('sha256').update(newPassword).digest('hex');
        db.prepare('UPDATE users SET password = ? WHERE username = ?').run(newHash, username);
    }

    // Update display name in a separate profile table or just return ok
    // For now, store displayName in localStorage on client side
    
    db.prepare("INSERT INTO history (aktivitas, detail) VALUES ('Profile', ?)").run('User ' + username + ' updated profile');
    res.json({ ok: true, username, displayName: displayName || username });
});

app.get('/api/status', (req, res) => {
    res.json(latestStatus || { mode: '—', suhu: null, humi: null, heater: null, kipas: null });
});

app.get('/api/history', (req, res) => {
    const { from, to, limit = 100 } = req.query;
    let sql = 'SELECT * FROM history';
    const params = [];
    const clauses = [];

    if (from) { clauses.push('timestamp >= ?'); params.push(from); }
    if (to) { clauses.push('timestamp <= ?'); params.push(to); }

    if (clauses.length) sql += ' WHERE ' + clauses.join(' AND ');
    sql += ' ORDER BY id DESC LIMIT ?';
    params.push(parseInt(limit) || 100);

    res.json(db.prepare(sql).all(...params));
});

app.post('/api/history/clear', (req, res) => {
    db.exec('DELETE FROM history');
    db.exec("INSERT INTO history (aktivitas, detail) VALUES ('System', 'Riwayat dibersihkan')");
    res.json({ ok: true });
});

app.get('/api/history/export', (req, res) => {
    const rows = db.prepare('SELECT * FROM history ORDER BY id DESC').all();
    let csv = 'ID,Waktu,Suhu,Humi,Heater,Kipas,Mode,Aktivitas,Detail\n';
    rows.forEach(r => {
        csv += `${r.id},"${r.timestamp}",${r.suhu ?? ''},${r.humi ?? ''},${r.heater ?? ''},${r.kipas ?? ''},${r.mode ?? ''},"${r.aktivitas ?? ''}","${(r.detail||'').replace(/"/g,'""')}"\n`;
    });
    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename=chickhub_export_${new Date().toISOString().slice(0,10)}.csv`);
    res.send(csv);
});

app.post('/api/set', (req, res) => {
    const { key, value } = req.body;
    if (!key || value === undefined) return res.status(400).json({ error: 'key and value required' });

    // Publish ke MQTT
    const payload = `${key}=${value}`;
    mqttClient.publish(TOPIC_PARAM, payload);
    res.json({ ok: true });
});

app.post('/api/mode', (req, res) => {
    const { mode } = req.body;
    if (!mode || !['AUTO', 'MANUAL'].includes(mode.toUpperCase())) {
        return res.status(400).json({ error: 'mode must be AUTO or MANUAL' });
    }
    mqttClient.publish(TOPIC_MODE, mode.toUpperCase());
    res.json({ ok: true });
});

// ===== WebSocket =====
const wss = new WebSocketServer({ server });
const clients = new Set();

wss.on('connection', (ws) => {
    clients.add(ws);

    // Kirim status terbaru
    if (latestStatus) {
        ws.send(JSON.stringify({ type: 'status', data: latestStatus }));
    }

    ws.on('message', (raw) => {
        try {
            const msg = JSON.parse(raw.toString());
            const { action, payload } = msg;

            if (action === 'set_param' && payload) {
                const { key, value } = payload;
                mqttClient.publish(TOPIC_PARAM, `${key}=${value}`);
            } else if (action === 'set_mode' && payload) {
                const { mode } = payload;
                mqttClient.publish(TOPIC_MODE, mode.toUpperCase());
            }
        } catch { /* ignore */ }
    });

    ws.on('close', () => {
        clients.delete(ws);
        db.prepare("INSERT INTO history (aktivitas, detail) VALUES ('Logout', 'User disconnected')").run();
    });
});

function broadcast(data) {
    const msg = JSON.stringify({ type: 'status', data });
    clients.forEach(ws => {
        if (ws.readyState === 1) ws.send(msg);
    });
}

// ===== MQTT Client =====
const mqttClient = mqtt.connect(MQTT_URL);

mqttClient.on('connect', () => {
    console.log('MQTT connected to', MQTT_URL);
    mqttClient.subscribe(TOPIC_STATUS);
});

mqttClient.on('message', (topic, message) => {
    if (topic === TOPIC_STATUS) {
        try {
            const data = JSON.parse(message.toString());
            latestStatus = data;

            // Broadcast ke semua WebSocket client
            broadcast(data);

            // Simpan ke database tiap 1 menit (untuk CSV)
            const now = Date.now();
            if (now - lastSensorLog >= 60000) {
                lastSensorLog = now;
                insertStmt.run(
                    data.suhu ?? null,
                    data.humi ?? null,
                    data.heater ?? null,
                    data.kipas ?? null,
                    data.mode ?? null,
                    'Monitoring',
                    'Suhu: ' + (data.suhu ?? '--') + '°C / Hum: ' + (data.humi ?? '--') + '%'
                );
            }
        } catch (err) {
            console.error('Parse error:', err.message);
        }
    }
});

mqttClient.on('error', (err) => {
    console.error('MQTT error:', err.message);
});

mqttClient.on('close', () => {
    console.log('MQTT disconnected, reconnecting...');
});

// ===== Start =====
server.listen(HTTP_PORT, () => {
    console.log(`ChickHub Server running at http://localhost:${HTTP_PORT}`);
    console.log(`MQTT broker: ${MQTT_URL}`);
    console.log(`WebSocket: ws://localhost:${HTTP_PORT}`);
});
