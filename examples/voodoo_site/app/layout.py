from voodoo.components import Component, Div, Text, Heading
from voodoo.i18n import _

class Link(Component):
    tag = "a"
    def __init__(self, *children, href="#", **kwargs):
        kwargs["href"] = href
        super().__init__(*children, **kwargs)

class Icon(Component):
    tag = "span"
    def __init__(self, svg_code: str, **kwargs):
        super().__init__(**kwargs)
        self.svg_code = svg_code
        
    def render(self) -> str:
        attrs = [f'id="{self.id}"']
        for k, v in self.attributes.items():
            if k == "className": k = "class"
            attrs.append(f'{k}="{v}"')
        attr_str = " " + " ".join(attrs) if attrs else ""
        return f"<span{attr_str}>{self.svg_code}</span>"

def Sidebar():
    icons = {
        "dashboard": '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>',
        "leads": '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>',
        "agent": '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>',
        "storage": '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path></svg>',
        "docs": '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>',
    }
    
    return Div(
        Div(
            Heading("Voodoo", level=1, className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-[var(--color-secondary)] to-[var(--color-primary)] tracking-tight"),
            className="mb-10 px-4"
        ),
        Div(
            Link(
                Div(Icon(icons["dashboard"]), Text(_("sidebar.dashboard")), className="flex items-center space-x-3"),
                href="/",
                className="block py-2 px-4 rounded-lg hover:bg-[var(--color-surface)] transition-colors text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            ),
            Link(
                Div(Icon(icons["leads"]), Text(_("sidebar.leads")), className="flex items-center space-x-3"),
                href="/leads",
                className="block py-2 px-4 rounded-lg hover:bg-[var(--color-surface)] transition-colors text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            ),
            Link(
                Div(Icon(icons["agent"]), Text(_("sidebar.agent")), className="flex items-center space-x-3"),
                href="/agent",
                className="block py-2 px-4 rounded-lg hover:bg-[var(--color-surface)] transition-colors text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            ),
            Link(
                Div(Icon(icons["storage"]), Text(_("sidebar.storage")), className="flex items-center space-x-3"),
                href="/storage",
                className="block py-2 px-4 rounded-lg hover:bg-[var(--color-surface)] transition-colors text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            ),
            Link(
                Div(Icon(icons["docs"]), Text("Docs"), className="flex items-center space-x-3"),
                href="/documentation",
                className="block py-2 px-4 rounded-lg hover:bg-[var(--color-surface)] transition-colors text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            ),
            className="space-y-2 flex-1"
        ),
        Div(
            Div(
                """
                <script>
                function toggleTheme() {
                    const html = document.documentElement;
                    if (html.classList.contains('dark')) {
                        html.classList.remove('dark');
                        html.classList.add('light');
                        document.cookie = "voodoo_theme=light; path=/";
                    } else {
                        html.classList.remove('light');
                        html.classList.add('dark');
                        document.cookie = "voodoo_theme=dark; path=/";
                    }
                }
                function switchLang(lang) {
                    document.cookie = "voodoo_lang=" + lang + "; path=/";
                    window.location.reload();
                }
                </script>
                """
            ),
            Div(
                Component(
                    tag="button",
                    onclick="toggleTheme()",
                    className="p-2 rounded-lg hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors",
                    * [
                        Icon('<svg class="w-5 h-5 hidden dark:block" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>'),
                        Icon('<svg class="w-5 h-5 block dark:hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>')
                    ]
                ),
                Div(
                    Component(tag="button", onclick="switchLang('en')", className="text-xs font-semibold px-2 py-1 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors", *["EN"]),
                    Component(tag="button", onclick="switchLang('pt')", className="text-xs font-semibold px-2 py-1 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors", *["PT"]),
                    className="flex space-x-1"
                ),
                className="flex items-center justify-between px-2 pt-4 border-t border-[var(--color-border)]"
            ),
            className="mt-auto"
        ),
        className="w-64 h-screen fixed left-0 top-0 border-r border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur-xl p-6 flex flex-col z-50"
    )

def Layout(content: Component, title: str = ""):
    return Div(
        Sidebar(),
        Div(
            Div(
                Heading(title, level=2, className="text-3xl font-semibold text-[var(--color-text)] mb-8 tracking-tight") if title else "",
                content,
                className="max-w-6xl mx-auto"
            ),
            className="ml-64 p-10 min-h-screen"
        ),
        className="min-h-screen bg-[var(--color-background)] font-sans text-[var(--color-text)] antialiased selection:bg-[var(--color-secondary)] selection:text-white"
    )
