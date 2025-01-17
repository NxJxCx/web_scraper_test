import asyncio
import os
import secrets
import traceback
from functools import partial

from flask import Flask, jsonify, request
from flask_cors import CORS

from svr.service import schedule_app
from svr.webscraper import google_scrape, web_scrape_from_google_using_selenium

app = Flask(__name__)
app.secret_key = (
    os.environ.get("SECRET_KEY")
    if "SECRET_KEY" in os.environ.keys()
    else secrets.token_hex(12)
)

CORS(app)


class Config:
    SCHEDULER_API_ENABLED = True


queue = asyncio.Queue()
queues = {}
app.config.from_object(Config)

scheduler = schedule_app(app)

@app.route("/")
def home():
    return "Welcome to Webscraper app"


@app.route("/search")
async def search():
    global queue
    try:
        search_text: str = str(request.args.get("q", ""))
        if not search_text:
            return jsonify(error="bad request")
        app_stopped: asyncio.Event = asyncio.Event()
        uid = secrets.token_hex(12)
        asyncio.create_task(asyncio.to_thread(web_scrape_from_google_using_selenium, search_text, queue, app_stopped, uid))

        return jsonify(uid=uid)

    except Exception as e:
        traceback.print_exc()
        print("Error:", e)
        return jsonify(error=str(e))

async def get_queues():
    global queue
    global queues
    while not queue.empty():
        uid, msg, result = await queue.get()
        if uid not in queues.keys():
            queues[uid] = asyncio.Queue()
        await queues[uid].put((msg, result))
    await asyncio.sleep(0.1)

@app.route("/result")
async def result():
    global queues
    try:
        await get_queues()
        uid: str = str(request.args.get("uid", ""))
        if not uid:
            return jsonify(error="bad request")
        if uid not in queues.keys():
            return jsonify(error="no processed search")
        myqueue: asyncio.Queue = queues[uid]
        results = []
        while not myqueue.empty():
            msg, result = await myqueue.get()
            results.append((msg, result))
        results.reverse()
        return jsonify(data=results)

    except Exception as e:
        traceback.print_exc()
        print("Error:", e)
        return jsonify(error=str(e))

if __name__ == "__main__":
    scheduler.start()
    app.run(host="0.0.0.0", port=5000, debug=True)
