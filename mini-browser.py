#!/usr/bin/env python3
"""MiniBrowser — A small but full-featured web browser built with PyQt6 + QtWebEngine."""

import sys
import os
import sqlite3
import json
import shutil
import subprocess
import gettext
import gc
from urllib.parse import quote
from datetime import datetime

from PyQt6.QtCore import Qt, QUrl, QSettings, QStandardPaths, QSize
from PyQt6.QtGui import QAction, QKeySequence, QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
    QDialog, QListWidget, QListWidgetItem, QLabel, QDialogButtonBox,
    QMessageBox, QFileDialog, QCheckBox, QSpinBox, QGroupBox, QFormLayout,
    QComboBox,
    QProgressBar
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest,
    QWebEngineSettings
)
from PyQt6.QtNetwork import QNetworkProxy

# ── Internationalization ──────────────────────────────────────────────
LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")
try:
    _translations = gettext.translation("mini-browser", LOCALE_DIR, fallback=True)
    _ = _translations.gettext
except Exception:
    _ = lambda s: s
# ──────────────────────────────────────────────────────────────────────

APP_NAME = "MiniBrowser"
APP_VERSION = "1.0"
DATA_DIR = os.path.join(
    QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation),
    APP_NAME
)
HISTORY_DB = os.path.join(DATA_DIR, "history.db")
BOOKMARKS_FILE = os.path.join(DATA_DIR, "bookmarks.json")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
COOKIE_DIR = os.path.join(DATA_DIR, "cookies")
CONF_FILE = os.path.join(DATA_DIR, "conf.json")
DEFAULT_HOME = "https://www.google.com"

def _read_chromium_config() -> str:
    """读取低内存模式等配置（QApplication 创建前调用）。"""
    try:
        with open(CONF_FILE, "r") as f:
            cfg = json.load(f)
            if cfg.get("low_memory_mode"):
                return "--single-process"
    except Exception:
        pass
    return ""

# ── Chromium 精简配置 ─────────────────────────────────────────────────
# 在 QApplication 创建前设置 Chromium 命令行标志
_extra_cfg = _read_chromium_config()
_CHROME_FLAGS = " ".join([
    "--disable-gpu",                          # 禁用 GPU 进程（省 ~150 MB）
    "--disable-software-rasterizer",           # 禁用软件光栅化
    "--process-per-site",                      # 同站点共享渲染进程
    "--disable-features=TranslateUI,ChromeWhatsNewUI,BackgroundSync,"
    "NotificationTriggers,Sync,MediaSession,KeyboardLockAPI,"
    "WebNfc,WebBluetooth,WebUsb,WebShare,WebXr",
    "--disable-background-networking",         # 禁用后台网络
    "--disable-sync",                           # 禁用同步
    "--disable-component-update",               # 禁用组件更新
    "--no-first-run",                           # 跳过首次运行
    "--no-pings",                               # 禁用超链接审计
    "--mute-audio",                             # 默认静音
    "--disable-breakpad",                       # 禁用崩溃上报
    "--disable-domain-reliability",              # 禁用域名可靠性报告
    "--max_old_space_size=256",                  # V8 堆上限 256 MB
])
if _extra_cfg:
    _CHROME_FLAGS += " " + _extra_cfg
_old_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    _old_flags + " " + _CHROME_FLAGS if _old_flags else _CHROME_FLAGS
)
# ──────────────────────────────────────────────────────────────────────

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(COOKIE_DIR, exist_ok=True)


class HistoryManager:
    """SQLite-backed browsing history."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    visit_time REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_time ON history(visit_time DESC)")
            conn.commit()

    def add_entry(self, url: str, title: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO history (url, title, visit_time) VALUES (?, ?, ?)",
                (url, title, datetime.now().timestamp())
            )
            conn.commit()

    def get_all(self, limit: int = 500) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT url, title, visit_time FROM history ORDER BY visit_time DESC LIMIT ?",
                (limit,)
            )
            return cur.fetchall()

    def search(self, keyword: str, limit: int = 100) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT url, title, visit_time FROM history "
                "WHERE url LIKE ? OR title LIKE ? ORDER BY visit_time DESC LIMIT ?",
                (f"%{keyword}%", f"%{keyword}%", limit)
            )
            return cur.fetchall()

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history")
            conn.commit()

    def delete_url(self, url: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history WHERE url = ?", (url,))
            conn.commit()


class BookmarkManager:
    """JSON-file-based bookmark storage."""

    def __init__(self, path: str):
        self.path = path
        self._bookmarks: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._bookmarks = json.load(f)
            except Exception:
                self._bookmarks = []

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._bookmarks, f, indent=2, ensure_ascii=False)

    def get_all(self) -> list[dict]:
        return list(self._bookmarks)

    def add(self, url: str, title: str):
        for b in self._bookmarks:
            if b["url"] == url:
                b["title"] = title
                self._save()
                return
        self._bookmarks.append({"url": url, "title": title})
        self._save()

    def remove(self, url: str):
        self._bookmarks = [b for b in self._bookmarks if b["url"] != url]
        self._save()

    def is_bookmarked(self, url: str) -> bool:
        return any(b["url"] == url for b in self._bookmarks)


class BrowserTab(QWidget):
    """A single tab with its own navigation bar and web view."""

    def __init__(self, profile: QWebEngineProfile, parent_browser=None):
        super().__init__()
        self.parent_browser = parent_browser
        self._history: list[QUrl] = []
        self._history_index = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        nav.setContentsMargins(6, 4, 6, 4)

        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip(_("Back"))
        self.btn_back.setFixedWidth(32)
        self.btn_back.setEnabled(False)

        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip(_("Forward"))
        self.btn_forward.setFixedWidth(32)
        self.btn_forward.setEnabled(False)

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setToolTip(_("Refresh"))
        self.btn_refresh.setFixedWidth(32)

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText(_("Enter URL or search\u2026"))
        self.address_bar.setClearButtonEnabled(True)

        self.btn_bookmark = QPushButton("☆")
        self.btn_bookmark.setToolTip(_("Bookmark"))
        self.btn_bookmark.setFixedWidth(32)
        self.btn_bookmark.setCheckable(True)

        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_forward)
        nav.addWidget(self.btn_refresh)
        nav.addWidget(self.address_bar, 1)
        nav.addWidget(self.btn_bookmark)

        nav_widget = QWidget()
        nav_widget.setLayout(nav)
        layout.addWidget(nav_widget)

        self.web_view = QWebEngineView()
        self.web_page = QWebEnginePage(profile, self.web_view)
        self.web_view.setPage(self.web_page)
        layout.addWidget(self.web_view, 1)

        self.web_view.loadProgress.connect(self._on_load_progress)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.titleChanged.connect(self._on_title_changed)
        self.web_view.loadFinished.connect(self._on_load_finished)

        self.address_bar.returnPressed.connect(self._navigate_to_address)

        self.btn_back.clicked.connect(self._go_back)
        self.btn_forward.clicked.connect(self._go_forward)
        self.btn_refresh.clicked.connect(lambda: self.web_view.reload())
        self.btn_bookmark.clicked.connect(self._toggle_bookmark)

    def navigate(self, url: QUrl):
        self._history = self._history[:self._history_index + 1]
        self._history.append(url)
        self._history_index = len(self._history) - 1
        self._update_nav_buttons()
        self.web_view.setUrl(url)

    def _navigate_to_address(self):
        text = self.address_bar.text().strip()
        if not text:
            return
        url = QUrl(text)
        if url.scheme() == "":
            if "." not in text or " " in text:
                search_url = self._get_search_url()
                url = QUrl(search_url.format(query=quote(text)))
            else:
                url = QUrl(f"https://{text}")
        self.navigate(url)

    def _get_search_url(self) -> str:
        if self.parent_browser:
            return self.parent_browser.search_url
        return "https://www.google.com/search?q={query}"

    def _on_url_changed(self, url: QUrl):
        self.address_bar.setText(url.toString())
        if self.parent_browser:
            bm = self.parent_browser.bookmark_manager
            self.btn_bookmark.setChecked(bm.is_bookmarked(url.toString()))

    def _on_title_changed(self, title: str):
        if self.parent_browser:
            idx = self.parent_browser.tabs.indexOf(self)
            if idx >= 0:
                tab_text = title[:20] + "\u2026" if len(title) > 20 else title
                self.parent_browser.tabs.setTabText(idx, tab_text)
                self.parent_browser.tabs.setTabToolTip(idx, title)

    def _on_load_finished(self, ok: bool):
        if ok and self.parent_browser:
            url = self.web_view.url().toString()
            title = self.web_view.page().title()
            self.parent_browser.history_manager.add_entry(url, title)

    def _on_load_progress(self, progress: int):
        if progress < 100 and self.parent_browser:
            self.parent_browser.statusBar().showMessage(_("Loading\u2026 {}%").format(progress))
        else:
            if self.parent_browser:
                self.parent_browser.statusBar().clearMessage()

    def _go_back(self):
        if self._history_index > 0:
            self._history_index -= 1
            self.web_view.setUrl(self._history[self._history_index])
            self._update_nav_buttons()

    def _go_forward(self):
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.web_view.setUrl(self._history[self._history_index])
            self._update_nav_buttons()

    def _update_nav_buttons(self):
        self.btn_back.setEnabled(self._history_index > 0)
        self.btn_forward.setEnabled(self._history_index < len(self._history) - 1)

    def _toggle_bookmark(self, checked: bool):
        if not self.parent_browser:
            return
        bm = self.parent_browser.bookmark_manager
        url = self.web_view.url().toString()
        title = self.web_view.page().title()
        if checked:
            bm.add(url, title)
        else:
            bm.remove(url)

    def current_url(self) -> str:
        return self.web_view.url().toString()

    def current_title(self) -> str:
        return self.web_view.page().title()


class HistoryDialog(QDialog):
    def __init__(self, history_mgr: HistoryManager, parent=None):
        super().__init__(parent)
        self.history_mgr = history_mgr
        self.setWindowTitle(_("History"))
        self.resize(700, 450)
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_("Search history\u2026"))
        self.search_input.textChanged.connect(self._on_search)
        btn_clear = QPushButton(_("Clear All"))
        btn_clear.clicked.connect(self._clear_all)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(btn_clear)
        layout.addLayout(search_layout)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._open_url)
        layout.addWidget(self.list_widget, 1)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_history(self, keyword: str = ""):
        self.list_widget.clear()
        rows = self.history_mgr.search(keyword) if keyword else self.history_mgr.get_all()
        for url, title, ts in rows:
            dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            display = f"{title}  \u2014  {url}" if title else url
            item = QListWidgetItem(f"[{dt}]  {display}")
            item.setData(Qt.ItemDataRole.UserRole, url)
            item.setToolTip(f"{url}\n{dt}")
            self.list_widget.addItem(item)

    def _on_search(self, text: str):
        self._load_history(text.strip())

    def _clear_all(self):
        reply = QMessageBox.question(
            self, _("Confirm"), _("Clear all history?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_mgr.clear()
            self._load_history()

    def _open_url(self, item: QListWidgetItem):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url and self.parent():
            self.parent().open_url_in_new_tab(url)
            self.accept()


class BookmarkDialog(QDialog):
    def __init__(self, bookmark_mgr: BookmarkManager, parent=None):
        super().__init__(parent)
        self.bookmark_mgr = bookmark_mgr
        self.setWindowTitle(_("Bookmarks"))
        self.resize(600, 400)
        self._setup_ui()
        self._load_bookmarks()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._open_url)
        layout.addWidget(self.list_widget, 1)

        btn_layout = QHBoxLayout()
        btn_open = QPushButton(_("Open"))
        btn_open.clicked.connect(self._open_selected)
        btn_delete = QPushButton(_("Delete"))
        btn_delete.clicked.connect(self._delete_selected)
        btn_close = QPushButton(_("Close"))
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _load_bookmarks(self):
        self.list_widget.clear()
        for b in self.bookmark_mgr.get_all():
            item = QListWidgetItem(f"{b['title']}  \u2014  {b['url']}")
            item.setData(Qt.ItemDataRole.UserRole, b["url"])
            item.setToolTip(b["url"])
            self.list_widget.addItem(item)

    def _open_url(self, item: QListWidgetItem):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url and self.parent():
            self.parent().open_url_in_new_tab(url)
            self.accept()

    def _open_selected(self):
        item = self.list_widget.currentItem()
        if item:
            self._open_url(item)

    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.bookmark_mgr.remove(url)
            self._load_bookmarks()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.resize(500, 400)
        self.parent_browser = parent
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        grp_home = QGroupBox(_("Homepage"))
        home_layout = QHBoxLayout()
        self.home_edit = QLineEdit()
        home_layout.addWidget(self.home_edit, 1)
        grp_home.setLayout(home_layout)
        layout.addWidget(grp_home)

        grp_proxy = QGroupBox(_("Proxy"))
        proxy_layout = QFormLayout()
        self.proxy_type = QComboBox()
        self.proxy_type.addItems([_("None"), _("HTTP"), _("SOCKS5")])
        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText("127.0.0.1")
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(1080)
        proxy_layout.addRow(_("Type:"), self.proxy_type)
        proxy_layout.addRow(_("Host:"), self.proxy_host)
        proxy_layout.addRow(_("Port:"), self.proxy_port)
        grp_proxy.setLayout(proxy_layout)
        layout.addWidget(grp_proxy)

        grp_search = QGroupBox(_("Search Engine"))
        search_layout = QFormLayout()
        self.search_engine_combo = QComboBox()
        self.search_engine_combo.addItems([
            "Google", "Bing", "DuckDuckGo", "Baidu"
        ])
        search_layout.addRow(_("Engine:"), self.search_engine_combo)
        grp_search.setLayout(search_layout)
        layout.addWidget(grp_search)

        grp_perf = QGroupBox(_("Performance"))
        perf_layout = QVBoxLayout()
        self.chk_low_mem = QCheckBox(_("Low Memory Mode (single process)"))
        self.chk_low_mem.setToolTip(_(
            "Run all browser components in a single process to save memory.\n"
            "A crash in one tab may close ALL tabs. Requires restart."
        ))
        perf_layout.addWidget(self.chk_low_mem)
        grp_perf.setLayout(perf_layout)
        layout.addWidget(grp_perf)

        grp_clear = QGroupBox(_("Clear Data"))
        clear_layout = QVBoxLayout()
        self.chk_history = QCheckBox(_("Clear History"))
        self.chk_cache = QCheckBox(_("Clear Cache"))
        self.chk_cookies = QCheckBox(_("Clear Cookies"))
        btn_clear = QPushButton(_("Clear Now"))
        btn_clear.clicked.connect(self._clear_data)
        clear_layout.addWidget(self.chk_history)
        clear_layout.addWidget(self.chk_cache)
        clear_layout.addWidget(self.chk_cookies)
        clear_layout.addWidget(btn_clear)
        grp_clear.setLayout(clear_layout)
        layout.addWidget(grp_clear)

        layout.addStretch()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save_settings)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_settings(self):
        s = QSettings(APP_NAME, APP_NAME)
        self.home_edit.setText(s.value("homepage", DEFAULT_HOME))
        engine_names = {"Google": 0, "Bing": 1, "DuckDuckGo": 2, "Baidu": 3}
        current = s.value("search/engine_name", "Google")
        self.search_engine_combo.setCurrentIndex(engine_names.get(current, 0))
        try:
            with open(CONF_FILE, "r") as f:
                cfg = json.load(f)
                self.chk_low_mem.setChecked(cfg.get("low_memory_mode", False))
        except Exception:
            self.chk_low_mem.setChecked(False)
        if s.value("proxy/enabled", "false") == "true":
            self.proxy_type.setCurrentText(s.value("proxy/type", "HTTP"))
            self.proxy_host.setText(s.value("proxy/host", ""))
            self.proxy_port.setValue(int(s.value("proxy/port", "1080")))

    def _save_settings(self):
        s = QSettings(APP_NAME, APP_NAME)
        s.setValue("homepage", self.home_edit.text().strip())

        search_map = {
            "Google": "https://www.google.com/search?q={query}",
            "Bing": "https://www.bing.com/search?q={query}",
            "DuckDuckGo": "https://duckduckgo.com/?q={query}",
            "Baidu": "https://www.baidu.com/s?wd={query}",
        }
        engine_name = self.search_engine_combo.currentText()
        s.setValue("search/engine_name", engine_name)
        s.setValue("search/url", search_map.get(engine_name, "https://www.google.com/search?q={query}"))

        # ── 低内存模式 ──
        low_mem = self.chk_low_mem.isChecked()
        try:
            with open(CONF_FILE, "r") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        changed = cfg.get("low_memory_mode", False) != low_mem
        cfg["low_memory_mode"] = low_mem
        with open(CONF_FILE, "w") as f:
            json.dump(cfg, f)
        if changed and low_mem:
            QMessageBox.warning(
                self, _("Restart Required"),
                _("Low Memory Mode reduces memory usage by running all "
                  "components in a single process.\n\n"
                  "⚠ A crash in any tab will close ALL tabs.\n\n"
                  "This change will take effect after restarting the browser.")
            )

        ptype = self.proxy_type.currentText()
        if ptype == _("None"):
            s.setValue("proxy/enabled", "false")
            QNetworkProxy.setApplicationProxy(QNetworkProxy())
        else:
            s.setValue("proxy/enabled", "true")
            s.setValue("proxy/type", ptype)
            s.setValue("proxy/host", self.proxy_host.text().strip())
            s.setValue("proxy/port", str(self.proxy_port.value()))
            host = self.proxy_host.text().strip()
            port = self.proxy_port.value()
            if host:
                proxy_cls = QNetworkProxy.ProxyType.HttpProxy if ptype == _("HTTP") else QNetworkProxy.ProxyType.Socks5Proxy
                QNetworkProxy.setApplicationProxy(QNetworkProxy(proxy_cls, host, port))
        self.accept()

    def _clear_data(self):
        browser = self.parent_browser
        if not browser:
            return
        if self.chk_history.isChecked():
            browser.history_manager.clear()
        if self.chk_cache.isChecked():
            browser.default_profile.clearHttpCache()
            if os.path.exists(CACHE_DIR):
                shutil.rmtree(CACHE_DIR)
                os.makedirs(CACHE_DIR, exist_ok=True)
        if self.chk_cookies.isChecked():
            browser.default_profile.cookieStore().deleteAllCookies()
            cpath = os.path.join(COOKIE_DIR, "Cookies")
            if os.path.exists(cpath):
                os.remove(cpath)
        QMessageBox.information(self, _("Done"), _("Selected data cleared."))


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("About"))
        self.resize(360, 200)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<h2>{APP_NAME}</h2>"))
        layout.addWidget(QLabel(_("Version {}")).format(APP_VERSION))
        layout.addWidget(QLabel(_("Built with PyQt6 + QtWebEngine")))
        layout.addWidget(QLabel(_("Supports tabs, history, bookmarks, cookies, cache")))
        layout.addStretch()
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)


class DownloadItemWidget(QWidget):
    """A single download item with progress bar."""

    def __init__(self, download: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self.label = QLabel(os.path.basename(download.path()))
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(200)
        self.status_label = QLabel("0%")
        self.status_label.setFixedWidth(40)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        download.downloadProgress.connect(self._update_progress)
        download.finished.connect(self._on_finished)

    def _update_progress(self, received: int, total: int):
        if total > 0:
            pct = int(received * 100 / total)
            self.progress.setValue(pct)
            self.status_label.setText(f"{pct}%")
        else:
            self.progress.setRange(0, 0)

    def _on_finished(self):
        self.progress.setValue(100)
        self.status_label.setText(_("Done"))


class DownloadManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Downloads"))
        self.resize(600, 350)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)
        btn_close = QPushButton(_("Close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def add_download(self, download: QWebEngineDownloadRequest):
        item = QListWidgetItem()
        widget = DownloadItemWidget(download)
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)


class MainBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        self.history_manager = HistoryManager(HISTORY_DB)
        self.bookmark_manager = BookmarkManager(BOOKMARKS_FILE)

        self.default_profile = QWebEngineProfile("MiniBrowserProfile", self)
        self.default_profile.setHttpUserAgent(f"mini-browser/{APP_VERSION}")
        self.default_profile.setPersistentStoragePath(COOKIE_DIR)
        self.default_profile.setCachePath(CACHE_DIR)
        self.default_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        self.default_profile.setHttpCacheMaximumSize(50 * 1024 * 1024)  # 限制缓存 50 MB
        self.default_profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.default_profile.downloadRequested.connect(self._on_download_requested)
        self._apply_memory_optimizations()

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

        self.statusBar().showMessage(_("Ready"))

        self.download_manager = DownloadManager(self)

        self._build_menu()
        self._build_toolbar()
        self._load_settings()
        self._add_new_tab(QUrl(self.homepage))
        self._apply_dark_theme()

    def _apply_memory_optimizations(self):
        """精简 Chromium 配置（仅禁用安全无害的功能）。"""
        s = self.default_profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.HyperlinkAuditingEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, False)

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu(_("&File"))
        act = QAction(_("New Tab\tCtrl+T"), self)
        act.setShortcut(QKeySequence("Ctrl+T"))
        act.triggered.connect(lambda: self._add_new_tab(QUrl(self.homepage)))
        file_menu.addAction(act)

        act = QAction(_("New Window\tCtrl+N"), self)
        act.setShortcut(QKeySequence("Ctrl+N"))
        act.triggered.connect(self._new_window)
        file_menu.addAction(act)

        file_menu.addSeparator()
        act = QAction(_("Save Page As\u2026\tCtrl+S"), self)
        act.setShortcut(QKeySequence("Ctrl+S"))
        act.triggered.connect(self._save_page)
        file_menu.addAction(act)

        file_menu.addSeparator()
        act = QAction(_("Print\u2026\tCtrl+P"), self)
        act.setShortcut(QKeySequence("Ctrl+P"))
        act.triggered.connect(self._print_page)
        file_menu.addAction(act)

        file_menu.addSeparator()
        act = QAction(_("Quit\tCtrl+Q"), self)
        act.setShortcut(QKeySequence("Ctrl+Q"))
        act.triggered.connect(self.close)
        file_menu.addAction(act)

        hist_menu = menubar.addMenu(_("&History"))
        act = QAction(_("Show History\tCtrl+H"), self)
        act.setShortcut(QKeySequence("Ctrl+H"))
        act.triggered.connect(self._show_history)
        hist_menu.addAction(act)

        act = QAction(_("Clear History"), self)
        act.triggered.connect(self._clear_history)
        hist_menu.addAction(act)

        bm_menu = menubar.addMenu(_("&Bookmarks"))
        act = QAction(_("Manage Bookmarks\tCtrl+B"), self)
        act.setShortcut(QKeySequence("Ctrl+B"))
        act.triggered.connect(self._show_bookmarks)
        bm_menu.addAction(act)

        act = QAction(_("Add Current Page\tCtrl+D"), self)
        act.setShortcut(QKeySequence("Ctrl+D"))
        act.triggered.connect(self._add_current_bookmark)
        bm_menu.addAction(act)

        tools_menu = menubar.addMenu(_("&Tools"))
        act = QAction(_("Downloads\tCtrl+J"), self)
        act.setShortcut(QKeySequence("Ctrl+J"))
        act.triggered.connect(self.download_manager.show)
        tools_menu.addAction(act)

        act = QAction(_("Settings\tCtrl+,"), self)
        act.setShortcut(QKeySequence("Ctrl+,"))
        act.triggered.connect(self._show_settings)
        tools_menu.addAction(act)

        dev_menu = menubar.addMenu(_("&Developer"))
        act = QAction(_("Inspect Element\tF12"), self)
        act.setShortcut(QKeySequence("F12"))
        act.triggered.connect(self._toggle_inspector)
        dev_menu.addAction(act)

        help_menu = menubar.addMenu(_("&Help"))
        act = QAction(_("About"), self)
        act.triggered.connect(lambda: AboutDialog(self).exec())
        help_menu.addAction(act)

    def _build_toolbar(self):
        toolbar = QToolBar(_("Navigation"), self)
        toolbar.setObjectName("mainToolBar")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        act = QAction("\U00002795", self)
        act.setToolTip(_("New Tab"))
        act.triggered.connect(lambda: self._add_new_tab(QUrl(self.homepage)))
        toolbar.addAction(act)

        act = QAction("\U0001F3E0", self)
        act.setToolTip(_("Home"))
        act.triggered.connect(self._go_home)
        toolbar.addAction(act)

        toolbar.addSeparator()

        act = QAction("\U0001F4CB", self)
        act.setToolTip(_("History"))
        act.triggered.connect(self._show_history)
        toolbar.addAction(act)

        act = QAction("\u2B50", self)
        act.setToolTip(_("Bookmarks"))
        act.triggered.connect(self._show_bookmarks)
        toolbar.addAction(act)

        toolbar.addSeparator()

        act = QAction("\u2B07", self)
        act.setToolTip(_("Downloads"))
        act.triggered.connect(self.download_manager.show)
        toolbar.addAction(act)

    def _add_new_tab(self, url: QUrl, background: bool = False):
        tab = BrowserTab(self.default_profile, self)
        idx = self.tabs.addTab(tab, _("New Tab"))
        if not background:
            self.tabs.setCurrentIndex(idx)
            tab.navigate(url)
        else:
            tab._lazy_url = url  # 后台标签延迟加载
        return tab

    def open_url_in_new_tab(self, url: str):
        self._add_new_tab(QUrl(url))

    def _close_tab(self, idx: int):
        if self.tabs.count() <= 1:
            return
        widget = self.tabs.widget(idx)
        self.tabs.removeTab(idx)
        if widget:
            widget.web_view.stop()
            widget.web_page.setDevToolsPage(None)
            widget.web_view.setPage(None)
            widget.deleteLater()
        gc.collect()

    def _on_tab_changed(self, idx: int):
        tab = self.tabs.widget(idx)
        if tab and hasattr(tab, '_lazy_url') and tab._lazy_url is not None:
            url = tab._lazy_url
            tab._lazy_url = None
            tab.navigate(url)

    def current_tab(self) -> BrowserTab | None:
        return self.tabs.currentWidget()

    def _go_home(self):
        tab = self.current_tab()
        if tab:
            tab.navigate(QUrl(self.homepage))

    def _new_window(self):
        subprocess.Popen([sys.executable, __file__])

    def _save_page(self):
        tab = self.current_tab()
        if not tab:
            return
        path, _ = QFileDialog.getSaveFileName(self, _("Save Page"), "", _("HTML (*.html);;All Files (*)"))
        if path:
            def callback(html: str):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
            tab.web_view.page().toHtml(callback)

    def _print_page(self):
        tab = self.current_tab()
        if tab:
            tab.web_view.page().printToPdf("")

    def _toggle_inspector(self):
        tab = self.current_tab()
        if tab:
            if hasattr(tab, '_devtools_window') and tab._devtools_window is not None:
                tab._devtools_window.close()
                tab._devtools_window = None
                tab.web_page.setDevToolsPage(None)
            else:
                dev_win = QMainWindow(self)
                dev_win.setWindowTitle(_("DevTools \u2014 ") + (tab.current_title() or _("Untitled")))
                dev_win.resize(800, 600)
                dev_view = QWebEngineView()
                dev_page = QWebEnginePage(self.default_profile, dev_view)
                dev_view.setPage(dev_page)
                tab.web_page.setDevToolsPage(dev_page)
                dev_win.setCentralWidget(dev_view)
                dev_win.show()
                tab._devtools_window = dev_win

    def _show_history(self):
        HistoryDialog(self.history_manager, self).exec()

    def _clear_history(self):
        reply = QMessageBox.question(
            self, _("Confirm"), _("Clear all history?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.clear()
            self.statusBar().showMessage(_("History cleared"), 3000)

    def _show_bookmarks(self):
        BookmarkDialog(self.bookmark_manager, self).exec()

    def _add_current_bookmark(self):
        tab = self.current_tab()
        if tab:
            self.bookmark_manager.add(tab.current_url(), tab.current_title())
            tab.btn_bookmark.setChecked(True)
            self.statusBar().showMessage(_("Bookmark added"), 2000)

    def _load_settings(self):
        s = QSettings(APP_NAME, APP_NAME)
        self.homepage = s.value("homepage", DEFAULT_HOME)
        self.search_url = s.value("search/url", "https://www.google.com/search?q={query}")

    def _show_settings(self):
        SettingsDialog(self).exec()
        self._load_settings()

    def _on_download_requested(self, download: QWebEngineDownloadRequest):
        path, _ = QFileDialog.getSaveFileName(
            self, _("Save File"), download.suggestedFileName(), _("All Files (*)")
        )
        if path:
            download.setPath(path)
            download.accept()
            self.download_manager.add_download(download)
            self.statusBar().showMessage(_("Downloading: {}").format(os.path.basename(path)), 3000)

    def _apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(55, 55, 55))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(60, 60, 60))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(70, 130, 180))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        QApplication.setPalette(palette)

        self.setStyleSheet("""
            QToolBar { background-color: #2b2b2b; border: none; padding: 4px; }
            QPushButton { background-color: #3c3c3c; color: #dcdcdc;
                          border: 1px solid #555; border-radius: 4px; padding: 4px 8px; }
            QPushButton:hover { background-color: #505050; }
            QPushButton:disabled { color: #666; }
            QLineEdit { background-color: #3c3c3c; color: #dcdcdc;
                        border: 1px solid #555; border-radius: 4px; padding: 4px 8px; }
            QTabWidget::pane { background-color: #2b2b2b; }
            QTabBar::tab { background-color: #2b2b2b; color: #aaa;
                           padding: 6px 12px; border: 1px solid #444;
                           border-bottom: none; border-top-left-radius: 4px;
                           border-top-right-radius: 4px; }
            QTabBar::tab:selected { background-color: #3c3c3c; color: #fff; }
            QStatusBar { background-color: #2b2b2b; color: #aaa; }
            QListWidget { background-color: #2b2b2b; color: #dcdcdc;
                          border: 1px solid #444; }
            QMenuBar { background-color: #2b2b2b; color: #dcdcdc; }
            QMenuBar::item:selected { background-color: #3c3c3c; }
            QMenu { background-color: #2b2b2b; color: #dcdcdc; border: 1px solid #444; }
            QMenu::item:selected { background-color: #3c3c3c; }
            QGroupBox { color: #dcdcdc; border: 1px solid #555;
                        border-radius: 4px; margin-top: 8px; padding-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QCheckBox { color: #dcdcdc; }
            QSpinBox { background-color: #3c3c3c; color: #dcdcdc;
                       border: 1px solid #555; border-radius: 4px; padding: 2px; }
            QComboBox { background-color: #3c3c3c; color: #dcdcdc;
                        border: 1px solid #555; border-radius: 4px; padding: 2px 6px; }
            QComboBox QAbstractItemView { background-color: #2b2b2b; color: #dcdcdc;
                                          selection-background-color: #3c3c3c; }
            QDialog { background-color: #2b2b2b; }
        """)

    def closeEvent(self, event):
        s = QSettings(APP_NAME, APP_NAME)
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/state", self.saveState())

        while self.tabs.count() > 0:
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if w:
                w.deleteLater()

        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("MiniBrowser")

    window = MainBrowser()
    s = QSettings(APP_NAME, APP_NAME)
    geo = s.value("window/geometry")
    state = s.value("window/state")
    if geo:
        window.restoreGeometry(geo)
    if state:
        window.restoreState(state)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
