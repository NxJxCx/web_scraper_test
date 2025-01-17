import asyncio
import logging
import platform
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException

# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

platform_name = platform.system()

facebook_domains = [
    "facebook",
    # Primary Domains
    "facebook.com",
    "facebook.net",
    "fb.com",
    "fbsbx.com",
    "fbpigeon.com",
    "facebook-hardware.com",
    "fb.gg",
    # Content Delivery Network (CDN) Domains
    "fbcdn.net",
    "fbcdn.com",
    "akamaihd.net",
    # Static Resource Domains
    "static.ak.fbcdn.net",
    "s-static.ak.facebook.com",
    "static.ak.connect.facebook.com",
    # Additional Domains
    "apps.facebook.com",
    "connect.facebook.net",
    "graph.facebook.com",
    "login.facebook.com",
]

# Disable debug logs
logging.getLogger().setLevel(logging.WARNING)


def scrape_facebook_links(
    pages: List[WebElement],
) -> Tuple[List[Dict[str, str]], List[str]]:
    scraped_data = []
    not_facebook_links = []
    for result in pages:
        try:
            title = result.find_element(By.TAG_NAME, "h3").text
            link = result.find_element(By.TAG_NAME, "a").get_attribute("href")
            if any([bool(fb_domain in link) for fb_domain in facebook_domains]):
                scraped_data.append({"Title": title, "Link": link})
            else:
                not_facebook_links.append(link)
        except Exception as e:
            traceback.print_exc()
            print("Error scraping result:", e)  # Log the error
            continue
    return scraped_data, not_facebook_links


def scrape_facebook_links_via_a_tag(
    driver: WebDriver, a_divg: list = []
) -> Tuple[List[Dict[str, str]], List[str]]:
    not_facebook_links = []
    results = []
    all_a = list(
        {
            result.get_attribute("href")
            for result in driver.find_elements(By.TAG_NAME, "a")
            if result not in a_divg and result.get_attribute("href") is not None
        }
    )
    for i, link in enumerate(all_a):
        if any([bool(fb_domain in link) for fb_domain in facebook_domains]):
            results.append({"Title": f"Other links [{i}]", "Link": link})
        else:
            not_facebook_links.append(link)
    return results, not_facebook_links


def goto_link_and_scrape_facebook_links_via_a_tag(
    app_stopped: asyncio.Event, link: str
):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-logging")
    options.add_argument("--headless")  # Run in headless mode for performance
    options.add_argument("--disable-gpu")  # Disable GPU for headless mode
    options.add_argument("--no-sandbox")  # Necessary for some environments
    options.add_argument("--log-level=3")
    options.add_argument("--disable-dev-shm-usage")

    driver = None
    if platform_name == "Windows":
        driver = webdriver.Chrome(options=options)
    else:
        from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

        selenium_grid_url = "http://localhost:4444/wd/hub"
        driver = webdriver.Remote(
            command_executor=selenium_grid_url,
            desired_capabilities=DesiredCapabilities.CHROME,
        )
    try:
        if app_stopped.is_set():
            return []
        # Open Google PH
        driver.get(link)
        if app_stopped.is_set():
            return []
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body script"))
            )
        except TimeoutException | WebDriverException:
            pass
        if app_stopped.is_set():
            return []
        time.sleep(1)
        if app_stopped.is_set():
            return []
        result, _ = scrape_facebook_links_via_a_tag(driver)
        return result
    except Exception as e:
        traceback.print_exc()
        print("error on web scrape other links", e)
        return []
    finally:
        print("other link drivers quitted")
        driver.quit()


async def google_scrape(
    search_text: str, output_queue: asyncio.Queue, app_stopped: asyncio.Event
):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-logging")
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-dev-shm-usage")

    driver = None
    if platform_name == "Windows":
        driver = webdriver.Chrome(options=options)
    else:
        from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

        selenium_grid_url = "http://localhost:4444/wd/hub"
        driver = webdriver.Remote(
            command_executor=selenium_grid_url,
            desired_capabilities=DesiredCapabilities.CHROME,
        )

    try:
        scraped_results = []
        driver.get("https://www.google.com/")
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        search_box.send_keys(search_text)
        search_box.send_keys(Keys.RETURN)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "search"))
            )
        except TimeoutException | WebDriverException:
            pass
        results = driver.find_elements(By.CSS_SELECTOR, "div.g")
        scraped_data, not_facebook_links = scrape_facebook_links(results)
        fb_links, not_fb_links = scrape_facebook_links_via_a_tag(
            driver, [fb["Link"] for fb in scraped_data]
        )
        notfblinks = list({*not_facebook_links, *not_fb_links})
        if app_stopped.is_set():
            return []

        # Use ThreadPoolExecutor for concurrent execution
        with ThreadPoolExecutor(max_workers=3) as executor:
            loop = asyncio.get_event_loop()
            not_fb = await asyncio.gather(
                *[
                    loop.run_in_executor(
                        executor,
                        goto_link_and_scrape_facebook_links_via_a_tag,
                        app_stopped,
                        nfbl,
                    )
                    for nfbl in notfblinks
                ]
            )

        nfb = []
        for nf in not_fb:
            nfb.extend(nf)
        if app_stopped.is_set():
            return []

        scraped_results = [*scraped_results, *nfb, *fb_links, *scraped_data]

        # Handle pagination as before
        next_page = driver.find_elements(By.CSS_SELECTOR, "a#pnnext")
        has_next = len(next_page) > 0

        while has_next:
            if app_stopped.is_set():
                return []
            next_page[0].click()
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "search"))
                )
            except TimeoutException | WebDriverException:
                pass
            results = driver.find_elements(By.CSS_SELECTOR, "div.g")
            scraped_data, not_facebook_links = scrape_facebook_links(results)
            fb_links, not_fb_links = scrape_facebook_links_via_a_tag(
                driver, [fb["Link"] for fb in scraped_data]
            )
            notfblinks = list({*not_facebook_links, *not_fb_links})

            # Reuse ThreadPoolExecutor for pagination
            with ThreadPoolExecutor(max_workers=3) as executor:
                not_fb = await asyncio.gather(
                    *[
                        loop.run_in_executor(
                            executor,
                            goto_link_and_scrape_facebook_links_via_a_tag,
                            app_stopped,
                            nfbl,
                        )
                        for nfbl in notfblinks
                    ]
                )

            nfb = []
            for nf in not_fb:
                nfb.extend(nf)
            scraped_results = [*scraped_results, *nfb, *fb_links, *scraped_data]

            next_page = driver.find_elements(By.CSS_SELECTOR, "a#pnnext")
            has_next = len(next_page) > 0

        await output_queue.put(scraped_results)
    except Exception as e:
        traceback.print_exc()
        print("error on web scraping google", e)
        await output_queue.put([])
    finally:
        print("first driver quitted")
        driver.quit()


def web_scrape_from_google_using_selenium(
    search_text: str, output_queue: asyncio.Queue, app_stopped: asyncio.Event
) -> pd.DataFrame:
    asyncio.run(google_scrape(search_text, output_queue, app_stopped))


def save_web_scraped_to_csv(dataframe: pd.DataFrame) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"facebook_links_{timestamp}.csv"
    dataframe[["Title", "Link"]].to_csv(f"./exports/{filename}")
    return filename
