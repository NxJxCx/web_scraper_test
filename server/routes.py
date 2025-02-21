import asyncio
import json
import queue
import secrets
import traceback
from concurrent.futures import ThreadPoolExecutor

from quart import Response, jsonify, render_template, request

from .webscraper import web_scrape_from_google_using_selenium


async def home():
    response = await render_template("index.html")
    return response


async def search():
    search_text: str = str(request.args.get("q", ""))
    if not search_text:
        return jsonify(error="bad request")

    async def stream():
        app_stopped: asyncio.Event = asyncio.Event()
        q: queue.Queue = queue.Queue()
        uid = secrets.token_hex(12)
        executor = ThreadPoolExecutor(max_workers=3)

        try:
            loop = asyncio.get_event_loop()
            # Launch the scraping task in the thread pool
            loop.run_in_executor(
                executor,
                web_scrape_from_google_using_selenium,
                search_text,
                q,
                app_stopped,
                uid,
            )

            while not app_stopped.is_set():
                try:
                    # Process messages from the queue
                    msg = await asyncio.to_thread(q.get)
                    uid, msg_type, result = msg
                    yield "data: {}\n\n".format(json.dumps({msg_type: result}))
                    if msg_type == "error":
                        q.task_done()
                        raise Exception(result)
                    elif msg_type == "done":
                        q.task_done()
                        app_stopped.set()
                except asyncio.TimeoutError:
                    # Timeout allows periodic checks for app_stopped
                    continue
                finally:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Handle when the client disconnects
            app_stopped.set()
        except Exception as e:
            # Log the error and send to the client
            traceback.print_exc()
            yield "data: {}\n\n".format(json.dumps({"error": str(e)}))
        finally:
            yield "data: {}\n\n".format(json.dumps({"exit": True}))
            # Cleanup resources
            app_stopped.set()
            executor.shutdown(wait=True)

    return Response(stream(), content_type="text/event-stream")
