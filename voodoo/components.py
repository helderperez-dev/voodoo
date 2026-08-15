import uuid
from typing import Any, List

class Component:
    tag = "div"
    
    def __init__(self, *children, id=None, **kwargs):
        self.id = id or f"vd-{uuid.uuid4().hex[:8]}"
        self.children = children
        self.attributes = kwargs
        
    def render(self) -> str:
        attrs = [f'id="{self.id}"']
        for k, v in self.attributes.items():
            k = k.replace("_", "-")
            if k == "className":
                k = "class"
            if v is not None and v is not False:
                if v is True:
                    attrs.append(f'{k}')
                else:
                    attrs.append(f'{k}="{v}"')
        
        attr_str = " " + " ".join(attrs) if attrs else ""
        
        rendered_children = ""
        for child in self.children:
            if isinstance(child, Component):
                rendered_children += child.render()
            else:
                rendered_children += str(child)
                
        # Self closing tags
        if self.tag in ["input", "img", "br", "hr"]:
            return f"<{self.tag}{attr_str} />"
            
        return f"<{self.tag}{attr_str}>{rendered_children}</{self.tag}>"

class Div(Component):
    tag = "div"

class A(Component):
    tag = "a"
    def __init__(self, *children, href="#", target=None, **kwargs):
        kwargs["href"] = href
        if target:
            kwargs["target"] = target
        # Default styling for a tags if they act like buttons
        classes = kwargs.get("className", "")
        kwargs["className"] = classes
        super().__init__(*children, **kwargs)

class Button(Component):
    tag = "button"
    
    def __init__(self, *children, on_click=None, **kwargs):
        if on_click:
            kwargs["onclick"] = f"voodoo.sendEvent('{on_click}', this.id, this.value)"
        super().__init__(*children, **kwargs)

class Input(Component):
    tag = "input"
    
    def __init__(self, *children, on_change=None, **kwargs):
        if on_change:
            kwargs["onchange"] = f"voodoo.sendEvent('{on_change}', this.id, this.value)"
        super().__init__(*children, **kwargs)

class Card(Component):
    tag = "div"
    def __init__(self, *children, **kwargs):
        classes = kwargs.get("className", "")
        # Remove default conflicting classes if user provides background/border
        default_bg = "bg-[var(--color-surface)]" if "bg-" not in classes else ""
        default_border = "border border-[var(--color-border)]" if "border" not in classes else ""
        kwargs["className"] = f"{default_bg} {default_border} rounded-xl p-6 shadow-xl {classes}".strip()
        super().__init__(*children, **kwargs)

class Text(Component):
    tag = "span"

class Heading(Component):
    tag = "h1"
    def __init__(self, *children, level=1, **kwargs):
        self.tag = f"h{level}"
        super().__init__(*children, **kwargs)

class ChatBox(Component):
    tag = "div"
    def __init__(self, *children, **kwargs):
        classes = kwargs.get("className", "")
        kwargs["className"] = f"flex flex-col space-y-2 overflow-y-auto {classes}".strip()
        super().__init__(*children, **kwargs)

class Table(Component):
    tag = "table"
    def __init__(self, headers: List[str], rows: List[List[Any]], **kwargs):
        super().__init__(**kwargs)
        self.headers = headers
        self.rows = rows
        
    def render(self) -> str:
        th_cells = "".join(f'<th class="px-6 py-4 text-left text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">{h}</th>' for h in self.headers)
        thead = f"<thead class='bg-[var(--color-surface)] border-b border-[var(--color-border)]'><tr>{th_cells}</tr></thead>"
        tbody_rows = []
        for row in self.rows:
            tds = "".join(f'<td class="px-6 py-4 whitespace-nowrap text-sm text-[var(--color-text)]">{cell}</td>' for cell in row)
            tbody_rows.append(f"<tr class='border-b border-[var(--color-border)] hover:bg-[var(--color-surface)] transition-colors'>{tds}</tr>")
        tbody = f"<tbody>{''.join(tbody_rows)}</tbody>"
        
        attrs = [f'id="{self.id}"']
        for k, v in self.attributes.items():
            if k == "className":
                k = "class"
            attrs.append(f'{k}="{v}"')
        
        attr_str = " " + " ".join(attrs) if attrs else ""
        return f"<table{attr_str}>{thead}{tbody}</table>"
