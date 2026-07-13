/* ===== ChickHub - Main App Logic ===== */

// State global
let currentData = {
    mode: 'AUTO', suhu: null, humi: null,
    heater: null, kipas: null,
    pid_h: { kp: 8.0, ki: 0.5, kd: 2.0, sp: 37.5 },
    pid_f: { kp: 6.0, ki: 0.3, kd: 1.5, sp: 60.0 },
    manual: { heater: 0, fan: 0 }
};

// Chart state
const chartHistory = { suhu: [], humi: [] };
const CHART_MAX = 60;
let chartLabels = [];

// ===== Dashboard (Home) =====
function initDashboard() {
    // Init mode
    const modeToggle = document.getElementById('mode-toggle');
    if (modeToggle) {
        // Reset ke AUTO default
        const text = modeToggle.querySelector('.mode-text');
        const icon = modeToggle.querySelector('.mode-icon');
        if (text) text.innerText = 'AUTO';
        if (icon) icon.innerText = 'smart_toy';
        modeToggle.classList.remove('bg-secondary-container/30');
        modeToggle.classList.add('bg-surface-container');

        // Reset panels
        const heaterPid = document.getElementById('heater-pid-content');
        const heaterManual = document.getElementById('heater-manual-content');
        const kipasAuto = document.getElementById('kipas-auto-content');
        const kipasManual = document.getElementById('kipas-manual-content');
        const heaterLabel = document.querySelector('.heater-mode-label');
        const kipasLabel = document.querySelector('.kipas-mode-label');

        if (heaterPid) heaterPid.classList.remove('hidden');
        if (heaterManual) heaterManual.classList.add('hidden');
        if (kipasAuto) kipasAuto.classList.remove('hidden');
        if (kipasManual) kipasManual.classList.add('hidden');
        if (heaterLabel) heaterLabel.innerText = 'Mode: PID Auto';
        if (kipasLabel) kipasLabel.innerText = 'Kecepatan: --%';
    }

    // Set placeholders
    setDashboardData(null);
    initIncubation();
    updateClock();
    setInterval(updateClock, 1000);
}

// Update seluruh dashboard dari data MQTT
function setDashboardData(data) {
    if (!data) data = {};

    // Update state
    Object.assign(currentData, data);
    if (data.pid_h) Object.assign(currentData.pid_h, data.pid_h);
    if (data.pid_f) Object.assign(currentData.pid_f, data.pid_f);
    if (data.manual) Object.assign(currentData.manual, data.manual);

    // Elements (unit dari HTML, jangan duplikat)
    setText('suhuDisplay', fmtVal(data.suhu, 1));
    setText('humiDisplay', fmtVal(data.humi, 0));
    setText('heaterDisplay', fmtVal(data.heater, 0));
    setText('fanStatus', (data.kipas || 0) > 0 ? 'ON' : 'OFF');

    // Mode
    const mode = data.mode || 'AUTO';
    const modeEl = document.getElementById('mode');
    if (modeEl) {
        modeEl.textContent = mode;
        modeEl.className = 'badge ' + (mode === 'AUTO' ? 'badge-auto' : 'badge-manual');
    }

    // Koneksi
    const conn = document.getElementById('connStatus');
    if (conn) {
        conn.textContent = ChickMQTT.isConnected() ? 'terhubung' : 'offline';
        conn.className = 'conn ' + (ChickMQTT.isConnected() ? 'conn-ok' : 'conn-err');
    }

    // Status system
    setText('systemStatus', data.suhu ? statusText(data.suhu) : '—');

    // PID values
    if (data.pid_h) {
        setInputVal('h_kp', data.pid_h.kp);
        setInputVal('h_ki', data.pid_h.ki);
        setInputVal('h_kd', data.pid_h.kd);
        setInputVal('h_sp', data.pid_h.sp);
    }
    if (data.pid_f) {
        setInputVal('f_kp', data.pid_f.kp);
        setInputVal('f_ki', data.pid_f.ki);
        setInputVal('f_kd', data.pid_f.kd);
        setInputVal('f_sp', data.pid_f.sp);
    }
    if (data.manual) {
        setInputVal('m_heater', data.manual.heater);
        setInputVal('m_fan', data.manual.fan);
    }

    // Heater bar
    const bar = document.getElementById('heaterBar');
    if (bar) {
        const pct = data.heater || 0;
        bar.style.width = pct + '%';
    }

    // Fan status
    const fanStatus = document.getElementById('fanStatus');
    if (fanStatus) {
        const isOn = parseInt(data.kipas) > 0;
        fanStatus.textContent = isOn ? 'ON' : 'OFF';
        fanStatus.className = 'font-stat-value text-stat-value ' + (isOn ? 'text-green-700' : 'text-gray-400');
    }

    // Motor (rak telur)
    const motorEl = document.getElementById('motorDisplay');
    if (motorEl && data.motor !== undefined) {
        const isOn = data.motor === 'ON';
        motorEl.textContent = isOn ? 'ON' : 'OFF';
        motorEl.style.color = isOn ? '#0a3' : '#aaa';
    }
    const motorBtn = document.getElementById('motorToggle');
    if (motorBtn && data.motor !== undefined) {
        const isOn = data.motor === 'ON';
        motorBtn.dataset.state = isOn ? 'on' : 'off';
        motorBtn.textContent = isOn ? 'MATIKAN' : 'NYALAKAN';
        motorBtn.className = isOn ? 'ch-btn' : 'ch-btn ch-btn-primary';
        motorBtn.style.cssText = 'width:100%;height:36px;font-size:12px;text-transform:uppercase;font-weight:700;letter-spacing:.05em;' +
            (isOn ? 'background:#a33;color:#fff;border:none;' : '');
    }

    // Charts
    if (data.suhu != null || data.humi != null) {
        updateCharts(data);
    }
}

// ===== History Page =====
let historyData = [];
let historyPage = 1;
const HISTORY_PER_PAGE = 10;

function initHistory() {
    renderHistoryTable();
    setupHistoryFilters();
}

function renderHistoryTable(data) {
    const tbody = document.querySelector('#historyTable tbody');
    if (!tbody) return;

    const list = data || historyData;
    if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-lg py-md text-center text-on-surface-variant font-body-md">Belum ada data riwayat.</td></tr>`;
        return;
    }

    // Pagination
    const totalPages = Math.ceil(list.length / HISTORY_PER_PAGE) || 1;
    const start = (historyPage - 1) * HISTORY_PER_PAGE;
    const pageItems = list.slice(start, start + HISTORY_PER_PAGE);

    tbody.innerHTML = pageItems.map(r => {
        const stat = statusClass(r.suhu, r.humi);
        const stext = statusText(r.suhu);
        return `<tr class="table-row-hover transition-colors">
            <td class="px-lg py-md whitespace-nowrap font-data-display text-xs">${esc(r.timestamp || r.waktu || '—')}</td>
            <td class="px-lg py-md font-medium">${esc(r.aktivitas || 'Monitoring')}</td>
            <td class="px-lg py-md">
                <span class="text-on-surface-variant">${esc(r.detail || 'Suhu: ' + fmt(r.suhu, '°C', 1) + ' / Hum: ' + fmt(r.humi, '%', 0))}</span>
            </td>
            <td class="px-lg py-md">
                <span class="${stat}"><span class="w-1.5 h-1.5 rounded-full inline-block" style="background:${stext === 'WARNING' ? '#ba1a1a' : '#565e74'}"></span> ${stext}</span>
            </td>
            <td class="px-lg py-md text-right">
                <button class="text-on-surface-variant hover:text-primary"><span class="material-symbols-outlined">more_vert</span></button>
            </td>
        </tr>`;
    }).join('');

    // Update pagination info
    const info = document.querySelector('#historyPagination .page-info');
    if (info) {
        info.innerHTML = `Menampilkan <span class="font-bold">${start + 1} - ${Math.min(start + HISTORY_PER_PAGE, list.length)}</span> dari <span class="font-bold">${list.length.toLocaleString()}</span> riwayat`;
    }
}

function setupHistoryFilters() {
    const searchInput = document.querySelector('#historySearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            const q = e.target.value.toLowerCase();
            const filtered = historyData.filter(r =>
                (r.aktivitas || '').toLowerCase().includes(q) ||
                (r.detail || '').toLowerCase().includes(q)
            );
            renderHistoryTable(filtered);
        }, 300));
    }

    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-chip').forEach(b => {
                b.classList.remove('bg-primary', 'text-on-primary');
                b.classList.add('bg-surface-container-low', 'text-on-surface-variant');
            });
            btn.classList.remove('bg-surface-container-low', 'text-on-surface-variant');
            btn.classList.add('bg-primary', 'text-on-primary');
        });
    });
}

// ===== Settings Page =====
function initSettings() {
    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const themeLabel = document.getElementById('theme-label');
    if (themeToggle) {
        const saved = storeGet('theme', 'light');
        if (saved === 'dark') {
            themeToggle.checked = true;
            applyDarkMode(true, themeIcon, themeLabel);
        }

        themeToggle.addEventListener('change', () => {
            const isDark = themeToggle.checked;
            storeSet('theme', isDark ? 'dark' : 'light');
            applyDarkMode(isDark, themeIcon, themeLabel);
        });
    }

    // Language selection
    document.querySelectorAll('input[name="lang"]').forEach(r => {
        r.addEventListener('change', () => {
            if (r.checked) storeSet('lang', r.value);
        });
    });
    const savedLang = storeGet('lang', 'id');
    const langRadio = document.querySelector(`input[name="lang"][value="${savedLang}"]`);
    if (langRadio) langRadio.checked = true;

    // Device name edit
    const devName = document.getElementById('deviceName');
    const devEdit = document.getElementById('deviceNameEdit');
    if (devEdit && devName) {
        devEdit.addEventListener('click', () => {
            const newName = prompt('Nama perangkat:', devName.textContent);
            if (newName && newName.trim()) {
                devName.textContent = newName.trim();
                storeSet('deviceName', newName.trim());
            }
        });
    }
    const savedDev = storeGet('deviceName', 'ESP32-Incubator-01');
    if (devName) devName.textContent = savedDev;
}

function applyDarkMode(isDark, icon, label) {
    const html = document.documentElement;
    if (isDark) {
        html.classList.add('dark');
        if (icon) icon.innerText = 'dark_mode';
        if (label) label.innerText = 'Dark Mode';
        document.body.style.backgroundColor = '#131b2e';
        document.body.style.color = '#f7f9fb';
    } else {
        html.classList.remove('dark');
        if (icon) icon.innerText = 'light_mode';
        if (label) label.innerText = 'Light Mode';
        document.body.style.backgroundColor = '#f7f9fb';
        document.body.style.color = '#191c1e';
    }
}

// ===== Navigation =====
function navigateTo(page) {
    // Highlight active nav
    document.querySelectorAll('.nav-link').forEach(a => {
        a.classList.remove('active-nav-item', 'bg-primary-container', 'text-on-primary-container');
        a.classList.add('text-on-surface-variant');
    });

    const links = document.querySelectorAll('.nav-link');
    // Find the link matching the page
    links.forEach(a => {
        const href = a.getAttribute('href');
        if (href && href.includes(page)) {
            a.classList.remove('text-on-surface-variant');
            a.classList.add('bg-primary-container', 'text-on-primary-container', 'font-semibold', 'rounded-lg');
        }
    });
}

// ===== Helpers =====
function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setInputVal(id, val) {
    const el = document.getElementById(id);
    if (el) {
        if (el.type === 'number' || el.tagName === 'INPUT') {
            el.value = val !== null && val !== undefined ? val : '';
        } else {
            el.textContent = val !== null && val !== undefined ? val : '—';
        }
    }
}

// ===== Incubation Counter =====
function initIncubation() {
    const start = localStorage.getItem('chickhub_incub_start');
    const dayEl = document.getElementById('inkubasiDay');
    if (start && dayEl) {
        const diff = Math.floor((Date.now() - parseInt(start)) / 86400000) + 1;
        dayEl.textContent = Math.min(diff, 21);
    }
}

function toggleIncubation() {
    const start = localStorage.getItem('chickhub_incub_start');
    const dayEl = document.getElementById('inkubasiDay');
    if (!dayEl) return;

    if (start) {
        localStorage.removeItem('chickhub_incub_start');
        dayEl.textContent = '—';
    } else {
        localStorage.setItem('chickhub_incub_start', Date.now().toString());
        dayEl.textContent = '1';
    }
}

// ===== Clock =====
function updateClock() {
    const now = new Date();
    const clockEl = document.getElementById('clock');
    if (clockEl) {
        clockEl.textContent = now.toLocaleTimeString('id-ID', { hour12: false });
    }
    const dateEl = document.getElementById('dateDisplay');
    if (dateEl) {
        dateEl.textContent = now.toLocaleDateString('id-ID', {
            day: 'numeric', month: 'long', year: 'numeric'
        });
    }
    // Update incubation day
    const start = localStorage.getItem('chickhub_incub_start');
    const dayEl = document.getElementById('inkubasiDay');
    if (start && dayEl && dayEl.textContent !== '—') {
        const diff = Math.floor((Date.now() - parseInt(start)) / 86400000) + 1;
        dayEl.textContent = Math.min(diff, 21);
    }
}

// ===== Mode Toggle Global =====
function toggleGlobalMode(btn) {
    if (!btn) return;
    const text = btn.querySelector('.mode-text');
    const icon = btn.querySelector('.mode-icon');

    const heaterLabel = document.querySelector('.heater-mode-label');
    const kipasLabel = document.querySelector('.kipas-mode-label');
    const heaterPid = document.getElementById('heater-pid-content');
    const heaterManual = document.getElementById('heater-manual-content');
    const kipasAuto = document.getElementById('kipas-auto-content');
    const kipasManual = document.getElementById('kipas-manual-content');

    const isAuto = text && text.innerText === 'AUTO';
    const newMode = isAuto ? 'MANUAL' : 'AUTO';

    if (text) text.innerText = newMode;
    if (icon) icon.innerText = isAuto ? 'settings_suggest' : 'smart_toy';
    if (btn) {
        btn.classList.toggle('bg-secondary-container/30', isAuto);
        btn.classList.toggle('bg-surface-container', !isAuto);
    }

    if (heaterLabel) heaterLabel.innerText = isAuto ? 'Mode: Manual' : 'Mode: PID Auto';
    if (kipasLabel) kipasLabel.innerText = isAuto ? 'Mode: Manual Override' : 'Kecepatan: --%';

    if (heaterPid) heaterPid.classList.toggle('hidden', isAuto);
    if (heaterManual) heaterManual.classList.toggle('hidden', !isAuto);
    if (kipasAuto) kipasAuto.classList.toggle('hidden', isAuto);
    if (kipasManual) kipasManual.classList.toggle('hidden', !isAuto);

    // Kirim ke server via MQTT
    ChickMQTT.setMode(newMode);
}

// ===== Panel Toggle =====
function togglePanel(panelId) {
    const panels = ['heater-panel', 'kipas-panel'];
    panels.forEach(id => {
        const p = document.getElementById(id);
        if (!p) return;
        if (id === panelId) {
            p.classList.toggle('hidden');
        } else {
            p.classList.add('hidden');
        }
    });
}

// ===== Login =====
function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUser').value.trim();
    const password = document.getElementById('loginPass').value.trim();

    if (!username || !password) {
        document.getElementById('loginError').textContent = 'Mohon isi username dan password.';
        return;
    }

    // Simple local auth - save to localStorage
    storeSet('user', { username, loggedIn: true, time: Date.now() });
    window.location.href = 'index.html';
}

function checkAuth() {
    const user = storeGet('user', null);
    const loginPage = window.location.pathname.includes('login.html');
    if (!user && !loginPage) {
        window.location.href = 'login.html';
    }
    if (user && loginPage) {
        window.location.href = 'index.html';
    }
}

function handleLogout() {
    storeSet('user', null);
    window.location.href = 'login.html';
}

// ===== Charts =====
function initCharts() {
    ['tempChart', 'humiChart'].forEach(id => drawChart(id, []));
}

function updateCharts(data) {
    const now = new Date();
    const label = now.getHours().toString().padStart(2, '0') + ':' +
                  now.getMinutes().toString().padStart(2, '0');

    if (data.suhu != null) {
        chartHistory.suhu.push(data.suhu);
        if (chartHistory.suhu.length > CHART_MAX) chartHistory.suhu.shift();
    }
    if (data.humi != null) {
        chartHistory.humi.push(data.humi);
        if (chartHistory.humi.length > CHART_MAX) chartHistory.humi.shift();
    }
    chartLabels.push(label);
    if (chartLabels.length > CHART_MAX) chartLabels.shift();

    drawChart('tempChart', chartHistory.suhu, '#fbc02d', 37.5);
    drawChart('humiChart', chartHistory.humi, '#565e74', 60);
}

function drawChart(canvasId, data, color = '#fbc02d', sp = null) {
    const c = document.getElementById(canvasId);
    if (!c || !data.length) return;
    const parent = c.parentElement;
    const W = parent.clientWidth || 400;
    const H = 180;
    c.width = W; c.height = H;
    const ctx = c.getContext('2d');
    const pad = { t: 16, r: 16, b: 28, l: 40 };
    const cw = W - pad.l - pad.r;
    const ch = H - pad.t - pad.b;

    // Background
    ctx.fillStyle = '#f7f9fb';
    ctx.fillRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = '#e0e3e5';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = pad.t + (ch / 4) * i;
        ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
    }

    // Y-axis labels
    ctx.fillStyle = '#4f4633';
    ctx.font = '10px Montserrat, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const isTemp = canvasId === 'tempChart';
    const min = isTemp ? 30 : 0;
    const max = isTemp ? 45 : 100;
    for (let i = 0; i <= 4; i++) {
        const val = max - ((max - min) / 4) * i;
        const y = pad.t + (ch / 4) * i;
        ctx.fillText(val.toFixed(0), pad.l - 6, y);
    }

    // Setpoint line
    if (sp != null) {
        const spY = pad.t + ch - ((sp - min) / (max - min)) * ch;
        ctx.strokeStyle = color + '40';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(pad.l, spY); ctx.lineTo(W - pad.r, spY); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = color + '80';
        ctx.font = '9px Montserrat, sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'bottom';
        ctx.fillText('SP: ' + sp.toFixed(1), W - pad.r - 50, spY - 2);
    }

    // Data line
    if (data.length < 2) {
        // Single point: draw a dot
        const x = pad.l;
        const y = pad.t + ch - ((data[0] - min) / (max - min)) * ch;
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#4f4633';
        ctx.font = '9px Montserrat, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(chartLabels[chartLabels.length - 1] || '', x, H - pad.b + 6);
        return;
    }

    const step = cw / (data.length - 1);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
        const x = pad.l + step * i;
        const y = pad.t + ch - ((data[i] - min) / (max - min)) * ch;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill area
    const last = data.length - 1;
    ctx.lineTo(pad.l + step * last, pad.t + ch);
    ctx.lineTo(pad.l, pad.t + ch);
    ctx.closePath();
    ctx.fillStyle = color + '15';
    ctx.fill();

    // X-axis labels
    ctx.fillStyle = '#4f4633';
    ctx.font = '9px Montserrat, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const labelStep = Math.max(1, Math.floor(data.length / 6));
    for (let i = 0; i < data.length; i += labelStep) {
        const idx = chartLabels.length - data.length + i;
        if (idx >= 0 && idx < chartLabels.length) {
            ctx.fillText(chartLabels[idx], pad.l + step * i, H - pad.b + 6);
        }
    }
    // Last label
    if (chartLabels.length > 0) {
        ctx.fillText(chartLabels[chartLabels.length - 1], pad.l + step * last, H - pad.b + 6);
    }
}

// ===== Init on page load =====
document.addEventListener('DOMContentLoaded', () => {
    // Init MQTT
    ChickMQTT.init();
    ChickMQTT.onStatus(setDashboardData);
    ChickMQTT.onConnection((connected) => {
        const conn = document.getElementById('connStatus');
        if (conn) {
            conn.textContent = connected ? 'terhubung' : 'offline';
            conn.className = 'conn ' + (connected ? 'conn-ok' : 'conn-err');
        }
    });

    // Close panels on outside click
    document.addEventListener('click', (e) => {
        const heaterCard = document.querySelector('[onclick*="heater-panel"]');
        const kipasCard = document.querySelector('[onclick*="kipas-panel"]');
        if (heaterCard && !heaterCard.contains(e.target) &&
            kipasCard && !kipasCard.contains(e.target)) {
            const hp = document.getElementById('heater-panel');
            const kp = document.getElementById('kipas-panel');
            if (hp) hp.classList.add('hidden');
            if (kp) kp.classList.add('hidden');
        }
    });

    // Logo hover effect
    const logo = document.querySelector('aside img, .sidebar-logo');
    if (logo) {
        logo.addEventListener('mouseenter', () => {
            logo.style.transform = 'scale(1.1) rotate(5deg)';
        });
        logo.addEventListener('mouseleave', () => {
            logo.style.transform = 'scale(1) rotate(0deg)';
        });
        logo.style.transition = 'transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
    }

    // Auth check (skip for login page)
    if (!window.location.pathname.includes('login.html')) {
        checkAuth();
    }
});
