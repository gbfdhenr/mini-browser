# MiniBrowser

A small but full-featured web browser built with **PyQt6 + QtWebEngine**. Lightweight, themable, and developer-friendly.
[（中文文档）](READE_zh.md)
---

## ✨ Features

| Category       | Features |
|----------------|----------|
| 📑 **Tabs**    | Multi-tab browsing, drag-and-drop reorder, lazy loading for background tabs |
| 📜 **History** | SQLite-backed persistent history, keyword search, clear single or all entries |
| ⭐ **Bookmarks** | JSON-based storage, add/remove/deduplicate, quick access |
| 📥 **Downloads** | Download manager with real-time progress bars |
| 🔍 **Search**  | Google / Bing / DuckDuckGo / Baidu — auto-detection from address bar |
| 🌐 **Proxy**   | HTTP & SOCKS5 proxy support, configurable from settings |
| 🌙 **Theme**   | Built-in dark theme with full palette and stylesheet |
| 🛠 **DevTools** | F12 to open Chromium DevTools in a detached window |
| 🌍 **i18n**    | gettext-based multi-language (Chinese included) |
| 🚀 **Performance** | Low-memory mode (single process), Chromium flags optimization, 50 MB cache cap |
| 🖨 **Print**   | Save page as HTML, print to PDF |

---

## 📦 Installation

### Debian / Ubuntu

```bash
sudo dpkg -i mini-browser_1.0.0-1_all.deb
sudo apt install -f   # Install any missing dependencies
```

### Requirements

- **Python** 3.10+
- **PyQt6**
- **PyQt6-WebEngine**

```bash
pip install PyQt6 PyQt6-WebEngine
```

### From source

```bash
git clone https://github.com/gbfdhenr/mini-browser
cd mini-browser
python3 mini-browser.py
```

---

## 🚀 Usage

```bash
mini-browser                         # Launch with default homepage
mini-browser https://example.org     # Open a specific URL
```

### ⌨️ Keyboard Shortcuts

| Key       | Action |
|-----------|--------|
| `Ctrl+T`  | New tab |
| `Ctrl+N`  | New window |
| `Ctrl+S`  | Save page as HTML |
| `Ctrl+P`  | Print to PDF |
| `Ctrl+H`  | Show history |
| `Ctrl+B`  | Manage bookmarks |
| `Ctrl+D`  | Bookmark current page |
| `Ctrl+J`  | Open downloads |
| `Ctrl+,`  | Open settings |
| `F12`     | Toggle Developer Tools |
| `Ctrl+Q`  | Quit |

---

## 🌍 Internationalization

Set the `LANG` environment variable to switch languages:

```bash
LANG=zh_CN.UTF-8 mini-browser   # Chinese
LANG=de_DE.UTF-8 mini-browser   # German
```

To add a new language, create a `.po` file under `locale/<LANG>/LC_MESSAGES/` and compile it:

```bash
msgfmt -o locale/<LANG>/LC_MESSAGES/mini-browser.mo \
          locale/<LANG>/LC_MESSAGES/mini-browser.po
```

---

## 🏗 Project Structure

```
mini-browser/
├── mini-browser.py                 # Main application (~41 KB)
├── locale/                         # Translation files
│   └── zh_CN/LC_MESSAGES/
│       ├── mini-browser.po         # Chinese translation source
│       └── mini-browser.mo         # Compiled translation
├── debian/                         # Debian packaging
│   ├── main.py, README.md          # Upstream copies
│   ├── tools/update-translations.py
│   ├── locale/                     # Packaged translations
│   ├── usr/                        # Icons and pixmaps
│   └── debian/                     # dpkg build metadata
│       ├── control, changelog, copyright
│       ├── rules, source/format
│       ├── mini-browser.desktop    # Desktop entry
│       └── mini-browser.1          # Man page
└── .gitignore
```

---

## 🧠 Architecture

The codebase is organized into clean, single-responsibility classes:

| Class              | Responsibility |
|--------------------|----------------|
| `HistoryManager`   | SQLite-backed browsing history (CRUD, search) |
| `BookmarkManager`  | JSON-based bookmark storage (CRUD, dedup) |
| `BrowserTab`       | Single tab: address bar, navigation buttons, `QWebEngineView` |
| `MainBrowser`      | Main window: menus, toolbar, `QTabWidget`, settings loading |
| `SettingsDialog`   | Configuration UI (homepage, proxy, search engine, low-mem, clear data) |
| `DownloadManager`  | Download progress tracking with `QListWidget` |
| `DownloadItemWidget` | Individual download row with `QProgressBar` |
| `HistoryDialog`    | History viewer with search & clear |
| `BookmarkDialog`   | Bookmark manager with open/delete |
| `AboutDialog`      | Version & credits |

### Chromium Optimization Flags

MiniBrowser applies a carefully selected set of Chromium command-line flags to reduce memory footprint:

- `--disable-gpu` — saves ~150 MB GPU process
- `--process-per-site` — share renderer across same-site tabs
- `--disable-background-networking`, `--disable-sync`, `--disable-breakpad` — remove background services
- `--max_old_space_size=256` — V8 heap limit at 256 MB

---

## 🔧 Building Debian Package

```bash
cd debian
dpkg-buildpackage -us -uc -b
```

---

## 📄 License

MIT © LiangXiangan
