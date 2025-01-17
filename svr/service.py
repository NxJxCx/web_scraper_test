from flask_apscheduler import APScheduler


def scheduled_web_scraping():
    print("Scheduled task executed")


def schedule_app(app, *callbacks):
    scheduler = APScheduler()
    scheduler.init_app(app)

    scheduler.add_job(
        id="Scheduled Task",
        func=scheduled_web_scraping,
        trigger="cron",
        day_of_week="mon,wed,fri",
        hour=8,
    )
    for i, callback in enumerate(callbacks):
        scheduler.add_job(
            id="Scheduled Task # {}".format(i + 1),
            func=callback,
        )
    return scheduler
