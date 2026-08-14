import uvicorn
from voodoo.core import create_app
from voodoo.config import config

# Voodoo automatically looks for the "app" folder in the current working directory
app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.host, port=8001, reload=True, ws_max_size=16777216, ws_max_queue=32)
