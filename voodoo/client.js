const voodoo = {
    ws: null,
    init: function() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/_voodoo_ws`);
        this.ws.onmessage = this.handleMessage.bind(this);
        this.ws.onclose = () => {
            console.log("Voodoo WS disconnected. Reconnecting in 1s...");
            setTimeout(() => this.init(), 1000);
        };
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