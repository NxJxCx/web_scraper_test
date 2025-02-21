FROM selenium/standalone-chrome:latest

COPY ./dist/linux/WebScraperApp /usr/src/app/
RUN chmod +x /usr/src/app/WebScraperApp
CMD ["/usr/src/app/WebScraperApp"]
