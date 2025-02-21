import os
import secrets

from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart
from quart_cors import cors

import server.routes as routes

app = Quart(__name__)

app.secret_key = (
    os.environ.get("SECRET_KEY")
    if "SECRET_KEY" in os.environ.keys()
    else secrets.token_hex(12)
)

cors(app)


@app.route("/")
async def home():
    response = await routes.home()
    return response


@app.route("/search")
async def search():
    response = await routes.search()
    return response


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=8000, debug=True)
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    import asyncio
    asyncio.run(serve(app, config))