"""Hello World — the minimal Voodoo app.

Run: python main.py  or  voodoo dev
"""

from voodoo import App, Text, page

app = App()


@page("/")
def home():
    return Text("Hello, World!")


if __name__ == "__main__":
    app.run()
