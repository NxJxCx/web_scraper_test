import asyncio
import traceback

from flask import Flask, jsonify, request

from svr.service import schedule_app
from svr.webscraper import google_scrape

app = Flask(__name__)


class Config:
    SCHEDULER_API_ENABLED = True


app.config.from_object(Config)
scheduler = schedule_app(app)


@app.route("/")
def home():
    return "Welcome to Webscraper app"


@app.route("/test")
async def test():
    try:
        search_text: str = str(request.args.get("q"))
        output_queue: asyncio.Queue = asyncio.Queue()
        app_stopped: asyncio.Event = asyncio.Event()
        await asyncio.gather(
            await google_scrape(search_text, output_queue, app_stopped)
        )
        results = []
        while not output_queue.empty():
            r = await output_queue.get()
            results = [*results, *r]
        return jsonify(data=results)

    except Exception as e:
        traceback.print_exc()
        print("Error:", e)


if __name__ == "__main__":
    scheduler.start()
    app.run(host="0.0.0.0", port=5000)
