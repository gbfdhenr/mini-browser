# MiniBrowser

A small but full-featured web browser built with **PyQt6 + QtWebEngine**.

## Features

- Multi-tab browsing with drag-and-drop tab reordering
- Bookmarks and SQLite-backed history with search
- Download manager with progress tracking
- Proxy support (HTTP / SOCKS5)
- Dark theme
- Developer tools (F12)
- Multi-language support (gettext-based i18n)
- Configurable search engine (Google, Bing, DuckDuckGo, Baidu)

## Installation

### Debian / Ubuntu

```bash
sudo dpkg -i mini-browser_1.0.0_all.deb
sudo apt install -f   # Install any missing dependencies
```

### Requirements

- Python 3.10+
- PyQt6
- PyQt6-WebEngine

### From source

```bash
git clone https://github.com/LiangXiangan/mini-browser
cd mini-browser
python3 mini-browser.py
```

## Usage

```bash
mini-browser                   # Launch with homepage
mini-browser https://example.org  # Open a specific URL
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+T | New tab |
| Ctrl+N | New window |
| Ctrl+S | Save page |
| Ctrl+P | Print to PDF |
| Ctrl+H | Show history |
| Ctrl+B | Manage bookmarks |
| Ctrl+D | Add bookmark |
| Ctrl+J | Downloads |
| Ctrl+, | Settings |
| F12 | Developer tools |

## Internationalization

Set the `LANG` environment variable to switch languages:

```bash
LANG=zh_CN.UTF-8 mini-browser   # Chinese
LANG=de_DE.UTF-8 mini-browser   # German
```

## Building the package

```bash
cd mini-browser-1.0.0
dpkg-buildpackage -us -uc -b
```

## License

MIT
