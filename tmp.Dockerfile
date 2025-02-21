# Use a Python base image
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy your app files into the container
COPY ./requirements_server.txt /app/requirements.txt

# Install required dependencies
# RUN python -m pip install --no-cache-dir -r requirements.txt
COPY ./app.py /app/
COPY ./WebScraperApp.spec /app/
COPY ./server /app/server
COPY ./templates /app/templates
COPY ./static /app/static
COPY ./install.sh /app/install.sh

RUN chmod +x /app/install.sh

# Run the generated executable
CMD ["/bin/sh", "/app/install.sh"]
