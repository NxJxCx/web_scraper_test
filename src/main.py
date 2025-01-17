import asyncio
import logging
import os
import sys
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from math import floor
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (AliasProperty, BooleanProperty, ListProperty,
                             NumericProperty, ObjectProperty, StringProperty)
from kivy.resources import resource_add_path, resource_find
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.widget import MDWidget
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

if platform == "win":  # For Windows
    print("Running on Windows")
elif platform == "android":  # For Android
    from kivymd.toast import toast

    print("Running on Android")
else:
    print(f"Running on {platform}")

platform_name = (
    "Windows"
    if platform == "win"
    else (
        "Linux"
        if platform == "linux"
        else "Android" if platform == "android" else "Mac OS"
    )
)

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
    if platform_name == "Windows" or not (
        "SELENIUM_HOST" in os.environ.keys()
        and os.environ.get("SELENIUM_HOST") is not None
    ):
        driver = webdriver.Chrome(options=options)
    else:
        selenium_grid_url = f"http://{os.environ.get('SELENIUM_HOST') if 'SELENIUM_HOST' in os.environ.keys() else 'localhost'}:4444/wd/hub"
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
        except TimeoutException:
            pass
        except WebDriverException:
            pass
        if app_stopped.is_set():
            return []
        time.sleep(2)
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
    search_text: str,
    output_queue: asyncio.Queue,
    app_stopped: asyncio.Event,
    uid: str = "",
):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-logging")
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--log-level=3")
    driver = None
    if platform_name == "Windows" or not (
        "SELENIUM_HOST" in os.environ.keys()
        and os.environ.get("SELENIUM_HOST") is not None
    ):
        driver = webdriver.Chrome(options=options)
    else:
        selenium_grid_url = f"http://{os.environ.get('SELENIUM_HOST') if 'SELENIUM_HOST' in os.environ.keys() else 'localhost'}:4444/wd/hub"
        driver = webdriver.Remote(
            command_executor=selenium_grid_url,
            desired_capabilities=DesiredCapabilities.CHROME,
        )

    try:
        await output_queue.put((uid, "processing", None))
        scraped_results = []
        driver.get("https://www.google.com/")
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        print("SEARCH BOX:", search_box)
        search_box.send_keys(search_text)
        search_box.send_keys(Keys.RETURN)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "search"))
            )
        except TimeoutException as t:
            res1, res2 = (
                driver.find_element(By.TAG_NAME, "div")
                .text.replace("\n", " ")
                .split("URL: ")
            )
            scraped_results = [{"Title": res1, "Link": res2}]
        except WebDriverException as w:
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
        print("All first data:")
        print(len([*scraped_results, *nfb, *fb_links, *scraped_data]))
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
            except TimeoutException:
                pass
            except WebDriverException:
                pass
            print("resulting ok", next_page)
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
            print("all next scrape data:")
            print(len([*scraped_results, *nfb, *fb_links, *scraped_data]))
            scraped_results = [*scraped_results, *nfb, *fb_links, *scraped_data]

            next_page = driver.find_elements(By.CSS_SELECTOR, "a#pnnext")
            has_next = len(next_page) > 0
        print("scraped", len(scraped_results))
        await output_queue.put((uid, "done", scraped_results))
    except Exception as e:
        traceback.print_exc()
        print("error on web scraping google", e)
        await output_queue.put((uid, "error", str(e)))
    finally:
        print("first driver quitted")
        driver.quit()


def web_scrape_from_google_using_selenium(
    search_text: str,
    output_queue: asyncio.Queue,
    app_stopped: asyncio.Event,
    uid: str = "",
) -> pd.DataFrame:
    asyncio.run(google_scrape(search_text, output_queue, app_stopped, uid))


def save_web_scraped_to_csv(dataframe: pd.DataFrame) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"facebook_links_{timestamp}.csv"
    dataframe[["Title", "Link"]].to_csv(f"./exports/{filename}")
    return filename


kv = """
#:import dp kivy.metrics.dp

ScreenManager:
    SearchPage:
        id: search_page
    ResultsPage:
        id: results_page

<SearchPage>:
    name: "search_page"
    SearchBar:
        pos_hint: {"center_x": 0.5, "center_y": 0.5}

<ResultsPage>:
	name: "results_page"
    md_bg_color: app.theme_cls.backgroundColor
    MDLabel:
        text: "Loading... {}".format(root.timer) if root.loading else "Total Facebook links: {}".format(root.total_count)
        halign: 'center'
        pos_hint: {"top": 1, "center_x": 0.5}
        padding: dp(10)
        size_hint_y: None
        height: dp(30)
        md_bg_color: app.theme_cls.primaryColor
        color: 1,1,1
    DisplayTable:
        pos_hint: {"top": 0.94, "center_x": 0.5}
        disabled: root.loading
        column_data: root.columns if root.columns else []
        row_data: root.rows if root.rows else []
        height: dp(300)
    MDButton:
        style: "outlined"
        on_release: root.manager.current = 'search_page'
        pos_hint: {"y": 0.05, "x": 0.1}
        MDButtonText:
            text: 'Back to Menu'
    MDButton:
        style: "outlined"
        on_release: app.save_to_csv()
        disabled: root.loading
        pos_hint: {"y": 0.05, "right": 0.9}
        MDButtonText:
            text: 'Save to CSV'

<SearchBar>:
	size_hint: None, None
	size: dp(500), dp(50)
	MDRelativeLayout:
        size: root.size
		pos: 0,0
		MDFloatLayout:
			size_hint: 1,1
			MDTextField:
				mode: "filled"
				size_hint: 1,1
				pos: root.pos
				text: root.search
				on_text: root._on_search_change(*args)
				on_text_validate: app.search(root.search)
				color: 0, 0, 0, 1
				background_color: 1,1,1
				multiline: False
				MDTextFieldHintText:
					text: root.placeholder

<DisplayTable>:
    size_hint: 1, None
    height: dp(500)
    MDScrollView:
        pos: root.pos
        size: root.size
        do_scroll_x: False
        MDBoxLayout:
            orientation: 'vertical'
            adaptive_height: True
            padding: dp(4)
            TableRowCellContainer:
                id: content_container
                size_hint: 1, None
                height: dp(30 * (len(root.row_data) + 1))
                parent_container: root
                orientation: "vertical"
                canvas.before:
                    Color:
                        rgb: 0, 0, 1
                    Rectangle:
                        size: self.size
                        pos: self.pos
                    Color:
                        rgb: 0,0,0,0

<TableRow>:
    TableRowCellContainer:
        id: content_container
        parent_container: root
        orientation: "horizontal"
        size: root.size
        pos: root.pos

<TableCell>
    size_hint_y: None
    height: dp(30)
    padding: dp(2)
    MDScrollView:
        pos: root.pos
        size: root.size
        do_scroll_y: False
        do_scroll_x: True
        MDLabel:
            id: content
            multiline: False
            color: 0,0,0,1
            padding: dp(4)
            adaptive_width: True
            size_hint_y: 1


<TableRowCellContainer>:
"""


class TableRowCellContainer(MDBoxLayout):
    parent_container = ObjectProperty(None)


class TableCell(MDWidget):
    prev_parent = ObjectProperty(None)

    def get_row(self):
        if (
            self.parent
            and self.parent.parent_container
            and isinstance(self.parent.parent_container, TableRow)
        ):
            return self.parent.parent_container
        return None

    row = AliasProperty(get_row, None, bind=["parent"])

    def get_content(self):
        return self.ids.content if self.ids else None

    content = AliasProperty(get_content, None, bind=["parent"])

    def get_index(self):
        parent: TableRow = self.row
        if parent:
            column_contents: list = parent.get_columns()
            if self in column_contents:
                return column_contents.index(self)
        return -1

    def change_values(self):
        index = self.get_index()
        if index > -1:
            parent: TableRow = self.row
            if parent:
                parent_index = parent.get_index()
                if parent_index > -1:
                    parent_table: DisplayTable = parent.table
                    if parent_table:
                        if parent_index == 0:
                            self.content.text = str(parent_table.column_data[index][0])
                            self.content.bold = True
                            self.size_hint_x = parent_table.column_data[index][1]
                            self.md_bg_color = (
                                MDApp.get_running_app().theme_cls.primaryColor
                            )
                            self.content.color = (
                                MDApp.get_running_app().theme_cls.backgroundColor
                            )
                        else:
                            self.content.text = str(
                                parent_table.row_data[parent_index - 1][index]
                            )
                            self.content.bold = False
                            self.size_hint_x = parent_table.column_data[index][1]
                            self.md_bg_color = (
                                MDApp.get_running_app().theme_cls.backgroundColor
                            )


class TableRow(MDWidget):
    def get_table(self):
        if (
            self.parent
            and self.parent.parent_container
            and isinstance(self.parent.parent_container, DisplayTable)
        ):
            return self.parent.parent_container
        return None

    table = AliasProperty(get_table, None, bind=["parent"])

    def get_index(self):
        if self.table:
            table: DisplayTable = self.table
            if table.row_contents:
                row_contents: list = [
                    content
                    for content in table.row_contents
                    if isinstance(content, TableRow)
                ]
                if self in row_contents:
                    return row_contents.index(self)
        return -1

    def get_content(self):
        return self.ids.content_container if self.ids else None

    content = AliasProperty(get_content, None, bind=["table", "parent"])

    def get_columns(self):
        if self.content:
            content: MDBoxLayout = self.content
            children = [
                child for child in content.children[:] if isinstance(child, TableCell)
            ]
            children.reverse()
            return children
        return []

    def add_cell(self, cell: TableCell):
        if cell not in self.get_columns():
            content: MDBoxLayout = self.get_content()
            content.add_widget(cell)

    def remove_cell(self, cell: TableCell):
        if cell in self.get_columns():
            self.content.remove_widget(cell)

    def clear_cells(self):
        self.content.clear_widgets()


class DisplayTable(MDWidget):
    column_data = ListProperty([])
    row_data = ListProperty([])
    disabled = BooleanProperty(False)

    def get_content(self):
        return self.ids.content_container if self.ids else None

    content = AliasProperty(
        get_content, None, bind=["column_data", "parent", "row_data", "disabled"]
    )

    def get_row_contents(self):
        if self.content:
            children = [child for child in self.content.children[:] if self.content]
            children.reverse()
            return children
        return []

    row_contents = AliasProperty(get_row_contents, None, bind=["content"])

    def get_rows(self):
        return len(self.row_data)

    rows = AliasProperty(get_rows, None, bind=["row_data"])

    def get_cols(self):
        return len(self.column_data)

    cols = AliasProperty(get_cols, None, bind=["column_data"])

    def create_row(self, columns: list):
        row = TableRow()
        for i in range(len(columns)):
            col = TableCell()
            row.add_cell(col)
        return row

    def add_row(self, row: TableRow):
        if row not in self.row_contents:
            self.content.add_widget(row)

    def remove_row(self, row: TableRow):
        if row in self.row_contents:
            self.content.remove_widget(row)

    def clear_rows(self):
        self.content.clear_widgets()

    def refresh_content_widgets(self):
        if self.content:
            self.clear_rows()
            header = self.create_row(self.column_data)
            self.add_row(header)
            for row in self.row_data:
                rows = self.create_row(row)
                self.add_row(rows)

    def on_column_data(self, instance, value):
        self.refresh_content_widgets()
        for row_content in self.row_contents:
            for column in row_content.get_columns():
                colcell: TableCell = column
                colcell.change_values()

    def on_row_data(self, instance, value):
        self.refresh_content_widgets()
        for row_content in self.row_contents:
            for column in row_content.get_columns():
                colcell: TableCell = column
                colcell.change_values()


class SearchBar(MDWidget):
    search = StringProperty("")
    placeholder = StringProperty("Search to scrape")

    def _on_search_change(self, instance, value):
        self.search = value


class SearchPage(MDScreen):
    pass


class ResultsPage(MDScreen):
    loading = BooleanProperty(True)
    columns = ListProperty([])
    rows = ListProperty([])
    started = NumericProperty(0)
    interval = ObjectProperty(None)
    timer = StringProperty("0 sec")
    total_count = NumericProperty(0)

    def _tick_timer(self, dt):
        self.started += dt
        now = floor(self.started)
        seconds = now % 60
        minutes = now // 60
        hours = now // 3600
        timer = f"{hours} hr " if hours > 0 else ""
        timer = f"{minutes} min " if minutes > 0 else ""
        timer += f"{seconds} sec "
        self.timer = timer

    def on_pre_enter(self, *args):
        self.loading = True
        self.started = 0
        app: WebScraperApp = MDApp.get_running_app()
        app.remove_result_dataframe()
        if self.interval:
            self.interval.cancel()

    def on_enter(self, *args):
        self.interval = Clock.schedule_interval(self._tick_timer, 0.5)

    def on_leave(self, *args):
        self.started = 0
        self.loading = True
        app: WebScraperApp = MDApp.get_running_app()
        app.remove_result_dataframe()
        if self.interval:
            self.interval.cancel()

    def set_dataframe(self, dataframe: pd.DataFrame):
        app: WebScraperApp = MDApp.get_running_app()
        app.add_result_dataframe(dataframe)
        columns = [(col, 0.5) for col in dataframe.columns]
        rows = np.array([row.tolist() for _, row in dataframe.items()]).T.tolist()
        self.total_count = len(rows)
        self.columns = columns
        self.rows = rows
        self.loading = False


async def async_loop(app_stopped: asyncio.Event, app):
    app: WebScraperApp = app
    while True:
        if app.message_passing and len(app.message_passing) > 0:
            message = app.message_passing.popleft()
            if message[0] == "search":
                search, callback, next_page = message[1:]
                print("searning for '", search, "'...")
                try:
                    next_page()
                    output_queue = asyncio.Queue()
                    await asyncio.gather(
                        asyncio.to_thread(
                            web_scrape_from_google_using_selenium,
                            search,
                            output_queue,
                            app_stopped,
                        ),
                    )
                    results = []
                    while not output_queue.empty():
                        uid, msg, r = await output_queue.get()
                        print("QUEUE: ", (uid, msg, r))
                        if msg == "done":
                            results = [*results, *r]
                    callback(pd.DataFrame(results), None)
                except Exception as e:
                    traceback.print_exc()
                    callback(None, e)
        if app_stopped.is_set():
            break
        await asyncio.sleep(1.0 / 30.0)
    print("See ya!")


class WebScraperApp(MDApp):
    message_passing = deque()
    trigger_stop_async: asyncio.Event = None
    result_dataframe: pd.DataFrame = None

    def build(self):
        return Builder.load_string(kv)

    async def loop_async_custom(self):
        await async_loop(self.trigger_stop_async, self)

    def send_async_message(self, message):
        self.message_passing.append(message)

    async def wait_all_trigger(self):
        await self.trigger_stop_async.wait()

    def on_stop(self):
        if self.trigger_stop_async:
            self.trigger_stop_async.set()
        loop = asyncio.get_event_loop()
        loop.create_task(self.wait_all_trigger())

    def on_start(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.loop_async_custom())

    def after_search(self, result: Optional[pd.DataFrame], error=None):
        if error:
            print("ERROR:", error)
            root: MDScreenManager = self.root
            root.current = "search_page"
        else:
            resultsPage: ResultsPage = self.root.ids.results_page
            resultsPage.set_dataframe(result)

    def to_results_page(self):
        root: MDScreenManager = self.root
        resultsPage: ResultsPage = root.ids.results_page
        root.current = resultsPage.name

    def search(self, search_text):
        self.send_async_message(
            ("search", search_text, self.after_search, self.to_results_page)
        )

    def add_result_dataframe(self, dataframe: pd.DataFrame):
        self.result_dataframe = dataframe

    def remove_result_dataframe(self):
        self.result_dataframe = None

    def save_to_csv(self):
        if self.result_dataframe is not None:
            filename = save_web_scraped_to_csv(self.result_dataframe)
            if platform == "android":
                toast(f"Saved to {filename}", True, 80, 200, 0)


# async def main():
#     app = WebScraperApp()
#     trigger_stop = asyncio.Event()
#     app.trigger_stop_async = trigger_stop
#     try:
#         await asyncio.gather(
#             app.async_run(async_lib="asyncio"),
#             async_loop(trigger_stop, app),
#         )
#     except:
#         pass


if __name__ == "__main__":
    if hasattr(sys, "_MEIPASS"):
        resource_add_path(os.path.join(sys._MEIPASS))
    try:
        loop = asyncio.get_event_loop()
        trs = trigger_stop_async = asyncio.Event()
        myapp = WebScraperApp()
        myapp.trigger_stop_async = trs
        loop.run_until_complete(myapp.async_run(async_lib="asyncio"))
    finally:
        loop.close()

# if __name__ == "__main__":
#     asyncio.run(main())
