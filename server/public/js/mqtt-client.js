/* ===== ChickHub - MQTT Client (via Server WebSocket) =====
 * Browser → WebSocket → Server → MQTT → Mosquitto → ESP32
 */
const ChickMQTT = (() => {
    let ws = null;
    let reconnectTimer = null;
    let statusListeners = [];
    let connectionListeners = [];
    let connected = false;
    let serverUrl = '';

    function init(url) {
        serverUrl = url || ((location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host);
        connect();
    }

    function connect() {
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

        ws = new WebSocket(serverUrl);

        ws.onopen = () => {
            connected = true;
            notifyConnection(true);
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        };

        ws.onclose = () => {
            connected = false;
            notifyConnection(false);
            scheduleReconnect();
        };

        ws.onerror = () => {
            // onclose will fire after this
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'status') {
                    notifyStatus(msg.data);
                } else if (msg.type === 'history') {
                    notifyStatus({ _history: msg.data });
                }
            } catch { /* ignore parse errors */ }
        };
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connect();
        }, 3000);
    }

    function sendAction(action, payload) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ action, payload }));
    }

    // Set parameter: { key: 'h_kp', value: 8.0 }
    function setParam(key, value) {
        sendAction('set_param', { key, value });
    }

    // Set mode: 'AUTO' or 'MANUAL'
    function setMode(mode) {
        sendAction('set_mode', { mode });
    }

    // Listeners
    function onStatus(fn) { statusListeners.push(fn); }
    function onConnection(fn) { connectionListeners.push(fn); }

    function notifyStatus(data) {
        statusListeners.forEach(fn => { try { fn(data); } catch {} });
    }

    function notifyConnection(state) {
        connectionListeners.forEach(fn => { try { fn(state); } catch {} });
    }

    function isConnected() { return connected; }

    // Cleanup
    function destroy() {
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        statusListeners = [];
        connectionListeners = [];
        if (ws) { ws.onclose = null; ws.close(); ws = null; }
    }

    return { init, connect, setParam, setMode, onStatus, onConnection, isConnected, destroy };
})();
