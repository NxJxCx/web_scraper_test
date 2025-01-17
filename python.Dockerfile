FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl

WORKDIR /app

COPY ./requirements_server.txt /app/requirements.txt
COPY ./svr /app/svr
COPY ./server.py /app/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "server:app"]
