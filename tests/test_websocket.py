import pytest
import json
from voodoo.core import register_event, ws_manager

def test_websocket_event(client):
    received = []
    
    async def async_dummy_handler(element_id, value):
        received.append((element_id, value))
        await ws_manager.broadcast_patch("target-1", "<b>Updated</b>")
        
    register_event("test_action", async_dummy_handler)
    
    with client.websocket_connect("/_voodoo_ws") as websocket:
        websocket.send_text(json.dumps({
            "type": "event",
            "event": "test_action",
            "id": "btn-1",
            "value": "clicked"
        }))
        
        # Receive the patch response
        response = websocket.receive_text()
        data = json.loads(response)
        
        assert data["type"] == "patch"
        assert data["id"] == "target-1"
        assert data["html"] == "<b>Updated</b>"
        
    assert len(received) == 1
    assert received[0] == ("btn-1", "clicked")

def test_websocket_append(client):
    async def append_handler(element_id, value):
        await ws_manager.broadcast_append("list-1", "<li>New Item</li>")
        
    register_event("append_action", append_handler)
    
    with client.websocket_connect("/_voodoo_ws") as websocket:
        websocket.send_text(json.dumps({
            "type": "event",
            "event": "append_action",
            "id": "add-btn",
            "value": ""
        }))
        
        response = websocket.receive_text()
        data = json.loads(response)
        
        assert data["type"] == "append"
        assert data["id"] == "list-1"
        assert data["html"] == "<li>New Item</li>"
