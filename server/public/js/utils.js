/* ===== ChickHub - Utility Functions ===== */

// Format tanggal ke string lokal Indonesia
function formatDateTime(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleString('id-ID', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false
    });
}

// Format angka, tampilkan '--' kalau null/undefined
function fmt(val, unit, decimals) {
    if (val === null || val === undefined || val === '--') return '--' + (unit ? ' ' + unit : '');
    const n = parseFloat(val);
    if (isNaN(n)) return '--' + (unit ? ' ' + unit : '');
    let s = decimals !== undefined ? n.toFixed(decimals) : n.toString();
    return s + (unit ? ' ' + unit : '');
}

// Format tanpa unit, return string
function fmtVal(val, decimals) {
    if (val === null || val === undefined || val === '--') return '--';
    const n = parseFloat(val);
    if (isNaN(n)) return '--';
    return decimals !== undefined ? n.toFixed(decimals) : n.toString();
}

// Status class based on value range
function statusClass(suhu, humi) {
    if (!suhu || suhu === '--') return 'status-badge status-badge-normal';
    const s = parseFloat(suhu);
    if (isNaN(s)) return 'status-badge status-badge-normal';
    if (s > 39 || s < 35) return 'status-badge status-badge-warning';
    return 'status-badge status-badge-normal';
}

function statusText(suhu) {
    if (!suhu || suhu === '--') return '—';
    const s = parseFloat(suhu);
    if (isNaN(s)) return '—';
    if (s > 39) return 'WARNING';
    if (s < 35) return 'RENDAH';
    return 'NORMAL';
}

// Escape HTML
function esc(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Debounce
function debounce(fn, ms) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms);
    };
}

// Simpan/load dari localStorage
function storeGet(key, def) {
    try {
        const v = localStorage.getItem('chickhub_' + key);
        return v !== null ? JSON.parse(v) : def;
    } catch { return def; }
}

function storeSet(key, val) {
    try { localStorage.setItem('chickhub_' + key, JSON.stringify(val)); }
    catch { /* ignore */ }
}
