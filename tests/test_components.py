import pytest
from voodoo.components import Component, Div, Button, Input, Card, Text, Heading, ChatBox, Table

def test_component_base():
    comp = Component("Hello", id="test-1", className="bg-red-500", data_custom="value")
    html = comp.render()
    assert html == '<div id="test-1" class="bg-red-500" data-custom="value">Hello</div>'

def test_div():
    div = Div("Content", id="d1")
    assert div.render() == '<div id="d1">Content</div>'

def test_button():
    btn = Button("Click Me", id="btn-1", on_click="my_action")
    html = btn.render()
    assert html == '<button id="btn-1" onclick="voodoo.sendEvent(\'my_action\', this.id, this.value)">Click Me</button>'

def test_input():
    inp = Input(id="inp-1", on_change="input_changed", type="text")
    html = inp.render()
    assert html == '<input id="inp-1" type="text" onchange="voodoo.sendEvent(\'input_changed\', this.id, this.value)" />'

def test_card():
    card = Card("Card Content", id="card-1", className="extra-class")
    html = card.render()
    assert html == '<div id="card-1" class="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6 shadow-xl extra-class">Card Content</div>'

def test_text():
    text = Text("Span Text", id="txt-1")
    assert text.render() == '<span id="txt-1">Span Text</span>'

def test_heading():
    h1 = Heading("H1 Title", id="h-1")
    assert h1.render() == '<h1 id="h-1">H1 Title</h1>'
    
    h3 = Heading("H3 Title", id="h-3", level=3)
    assert h3.render() == '<h3 id="h-3">H3 Title</h3>'

def test_chatbox():
    box = ChatBox("Messages", id="chat-1")
    assert box.render() == '<div id="chat-1" class="flex flex-col space-y-2 overflow-y-auto">Messages</div>'

def test_table():
    table = Table(
        headers=["Name", "Age"],
        rows=[["Alice", 30], ["Bob", 25]],
        id="tbl-1",
        className="my-table"
    )
    html = table.render()
    assert html.startswith('<table id="tbl-1" class="my-table">')
    assert '<th class="px-6 py-4 text-left text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Name</th>' in html
    assert '<td class="px-6 py-4 whitespace-nowrap text-sm text-[var(--color-text)]">Alice</td>' in html
