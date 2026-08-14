import uvicorn
from voodoo.core import create_app
from voodoo.config import config

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.host, port=config.port, reload=True, ws_max_size=16777216, ws_max_queue=32)
