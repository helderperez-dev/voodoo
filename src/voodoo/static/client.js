const voodoo = {
    ws: null,
    _reconnectAttempts: 0,
    _maxBackoff: 5000,

    init: function() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/_voodoo_ws`);
        this.ws.onopen = () => { this._reconnectAttempts = 0; };
        this.ws.onmessage = this.handleMessage.bind(this);
        this.ws.onclose = () => { this._scheduleReconnect(); };
        this.ws.onerror = () => {};
    },

    _scheduleReconnect: function() {
        const delay = Math.min(1000 * Math.pow(2, this._reconnectAttempts), this._maxBackoff);
        this._reconnectAttempts++;
        setTimeout(() => this.init(), delay);
    },

    sendEvent: function(binding, elementId, value, eventType, meta) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        this.ws.send(JSON.stringify({
            type: 'event',
            binding: binding,
            // Keep `event` during the compatibility window for older servers.
            event: binding,
            event_type: eventType || 'event',
            id: elementId,
            value: value,
            meta: meta || {}
        }));
    },

    valueOf: function(el) {
        if (!el) return null;
        if (el.tagName === 'FORM') {
            return Object.fromEntries(new FormData(el).entries());
        }
        if (el.type === 'checkbox' || el.type === 'radio') return !!el.checked;
        return el.value !== undefined ? el.value : null;
    },

    setTheme: function(mode) {
        let resolved = mode;
        if (resolved === 'system') {
            resolved = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
                ? 'dark' : 'light';
        }
        document.documentElement.classList.toggle('dark', resolved === 'dark');
        document.cookie = 'voodoo_theme=' + encodeURIComponent(mode) + '; path=/; max-age=31536000';
    },

    toggleTheme: function() {
        const dark = !document.documentElement.classList.contains('dark');
        this.setTheme(dark ? 'dark' : 'light');
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

    _focusSnapshot: function() {
        const active = document.activeElement;
        if (!active || active === document.body) return null;
        return {
            id: active.id || null,
            name: active.getAttribute && active.getAttribute('name'),
            start: typeof active.selectionStart === 'number' ? active.selectionStart : null,
            end: typeof active.selectionEnd === 'number' ? active.selectionEnd : null
        };
    },

    _restoreFocus: function(snapshot) {
        if (!snapshot) return;
        let el = snapshot.id ? document.getElementById(snapshot.id) : null;
        if (!el && snapshot.name) {
            try { el = document.querySelector(`[name="${CSS.escape(snapshot.name)}"]`); } catch (_) {}
        }
        if (!el || typeof el.focus !== 'function') return;
        el.focus({preventScroll: true});
        if (snapshot.start !== null && typeof el.setSelectionRange === 'function') {
            try { el.setSelectionRange(snapshot.start, snapshot.end); } catch (_) {}
        }
    },

    patchDOM: function(id, html) {
        const el = document.getElementById(id);
        if (!el) return;

        const focus = this._focusSnapshot();
        const scrollX = window.scrollX;
        const scrollY = window.scrollY;

        if (id === 'root') {
            // StateRenderer may send a root wrapper for backwards compatibility.
            const template = document.createElement('template');
            template.innerHTML = html.trim();
            const candidate = template.content.firstElementChild;
            el.innerHTML = candidate && candidate.id === 'root'
                ? candidate.innerHTML
                : html;
        } else {
            const template = document.createElement('template');
            template.innerHTML = html.trim();
            const replacement = template.content.firstElementChild;
            if (replacement) el.replaceWith(replacement);
        }

        window.scrollTo(scrollX, scrollY);
        this._restoreFocus(focus);
        this.setupBehaviors();
    },

    appendDOM: function(id, html) {
        const el = document.getElementById(id);
        if (el) {
            el.insertAdjacentHTML('beforeend', html);
            this.setupBehaviors();
        }
    },

    navigate: async function(path, options) {
        const opts = options || {};
        const url = new URL(path, window.location.href);
        if (url.origin !== window.location.origin) {
            window.location.href = url.href;
            return;
        }

        const response = await fetch(url.pathname + url.search, {
            headers: {'X-Voodoo-Navigation': '1'},
            credentials: 'same-origin'
        });
        if (!response.ok) {
            window.location.href = url.href;
            return;
        }

        const text = await response.text();
        const doc = new DOMParser().parseFromString(text, 'text/html');
        const nextRoot = doc.getElementById('root');
        const root = document.getElementById('root');
        if (!nextRoot || !root) {
            window.location.href = url.href;
            return;
        }

        root.innerHTML = nextRoot.innerHTML;
        if (doc.title) document.title = doc.title;
        if (!opts.popstate) history.pushState({voodoo: true}, '', url.href);
        window.scrollTo(0, 0);
        this.setupBehaviors();
    },

    scrollToBottom: function(id) {
        const el = id ? document.getElementById(id) : document.scrollingElement;
        if (el) el.scrollTop = el.scrollHeight;
    },

    setupChatBehaviors: function() {
        document.querySelectorAll('[data-vd-enter-send]').forEach(function(el) {
            if (el.dataset.vdWired) return;
            el.dataset.vdWired = '1';
            const binding = el.dataset.vdEnterSend;
            el.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    voodoo.sendEvent(binding, el.id || null, el.value, 'submit');
                    el.value = '';
                    el.style.height = 'auto';
                }
            });
            el.addEventListener('input', function() {
                el.style.height = 'auto';
                el.style.height = Math.min(el.scrollHeight, 200) + 'px';
            });
        });

        document.querySelectorAll('[data-vd-enter-send-trigger]').forEach(function(btn) {
            if (btn.dataset.vdWired) return;
            btn.dataset.vdWired = '1';
            const binding = btn.dataset.vdEnterSendTrigger;
            btn.addEventListener('click', function() {
                const area = btn.parentElement && btn.parentElement.querySelector('[data-vd-enter-send]');
                const value = area ? area.value : '';
                voodoo.sendEvent(binding, area ? area.id || null : null, value, 'submit');
                if (area) {
                    area.value = '';
                    area.style.height = 'auto';
                }
            });
        });

        document.querySelectorAll('[data-vd-auto-scroll]').forEach(function(el) {
            voodoo.scrollToBottom(el.id);
        });
    },

    setupBehaviors: function() {
        this.setupChatBehaviors();
    }
};

function eventBinding(el, type) {
    return el && el.getAttribute ? el.getAttribute(`data-vd-event-${type}`) : null;
}

// One delegated listener per browser event type. Components therefore never
// need inline JavaScript and newly patched DOM works automatically.
document.addEventListener('click', function(e) {
    const actionEl = e.target.closest && e.target.closest('[data-vd-action]');
    if (actionEl && actionEl.dataset.vdAction === 'toggle-theme') {
        e.preventDefault();
        voodoo.toggleTheme();
        return;
    }

    const bound = e.target.closest && e.target.closest('[data-vd-event-click]');
    if (bound) {
        voodoo.sendEvent(eventBinding(bound, 'click'), bound.id || null, voodoo.valueOf(bound), 'click');
    }

    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const link = e.target.closest && e.target.closest('a[href]');
    if (!link || link.target || link.hasAttribute('download') || link.dataset.vdFullReload !== undefined) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin || url.hash && url.pathname === window.location.pathname) return;
    e.preventDefault();
    voodoo.navigate(url.href);
});

document.addEventListener('change', function(e) {
    const binding = eventBinding(e.target, 'change');
    if (binding) voodoo.sendEvent(binding, e.target.id || null, voodoo.valueOf(e.target), 'change');
});

document.addEventListener('input', function(e) {
    const binding = eventBinding(e.target, 'input');
    if (binding) voodoo.sendEvent(binding, e.target.id || null, voodoo.valueOf(e.target), 'input');
});

document.addEventListener('submit', function(e) {
    const binding = eventBinding(e.target, 'submit');
    if (!binding) return;
    e.preventDefault();
    voodoo.sendEvent(binding, e.target.id || null, voodoo.valueOf(e.target), 'submit');
});

window.addEventListener('popstate', function() {
    voodoo.navigate(window.location.href, {popstate: true});
});

document.addEventListener('DOMContentLoaded', () => {
    voodoo.init();
    voodoo.setupBehaviors();
});

window.voodoo = voodoo;

// Legacy facade retained during migration. New Voodoo code passes Python
// callables directly to component props and never needs to use this object.
window.vd = {
    event: function(name, elementId, value) {
        if (arguments.length > 3) value = Array.prototype.slice.call(arguments, 3);
        voodoo.sendEvent(name, elementId, value, 'event');
    }
};
