# MiniBrowser 迷你浏览器

一款使用 **PyQt6 + QtWebEngine** 构建的小型但功能完整的网页浏览器。轻量、可换肤、对开发者友好。

---

## ✨ 功能特性

| 类别 | 功能 |
|------|------|
| 📑 **标签页** | 多标签浏览、拖拽重排、后台标签延迟加载 |
| 📜 **历史记录** | SQLite 持久化存储、关键词搜索、单条/全部清除 |
| ⭐ **书签** | JSON 文件持久化、添加/删除/自动去重、快速访问 |
| 📥 **下载管理** | 下载管理器，实时进度条显示 |
| 🔍 **搜索** | Google / Bing / DuckDuckGo / Baidu — 地址栏自动识别搜索 |
| 🌐 **代理** | 支持 HTTP 和 SOCKS5 代理，设置界面中配置 |
| 🌙 **主题** | 内置深色主题，完整的调色板和样式表 |
| 🛠 **开发者工具** | F12 打开 Chromium DevTools 独立窗口 |
| 🌍 **国际化** | 基于 gettext 的多语言支持（已含简体中文） |
| 🚀 **性能优化** | 低内存模式（单进程）、Chromium 标志精简、缓存上限 50 MB |
| 🖨 **打印** | 页面另存为 HTML、打印为 PDF |

---

## 📦 安装

### Debian / Ubuntu

```bash
sudo dpkg -i mini-browser_1.0.0-1_all.deb
sudo apt install -f   # 安装缺失的依赖
```

### 运行依赖

- **Python** 3.10+
- **PyQt6**
- **PyQt6-WebEngine**

```bash
pip install PyQt6 PyQt6-WebEngine
```

### 源码运行

```bash
git clone https://github.com/gbfdhenr/mini-browser
cd mini-browser
python3 mini-browser.py
```

---

## 🚀 使用方法

```bash
mini-browser                         # 以默认主页启动
mini-browser https://example.org     # 打开指定网址
```

### ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+T` | 新建标签页 |
| `Ctrl+N` | 新建窗口 |
| `Ctrl+S` | 页面另存为 HTML |
| `Ctrl+P` | 打印为 PDF |
| `Ctrl+H` | 显示历史记录 |
| `Ctrl+B` | 管理书签 |
| `Ctrl+D` | 添加当前页面到书签 |
| `Ctrl+J` | 打开下载管理器 |
| `Ctrl+,` | 打开设置 |
| `F12` | 切换开发者工具 |
| `Ctrl+Q` | 退出 |

---

## 🌍 国际化

设置 `LANG` 环境变量即可切换语言：

```bash
LANG=zh_CN.UTF-8 mini-browser   # 简体中文
LANG=de_DE.UTF-8 mini-browser   # 德语
```

若要添加新语言，在 `locale/<语言代码>/LC_MESSAGES/` 下创建 `.po` 文件并编译：

```bash
msgfmt -o locale/<语言代码>/LC_MESSAGES/mini-browser.mo \
          locale/<语言代码>/LC_MESSAGES/mini-browser.po
```

---

## 🏗 项目结构

```
mini-browser/
├── mini-browser.py                 # 主程序（约 41 KB）
├── README.md                       # 英文说明
├── README_zh.md                    # 中文说明
├── locale/                         # 翻译文件
│   └── zh_CN/LC_MESSAGES/
│       ├── mini-browser.po         # 简体中文翻译源文件
│       └── mini-browser.mo         # 编译后翻译文件
├── debian/                         # Debian 打包目录
│   ├── main.py, README.md          # 上游副本
│   ├── tools/update-translations.py
│   ├── locale/                     # 打包用的翻译
│   ├── usr/                        # 图标文件
│   └── debian/                     # dpkg 构建元数据
│       ├── control, changelog, copyright
│       ├── rules, source/format
│       ├── mini-browser.desktop    # 桌面入口文件
│       └── mini-browser.1          # 手册页
└── .gitignore
```

---

## 🧠 代码架构

代码按照单一职责原则划分为清晰的类：

| 类 | 职责 |
|----|------|
| `HistoryManager` | SQLite 驱动的浏览历史（增删改查、搜索） |
| `BookmarkManager` | JSON 文件驱动的书签管理（增删改查、去重） |
| `BrowserTab` | 单个标签页：地址栏、导航按钮、`QWebEngineView` |
| `MainBrowser` | 主窗口：菜单栏、工具栏、`QTabWidget`、设置加载 |
| `SettingsDialog` | 设置 UI（主页、代理、搜索引擎、低内存模式、清理数据） |
| `DownloadManager` | 下载管理对话框，使用 `QListWidget` 显示 |
| `DownloadItemWidget` | 单个下载项，带 `QProgressBar` 进度条 |
| `HistoryDialog` | 历史记录查看器，支持搜索和清除 |
| `BookmarkDialog` | 书签管理器，支持打开和删除 |
| `AboutDialog` | 版本和版权信息 |

### Chromium 优化标志

MiniBrowser 应用了一组精选的 Chromium 命令行标志以降低内存占用：

- `--disable-gpu` — 节省约 150 MB GPU 进程内存
- `--process-per-site` — 同站点标签共享渲染进程
- `--disable-background-networking`、`--disable-sync`、`--disable-breakpad` — 移除后台服务
- `--max_old_space_size=256` — V8 堆上限 256 MB

### 低内存模式

在「设置 → 性能」中可启用**低内存模式**（单进程模式）。此模式会加上 `--single-process` 标志，进一步减少内存占用，但代价是一个标签页崩溃会导致所有标签页关闭。修改后需要重启浏览器生效。

---

## 🔧 构建 Debian 包

```bash
cd debian
dpkg-buildpackage -us -uc -b
```

---

## 📄 许可证

AGPL-3.0-or-later © LiangXiangan
