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
        const explicit = el.getAttribute && el.getAttribute('data-vd-value');
        if (explicit !== null && explicit !== undefined) {
            try { return JSON.parse(explicit); } catch (_) { return explicit; }
        }
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

    setupCommandBars: function() {
        document.querySelectorAll('[data-vd-command-bar]').forEach(function(bar) {
            if (bar.dataset.vdWired) return;
            bar.dataset.vdWired = '1';
            const input = bar.querySelector('input[name="command"]');
            const button = bar.querySelector('[data-vd-command-submit]');
            const binding = bar.dataset.vdCommandBinding;
            const submit = function() {
                if (!binding || !input) return;
                voodoo.sendEvent(binding, input.id || null, input.value, 'submit');
            };
            if (input) {
                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        submit();
                    }
                });
            }
            if (button) button.addEventListener('click', submit);
        });
    },

    _focusable: function(root) {
        if (!root) return [];
        return Array.from(root.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), ' +
            'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )).filter(function(el) {
            return !el.hidden &&
                el.getAttribute('aria-hidden') !== 'true' &&
                el.getAttribute('aria-disabled') !== 'true' &&
                !el.closest('[inert]');
        });
    },

    _menuItems: function(menu) {
        if (!menu) return [];
        return Array.from(menu.querySelectorAll('[role="menuitem"]')).filter(function(item) {
            return !item.disabled && item.getAttribute('aria-disabled') !== 'true';
        });
    },

    _storageGet: function(key) {
        try { return window.localStorage.getItem(key); } catch (_) { return null; }
    },

    _storageSet: function(key, value) {
        try { window.localStorage.setItem(key, value); } catch (_) {}
    },

    openDialog: function(id, trigger) {
        const dialog = document.getElementById(id);
        if (!dialog || typeof dialog.showModal !== 'function') return;
        if (dialog._vdCloseTimer) {
            window.clearTimeout(dialog._vdCloseTimer);
            dialog._vdCloseTimer = null;
        }
        if (trigger && trigger.id) dialog.dataset.vdReturnFocus = trigger.id;
        dialog.removeAttribute('data-vd-closing');
        if (!dialog.open) dialog.showModal();
        requestAnimationFrame(() => {
            const first = this._focusable(dialog)[0];
            (first || dialog).focus({preventScroll: true});
        });
    },

    closeDialog: function(dialog) {
        if (!dialog || !dialog.open) return;
        dialog.setAttribute('data-vd-closing', '');
        const finish = () => {
            const trigger = document.getElementById(dialog.dataset.vdReturnFocus || '');
            dialog.removeAttribute('data-vd-closing');
            if (dialog.open) dialog.close();
            if (trigger) {
                window.setTimeout(function() {
                    trigger.focus({preventScroll: true});
                }, 0);
            }
        };
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) finish();
        else dialog._vdCloseTimer = window.setTimeout(finish, 160);
    },

    positionAnchored: function(layer) {
        const anchor = document.getElementById(layer.dataset.vdAnchor || '');
        if (!anchor) return;
        const rect = anchor.getBoundingClientRect();
        const width = layer.offsetWidth || 192;
        const gap = 6;
        let x = rect.left;
        if (layer.dataset.vdAlign === 'center') x = rect.left + (rect.width - width) / 2;
        if (layer.dataset.vdAlign === 'end') x = rect.right - width;
        x = Math.max(8, Math.min(x, window.innerWidth - width - 8));
        let y = rect.bottom + gap;
        const height = layer.offsetHeight || 200;
        if (y + height > window.innerHeight - 8) y = Math.max(8, rect.top - height - gap);
        layer.style.setProperty('--vd-anchor-x', x + 'px');
        layer.style.setProperty('--vd-anchor-y', y + 'px');
    },

    activateTab: function(trigger, focus) {
        const root = trigger && trigger.closest('[data-vd-tabs]');
        if (!root) return;
        const value = trigger.dataset.vdTab;
        const current = root.querySelector('[data-vd-tab][aria-selected="true"]');
        const changed = !current || current.dataset.vdTab !== value;
        root.querySelectorAll('[data-vd-tab]').forEach(function(tab) {
            const active = tab.dataset.vdTab === value;
            tab.setAttribute('aria-selected', active ? 'true' : 'false');
            tab.tabIndex = active ? 0 : -1;
        });
        root.querySelectorAll('[data-vd-tab-panel]').forEach(function(panel) {
            panel.hidden = panel.dataset.vdTabPanel !== value;
        });
        if (focus) trigger.focus({preventScroll: true});
        const binding = eventBinding(root, 'change');
        if (changed && binding) {
            voodoo.sendEvent(binding, root.id || null, value, 'change');
        }
    },

    dismissToast: function(toast) {
        if (!toast || toast.dataset.vdClosing !== undefined) return;
        if (toast._vdTimer) window.clearTimeout(toast._vdTimer);
        toast.setAttribute('data-vd-closing', '');
        const remove = () => toast.remove();
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) remove();
        else window.setTimeout(remove, 180);
    },

    toast: function(message, options) {
        const opts = options || {};
        let region = document.querySelector('[data-vd-toast-region]');
        if (!region) {
            const positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
            const position = positions.includes(opts.position) ? opts.position : 'bottom-right';
            const positionClass = {
                'top-left': 'left-4 top-4',
                'top-right': 'right-4 top-4',
                'bottom-left': 'bottom-4 left-4',
                'bottom-right': 'bottom-4 right-4'
            }[position];
            region = document.createElement('div');
            region.className = (
                'vd-toast-region vd-toast-region--' + position + ' pointer-events-none ' +
                'fixed z-[120] flex w-[min(24rem,calc(100vw-2rem))] ' +
                'flex-col gap-2 ' + positionClass
            );
            region.setAttribute('aria-label', 'Notifications');
            region.setAttribute('aria-live', 'polite');
            region.dataset.vdToastRegion = 'true';
            document.body.appendChild(region);
        }

        const tone = ['info', 'success', 'warning', 'danger'].includes(opts.tone)
            ? opts.tone : 'default';
        const toast = document.createElement('div');
        toast.className = (
            'vd-toast vd-toast--' + tone + ' vd-toast--toast pointer-events-auto ' +
            'flex w-full items-center gap-3 rounded-lg border p-3 shadow-xl'
        );
        toast.setAttribute('role', tone === 'danger' ? 'alert' : 'status');
        toast.dataset.vdToast = 'true';
        const duration = Number(opts.duration === undefined ? 5000 : opts.duration);
        toast.dataset.vdDuration = String(Number.isFinite(duration) && duration >= 0 ? duration : 5000);

        const content = document.createElement('div');
        content.className = 'vd-toast-content min-w-0 flex-1';
        if (opts.title) {
            const title = document.createElement('div');
            title.className = 'vd-toast-title text-sm font-semibold';
            title.textContent = String(opts.title);
            content.appendChild(title);
        }
        const body = document.createElement('div');
        body.className = 'vd-toast-message text-sm';
        body.textContent = String(message);
        content.appendChild(body);
        toast.appendChild(content);

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'vd-toast-dismiss min-h-8 rounded px-2 text-sm';
        close.setAttribute('aria-label', 'Dismiss notification');
        close.dataset.vdDismiss = 'true';
        close.textContent = 'Close';
        toast.appendChild(close);
        region.appendChild(toast);
        const limit = Number.isInteger(opts.limit) && opts.limit > 0 ? opts.limit : 5;
        const queued = region.querySelectorAll('[data-vd-toast]');
        if (queued.length > limit) this.dismissToast(queued[0]);
        this.setupToasts();
        return toast;
    },

    snackbar: function(message, options) {
        const toast = this.toast(message, options);
        toast.classList.add('vd-toast--snackbar');
        return toast;
    },

    setSidebarMode: function(sidebar, mode, persist) {
        if (!sidebar) return;
        const validModes = ['expanded', 'rail', 'hidden'];
        if (!validModes.includes(mode)) {
            mode = validModes.includes(sidebar.dataset.vdSidebarDefault)
                ? sidebar.dataset.vdSidebarDefault : 'expanded';
        }
        sidebar.dataset.vdSidebarMode = mode;
        sidebar.classList.remove('vd-sidebar--expanded', 'vd-sidebar--rail', 'vd-sidebar--hidden');
        sidebar.classList.add('vd-sidebar--' + mode);
        document.querySelectorAll(
            '[data-vd-sidebar-toggle="' + CSS.escape(sidebar.id) + '"]'
        ).forEach(function(toggle) {
            toggle.setAttribute('aria-expanded', mode === 'expanded' ? 'true' : 'false');
            toggle.dataset.vdSidebarCurrentMode = mode;
            if (toggle.dataset.vdSidebarPlacement === 'inside') {
                toggle.setAttribute(
                    'aria-label',
                    mode === 'expanded'
                        ? (toggle.dataset.vdSidebarCollapseLabel || 'Collapse navigation')
                        : (toggle.dataset.vdSidebarExpandLabel || 'Expand navigation')
                );
            }
        });
        if (mode === 'hidden') {
            sidebar.setAttribute('aria-hidden', 'true');
            sidebar.setAttribute('inert', '');
        } else {
            sidebar.removeAttribute('aria-hidden');
            sidebar.removeAttribute('inert');
        }

        const scrimId = sidebar.id + '-scrim';
        let scrim = document.getElementById(scrimId);
        const needsScrim = window.matchMedia('(max-width: 767px)').matches && mode === 'expanded';
        if (needsScrim && !scrim) {
            scrim = document.createElement('button');
            scrim.id = scrimId;
            scrim.type = 'button';
            scrim.className = (
                'vd-sidebar-scrim fixed inset-0 z-[89] border-0 bg-black/40 p-0 backdrop-blur-[1px]'
            );
            scrim.setAttribute('aria-label', 'Close navigation');
            scrim.dataset.vdSidebarDismiss = sidebar.id;
            scrim.dataset.vdSidebarDismissMode =
                sidebar.dataset.vdSidebarDismissMode || 'hidden';
            sidebar.insertAdjacentElement('afterend', scrim);
        } else if (!needsScrim && scrim) {
            scrim.remove();
        }
        if (persist) {
            const viewport = window.matchMedia('(max-width: 767px)').matches
                ? 'mobile' : 'desktop';
            this._storageSet('vd-sidebar:' + sidebar.id + ':' + viewport, mode);
        }
    },

    setupAdaptiveNavigation: function() {
        document.querySelectorAll('[data-vd-sidebar]').forEach(function(sidebar) {
            if (sidebar.dataset.vdResponsiveWired) return;
            sidebar.dataset.vdResponsiveWired = '1';
            const mobile = window.matchMedia('(max-width: 767px)').matches;
            const viewport = mobile ? 'mobile' : 'desktop';
            const stored = voodoo._storageGet('vd-sidebar:' + sidebar.id + ':' + viewport);
            const fallback = mobile && sidebar.dataset.vdSidebarCollapsible !== undefined
                ? sidebar.dataset.vdSidebarMobileMode || 'hidden'
                : sidebar.dataset.vdSidebarDefault || 'expanded';
            const mode = stored || fallback;
            voodoo.setSidebarMode(sidebar, mode, false);
        });
        if (!this._sidebarMediaWired) {
            this._sidebarMediaWired = true;
            const media = window.matchMedia('(max-width: 767px)');
            const update = function(event) {
                document.querySelectorAll('[data-vd-sidebar]').forEach(function(sidebar) {
                    const viewport = event.matches ? 'mobile' : 'desktop';
                    const stored = voodoo._storageGet(
                        'vd-sidebar:' + sidebar.id + ':' + viewport
                    );
                    const fallback = event.matches &&
                        sidebar.dataset.vdSidebarCollapsible !== undefined
                        ? sidebar.dataset.vdSidebarMobileMode || 'hidden'
                        : sidebar.dataset.vdSidebarDefault || 'expanded';
                    voodoo.setSidebarMode(sidebar, stored || fallback, false);
                });
            };
            media.addEventListener('change', update);
        }
    },

    setupMenus: function() {
        document.querySelectorAll('[data-vd-menu]').forEach(function(menu) {
            if (menu.dataset.vdWired) return;
            menu.dataset.vdWired = '1';
            if (typeof menu.showPopover !== 'function') {
                menu.hidden = true;
                return;
            }
            menu.addEventListener('toggle', function() {
                const trigger = document.querySelector(
                    '[data-vd-menu-trigger="' + CSS.escape(menu.id) + '"]'
                );
                const open = menu.matches(':popover-open');
                if (trigger) trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
                if (open) {
                    voodoo.positionAnchored(menu);
                    const first = voodoo._menuItems(menu)[0];
                    if (first) first.focus({preventScroll: true});
                }
            });
        });
        if (!this._menuPositionWired) {
            this._menuPositionWired = true;
            let frame = null;
            const reposition = function() {
                if (frame !== null) return;
                frame = window.requestAnimationFrame(function() {
                    frame = null;
                    document.querySelectorAll('[data-vd-menu]:popover-open').forEach(
                        function(menu) { voodoo.positionAnchored(menu); }
                    );
                });
            };
            window.addEventListener('resize', reposition);
            document.addEventListener('scroll', reposition, true);
        }
    },

    setupDialogs: function() {
        document.querySelectorAll('dialog[data-vd-layer]').forEach(function(dialog) {
            if (dialog.dataset.vdDialogWired) return;
            dialog.dataset.vdDialogWired = '1';
            dialog.addEventListener('close', function() {
                if (dialog._vdCloseTimer) {
                    window.clearTimeout(dialog._vdCloseTimer);
                    dialog._vdCloseTimer = null;
                }
                dialog.removeAttribute('data-vd-closing');
            });
            dialog.addEventListener('click', function(event) {
                if (event.target !== dialog ||
                        dialog.dataset.vdDrawer === undefined ||
                        dialog.dataset.vdDismissible === undefined) return;
                const rect = dialog.getBoundingClientRect();
                const outside = event.clientX < rect.left || event.clientX > rect.right ||
                    event.clientY < rect.top || event.clientY > rect.bottom;
                if (outside) {
                    voodoo.closeDialog(dialog);
                }
            });
            dialog.addEventListener('cancel', function(event) {
                if (dialog.dataset.vdDrawer === undefined) return;
                event.preventDefault();
                if (dialog.dataset.vdDismissible !== undefined) voodoo.closeDialog(dialog);
            });
        });
    },

    setupToasts: function() {
        document.querySelectorAll('[data-vd-toast]').forEach(function(toast) {
            if (toast.dataset.vdWired) return;
            toast.dataset.vdWired = '1';
            const duration = Number(toast.dataset.vdDuration);
            if (Number.isFinite(duration) && duration > 0) {
                toast._vdRemaining = duration;
                const schedule = function() {
                    toast._vdDeadline = Date.now() + toast._vdRemaining;
                    toast._vdTimer = window.setTimeout(
                        () => voodoo.dismissToast(toast),
                        toast._vdRemaining
                    );
                };
                const pause = function() {
                    if (!toast._vdTimer) return;
                    window.clearTimeout(toast._vdTimer);
                    toast._vdTimer = null;
                    toast._vdRemaining = Math.max(0, toast._vdDeadline - Date.now());
                };
                const resume = function(event) {
                    if (event && toast.contains(event.relatedTarget)) return;
                    if (!toast._vdTimer && toast._vdRemaining > 0) schedule();
                };
                toast.addEventListener('mouseenter', pause);
                toast.addEventListener('mouseleave', resume);
                toast.addEventListener('focusin', pause);
                toast.addEventListener('focusout', resume);
                schedule();
            }
        });
    },

    setupBehaviors: function() {
        this.setupChatBehaviors();
        this.setupCommandBars();
        this.setupAdaptiveNavigation();
        this.setupDialogs();
        this.setupMenus();
        this.setupToasts();
    }
};

function eventBinding(el, type) {
    return el && el.getAttribute ? el.getAttribute(`data-vd-event-${type}`) : null;
}

function dispatchClickBinding(bound) {
    if (!bound) return;
    voodoo.sendEvent(
        eventBinding(bound, 'click'),
        bound.id || null,
        voodoo.valueOf(bound),
        'click'
    );
}

// One delegated listener per browser event type. Components therefore never
// need inline JavaScript and newly patched DOM works automatically.
document.addEventListener('click', function(e) {
    const fallbackMenuTrigger = e.target.closest &&
        e.target.closest('[data-vd-menu-trigger]');
    if (fallbackMenuTrigger) {
        const fallbackMenu = document.getElementById(
            fallbackMenuTrigger.dataset.vdMenuTrigger
        );
        if (fallbackMenu && typeof fallbackMenu.showPopover !== 'function') {
            e.preventDefault();
            const opening = fallbackMenu.hidden;
            fallbackMenu.hidden = !opening;
            fallbackMenu.toggleAttribute('data-vd-fallback-open', opening);
            fallbackMenuTrigger.setAttribute('aria-expanded', opening ? 'true' : 'false');
            if (opening) {
                voodoo.positionAnchored(fallbackMenu);
                const first = voodoo._menuItems(fallbackMenu)[0];
                if (first) first.focus({preventScroll: true});
            }
            return;
        }
    }
    document.querySelectorAll('[data-vd-menu][data-vd-fallback-open]').forEach(
        function(menu) {
            const trigger = document.querySelector(
                '[data-vd-menu-trigger="' + CSS.escape(menu.id) + '"]'
            );
            if (menu.contains(e.target) || trigger && trigger.contains(e.target)) return;
            menu.hidden = true;
            menu.removeAttribute('data-vd-fallback-open');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        }
    );

    const sidebarDismiss = e.target.closest && e.target.closest('[data-vd-sidebar-dismiss]');
    if (sidebarDismiss) {
        e.preventDefault();
        voodoo.setSidebarMode(
            document.getElementById(sidebarDismiss.dataset.vdSidebarDismiss),
            sidebarDismiss.dataset.vdSidebarDismissMode || 'hidden',
            true
        );
        return;
    }

    const sidebarToggle = e.target.closest && e.target.closest('[data-vd-sidebar-toggle]');
    if (sidebarToggle) {
        e.preventDefault();
        const sidebar = document.getElementById(sidebarToggle.dataset.vdSidebarToggle);
        if (sidebar) {
            const modes = (sidebarToggle.dataset.vdSidebarModes || 'expanded,rail,hidden').split(',');
            const current = sidebar.dataset.vdSidebarMode || modes[0];
            const next = modes[(modes.indexOf(current) + 1) % modes.length];
            voodoo.setSidebarMode(sidebar, next, true);
            const binding = eventBinding(sidebarToggle, 'change');
            if (binding) {
                voodoo.sendEvent(binding, sidebarToggle.id || null, next, 'change');
            }
        }
        return;
    }

    const dialogTrigger = e.target.closest && e.target.closest('[data-vd-dialog-open]');
    if (dialogTrigger) {
        e.preventDefault();
        voodoo.openDialog(dialogTrigger.dataset.vdDialogOpen, dialogTrigger);
        return;
    }

    const dialogClose = e.target.closest && e.target.closest('[data-vd-dialog-close]');
    if (dialogClose) {
        e.preventDefault();
        voodoo.closeDialog(dialogClose.closest('dialog'));
        return;
    }

    const dismiss = e.target.closest && e.target.closest('[data-vd-dismiss]');
    if (dismiss) {
        e.preventDefault();
        voodoo.dismissToast(dismiss.closest('[data-vd-toast]'));
        return;
    }

    const tab = e.target.closest && e.target.closest('[data-vd-tab]');
    if (tab) {
        e.preventDefault();
        voodoo.activateTab(tab, true);
        return;
    }

    const menuItem = e.target.closest && e.target.closest('[role="menuitem"]');
    if (menuItem) {
        if (menuItem.disabled || menuItem.getAttribute('aria-disabled') === 'true') {
            e.preventDefault();
            return;
        }
        const menu = menuItem.closest('[data-vd-menu]');
        if (menu && typeof menu.hidePopover === 'function') {
            menu.hidePopover();
        } else if (menu) {
            menu.hidden = true;
            menu.removeAttribute('data-vd-fallback-open');
            const trigger = document.querySelector(
                '[data-vd-menu-trigger="' + CSS.escape(menu.id) + '"]'
            );
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        }
    }

    const actionEl = e.target.closest && e.target.closest('[data-vd-action]');
    if (actionEl && actionEl.dataset.vdAction === 'toggle-theme') {
        e.preventDefault();
        voodoo.toggleTheme();
        return;
    }

    const bound = e.target.closest && e.target.closest('[data-vd-event-click]');
    if (bound) dispatchClickBinding(bound);

    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const link = e.target.closest && e.target.closest('a[href]');
    if (!link || link.target || link.hasAttribute('download') || link.dataset.vdFullReload !== undefined) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin || url.hash && url.pathname === window.location.pathname) return;
    e.preventDefault();
    voodoo.navigate(url.href);
});

// Non-native interactive surfaces (for example selectable DataTable rows)
// receive keyboard activation without application-side JavaScript.
document.addEventListener('keydown', function(e) {
    const menu = e.target.closest && e.target.closest('[data-vd-menu]');
    if (menu) {
        if (e.key === 'Escape') {
            if (typeof menu.hidePopover === 'function') menu.hidePopover();
            else {
                menu.hidden = true;
                menu.removeAttribute('data-vd-fallback-open');
            }
            const trigger = document.querySelector(
                '[data-vd-menu-trigger="' + CSS.escape(menu.id) + '"]'
            );
            if (trigger) {
                trigger.setAttribute('aria-expanded', 'false');
                trigger.focus({preventScroll: true});
            }
            return;
        }
        const items = voodoo._menuItems(menu);
        if (!items.length) return;
        const current = items.indexOf(document.activeElement);
        let next = null;
        if (e.key === 'ArrowDown') next = items[(current + 1) % items.length];
        if (e.key === 'ArrowUp') next = items[(current - 1 + items.length) % items.length];
        if (e.key === 'Home') next = items[0];
        if (e.key === 'End') next = items[items.length - 1];
        if (next) {
            e.preventDefault();
            next.focus({preventScroll: true});
            return;
        }
        if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
            window.clearTimeout(menu._vdTypeaheadTimer);
            menu._vdTypeahead = (menu._vdTypeahead || '') + e.key.toLocaleLowerCase();
            menu._vdTypeaheadTimer = window.setTimeout(function() {
                menu._vdTypeahead = '';
            }, 500);
            const ordered = items.slice(current + 1).concat(items.slice(0, current + 1));
            const match = ordered.find(function(item) {
                return item.textContent.trim().toLocaleLowerCase().startsWith(menu._vdTypeahead);
            });
            if (match) {
                e.preventDefault();
                match.focus({preventScroll: true});
                return;
            }
        }
    }

    const tab = e.target.closest && e.target.closest('[data-vd-tab]');
    if (tab) {
        const root = tab.closest('[data-vd-tabs]');
        const tabs = Array.from(root.querySelectorAll('[data-vd-tab]:not([disabled])'));
        const current = tabs.indexOf(tab);
        const vertical = root.dataset.vdOrientation === 'vertical';
        const automatic = root.dataset.vdActivation !== 'manual';
        let next = null;
        if (e.key === (vertical ? 'ArrowDown' : 'ArrowRight')) next = tabs[(current + 1) % tabs.length];
        if (e.key === (vertical ? 'ArrowUp' : 'ArrowLeft')) next = tabs[(current - 1 + tabs.length) % tabs.length];
        if (e.key === 'Home') next = tabs[0];
        if (e.key === 'End') next = tabs[tabs.length - 1];
        if (next) {
            e.preventDefault();
            if (automatic) voodoo.activateTab(next, true);
            else next.focus({preventScroll: true});
            return;
        }
        if (!automatic && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            voodoo.activateTab(tab, true);
            return;
        }
    }

    if (e.key !== 'Enter' && e.key !== ' ') return;
    const bound = e.target.closest && e.target.closest('[data-vd-event-click]');
    if (!bound) return;
    const tag = bound.tagName;
    if (tag === 'BUTTON' || tag === 'A' || tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    e.preventDefault();
    dispatchClickBinding(bound);
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
