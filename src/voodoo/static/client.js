const voodoo = {
    ws: null,
    _reconnectAttempts: 0,
    _maxBackoff: 5000,
    init: function() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/_voodoo_ws`);
        this.ws.onopen = () => {
            this._reconnectAttempts = 0;
        };
        this.ws.onmessage = this.handleMessage.bind(this);
        this.ws.onclose = () => {
            this._scheduleReconnect();
        };
        this.ws.onerror = () => {
            // onclose will fire after onerror; let onclose handle reconnect
        };
    },
    _scheduleReconnect: function() {
        const delay = Math.min(1000 * Math.pow(2, this._reconnectAttempts), this._maxBackoff);
        this._reconnectAttempts++;
        setTimeout(() => this.init(), delay);
    },
    
    sendEvent: function(eventName, elementId, value) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'event',
                event: eventName,
                id: elementId,
                value: value
            }));
        }
    },
    
    handleMessage: function(event) {
        const msg = JSON.parse(event.data);
        if (msg.type === 'patch') {
            this.patchDOM(msg.id, msg.html);
        } else if (msg.type === 'append') {
            this.appendDOM(msg.id, msg.html);
        } else if (msg.type === 'reload') {
            window.location.reload();
        }
    },
    
    patchDOM: function(id, html) {
        const el = document.getElementById(id);
        if (el) {
            el.outerHTML = html;
        } else if (id === 'root') {
            document.body.innerHTML = html;
        }
    },
    
    appendDOM: function(id, html) {
        const el = document.getElementById(id);
        if (el) {
            el.insertAdjacentHTML('beforeend', html);
        }
    }
};

document.addEventListener("DOMContentLoaded", () => {
    voodoo.init();
});
window.voodoo = voodoo;