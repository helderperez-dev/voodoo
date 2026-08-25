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

    setTheme: function(mode) {
        // mode: 'dark' | 'light' | 'system'
        var resolved = mode;
        if (resolved === 'system') {
            resolved = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
                ? 'dark' : 'light';
        }
        document.documentElement.classList.toggle('dark', resolved === 'dark');
        document.cookie = 'voodoo_theme=' + encodeURIComponent(mode) + '; path=/; max-age=31536000';
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
    },

    // -- Client SDK helpers -------------------------------------------------

    navigate: function(path) {
        history.pushState({}, '', path);
        window.location.reload();  // full restore; SPA-mode lands later
    },

    scrollToBottom: function(id) {
        const el = id ? document.getElementById(id) : document.scrollingElement;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    },

    onEnter: function(el, handler) {
        // Enter sends; Shift+Enter inserts a newline.
        el.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handler(el.value);
            }
        });
    },

    setupChatBehaviors: function() {
        // Wire all composers: Enter sends, button clicks send.
        document.querySelectorAll('[data-vd-enter-send]').forEach(function(el) {
            if (el.dataset.vdWired) return;
            el.dataset.vdWired = '1';
            var eventName = el.dataset.vdEnterSend;
            el.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    voodoo.sendEvent(eventName, el.id || 'composer', el.value);
                    el.value = '';
                    el.style.height = 'auto';
                }
            });
            // Auto-grow textarea
            el.addEventListener('input', function() {
                el.style.height = 'auto';
                el.style.height = Math.min(el.scrollHeight, 200) + 'px';
            });
        });
        document.querySelectorAll('[data-vd-enter-send-trigger]').forEach(function(btn) {
            if (btn.dataset.vdWired) return;
            btn.dataset.vdWired = '1';
            var eventName = btn.dataset.vdEnterSendTrigger;
            btn.addEventListener('click', function() {
                var area = btn.closest('.vd-composer, .vd-flex, div')
                    ? btn.parentElement.querySelector('[data-vd-enter-send]')
                    : null;
                var value = area ? area.value : '';
                voodoo.sendEvent(eventName, area ? area.id || 'composer' : 'composer', value);
                if (area) {
                    area.value = '';
                    area.style.height = 'auto';
                }
            });
        });
        // Auto-scroll message lists on patch/append.
        document.querySelectorAll('[data-vd-auto-scroll]').forEach(function(el) {
            voodoo.scrollToBottom(el.id);
        });
    }
};

// Patch/append keep chat behaviors alive across DOM swaps.
const _origHandleMessage = voodoo.handleMessage.bind(voodoo);
voodoo.handleMessage = function(event) {
    _origHandleMessage(event);
    voodoo.setupChatBehaviors();
};

document.addEventListener("DOMContentLoaded", () => {
    voodoo.init();
    voodoo.setupChatBehaviors();
});
window.voodoo = voodoo;