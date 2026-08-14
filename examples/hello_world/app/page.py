from voodoo.components import Div, Heading, Text

def page(request):
    """
    A minimal single-page application.
    Voodoo's router will automatically map app/page.py to the root "/" route.
    """
    return Div(
        Heading("Hello, Voodoo! 🪄", level=1, className="text-5xl font-bold text-center mt-32 tracking-tight"),
        Div(Text("This is a minimal example of the Voodoo framework in action."), className="text-center text-gray-500 mt-6 text-lg"),
        className="min-h-screen bg-[var(--color-background)] text-[var(--color-text)]"
    )
