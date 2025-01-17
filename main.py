import asyncio
import traceback
from collections import deque
from math import floor
from typing import Optional

import numpy as np
import pandas as pd
from kivy.clock import Clock
from kivy.properties import (
    AliasProperty,
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.widget import MDWidget

from svr.webscraper import (
    save_web_scraped_to_csv,
    web_scrape_from_google_using_selenium,
)

if platform == "win":  # For Windows
    print("Running on Windows")
elif platform == "android":  # For Android
    from kivymd.toast import toast

    print("Running on Android")
else:
    print(f"Running on {platform}")


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
            self.interval = None

    def on_enter(self, *args):
        self.interval = Clock.schedule_interval(self._tick_timer, 0.5)

    def on_leave(self, *args):
        self.started = 0
        self.loading = True
        app: WebScraperApp = MDApp.get_running_app()
        app.remove_result_dataframe()
        if self.interval:
            self.interval.cancel()
            self.interval = None

    def set_dataframe(self, dataframe: pd.DataFrame):
        app: WebScraperApp = MDApp.get_running_app()
        app.add_result_dataframe(dataframe)
        columns = [(col, 0.5) for col in dataframe.columns]
        rows = np.array([row.tolist() for _, row in dataframe.items()]).T.tolist()
        self.total_count = len(rows)
        self.columns = columns
        self.rows = rows
        self.loading = False


class WebScraperApp(MDApp):
    kv_directory = "kv"
    message_passing = deque()
    trigger_stop_async: asyncio.Event = None
    result_dataframe: pd.DataFrame = None

    def send_async_message(self, message):
        self.message_passing.append(message)

    def on_stop(self):
        if self.trigger_stop_async:
            self.trigger_stop_async.set()

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


async def async_loop(app_stopped: asyncio.Event, app: WebScraperApp):
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
                        r = await output_queue.get()
                        results = [*results, *r]
                    callback(pd.DataFrame(results), None)
                except Exception as e:
                    traceback.print_exc()
                    callback(None, e)
        if app_stopped.is_set():
            break
        await asyncio.sleep(1.0 / 30.0)
    print("See ya!")


async def main():
    app = WebScraperApp()
    trigger_stop = asyncio.Event()
    app.trigger_stop_async = trigger_stop
    try:
        await asyncio.gather(
            app.async_run(async_lib="asyncio"),
            async_loop(trigger_stop, app),
        )
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())
