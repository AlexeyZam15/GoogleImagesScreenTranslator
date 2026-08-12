<div align="center">

# 📸 Google Screen Translate

**Application for translating screenshots via Google Translate or Yandex.Translator (OCR)**

[![Русский](https://img.shields.io/badge/Language-Russian-blue)](README.md)
[![English](https://img.shields.io/badge/Язык-Английский-red)](README.en.md)

</div>

---

## 📦 Download the ready-to-use program

**For Windows users** — a ready-made EXE file is available, no Python installation required:

➡️ **[Download the latest version](https://github.com/AlexeyZam15/GoogleImagesScreenTranslator/releases/latest)**

1. Go to the **Releases** section on GitHub
2. Download the `GoogleScreenTranslate.exe` file
3. Run the file — no installation required

---

## 💬 Join the Community

Discuss the project, ask questions, and share your experience in our Discord:

➡️ **[Join Discord](https://discord.gg/tAjZmzrPU7)**

---

## 💝 Support the project

If you find this program useful, you can support its development:

➡️ **[Support the author](https://dalink.to/wolfgunt)**

Thank you for your support! ❤️

---

## Features

### 📸 Screenshots and Translation
- **Window screenshot (F2)** — capture and translate the active window
- **Area selection (F3)** — choose any area on the screen for translation
- **Long press F3 (500ms)** — screenshot of the entire window + OCR recognition of all text zones and automatic overlay creation
- **Temporary translation (RMB in F3 mode)** — overlay is automatically removed after a specified time

### 🧠 Two Translation Engines
- **Google Translate** — translation via Google Images (requires stable internet)
- **Yandex.Translator (OCR)** — translation with text recognition on images

### 🔄 Automation
- **Auto-replace translated areas (F6)** — screen monitoring and automatic display of translation when the same area is detected
- **Translation queue** — select multiple areas in a row without waiting for the current translation to finish

### 🖼️ Overlay Management
- **Overlay with result** — display translated image over the original
- **Edit mode (F5)** — move overlays with the mouse and remove with ESC
- **Remove overlays (F4)** — remove all overlays or a specific one under the cursor

### ⚙️ Settings
- **Hotkeys** — fully customizable all combinations
- **Browser selection** — automatic search or manual path with "Find Browsers" button
- **Translation engine selection** — Google Translate or Yandex.Translator
- **100+ languages** — support for any translation language
- **Bilingual interface** — Russian and English

### 🔒 Security
- Minimal permissions, no external requests
- Version control — automatic cleanup of outdated files on update

---

## ⚠️ Important: Administrator Rights

### The Problem
If the application you want to translate is **running with administrator rights**, then the **Google Screen Translate hotkeys WILL NOT WORK** if the program itself is running without administrator privileges.

### The Reason
Windows blocks global hotkey interception from applications with standard privileges if the target window belongs to an application with elevated rights.

### The Solution
**Run Google Screen Translate with administrator rights.**

**How to do it:**
1. **Via context menu:** Right-click on `GoogleScreenTranslate.exe` → **"Run as administrator"**
2. **Via shortcut properties (permanent):** Right-click on shortcut → Properties → Compatibility → "Run this program as an administrator"
3. **Via command line:** `runas /user:Administrator "path\GoogleScreenTranslate.exe"`

---

## 🎮 Usage

### Default Hotkeys

| Action | Key | Description |
|--------|-----|-------------|
| **Window screenshot** | `F2` | Capture and translate the active window |
| **Area selection** | `F3` | Select area on screen for translation |
| **Long press F3** | `F3` (500ms) | OCR of entire window → all text zones are translated automatically |
| **Show/hide overlay** | `F1` | Toggle visibility of all overlays |
| **Clear all overlays** | `F4` | Remove all overlays from screen |
| **Edit mode** | `F5` | Toggle edit mode on/off |
| **Auto-replace** | `F6` | Toggle automatic area replacement on/off |

### 💡 Additional Features

| Action | Description |
|--------|-------------|
| **Temporary translation (RMB)** | In F3 mode, press RMB instead of LMB — overlay will be temporary and auto-removed |
| **Remove overlay under cursor** | In edit mode, press `ESC` over the overlay |
| **Translation queue** | Select multiple areas in a row without waiting for current translation to finish |
| **Drag overlays** | In edit mode, drag overlays with the mouse anywhere |

### Temporary Overlay Lifetime Configuration
Temporary overlay lifetime can be adjusted in **Settings → Interface → «Temporary overlay lifetime» slider** (from 10 to 600 seconds).

---

## 🔧 Program Settings

All settings are available in the settings window (opens via menu or by clicking ⚙️ in the main window).

### 🌐 Browser
- **Browser path** — manually specify the path to the browser executable
- **"Find Browsers" button** — scans the system for Yandex Browser, Google Chrome, and other Chromium browsers
- **Recommended** — Yandex Browser for better compatibility

### 🔤 Translation Engine (NEW!)
- **Google Translate** — standard translation via Google Images
- **Yandex.Translator (OCR)** — translation with text recognition on images
- Browser restarts automatically when changing the engine

### 🎨 Interface
- **Show translation indicator** — display progress during translation
- **Auto-hide overlay** — automatically hide when switching to another window
- **Auto-replace translated areas** — automatic detection and replacement of areas on screen
- **Fullscreen → windowed fullscreen** — automatic conversion when capturing area
- **Edit mode** — allow moving and removing overlays
- **Temporary overlay lifetime** — from 10 to 600 seconds

### ⌨️ Hotkeys
- **Reassign hotkeys** — click the button with the key, then press a new key
- **Automatic key swapping** — if a key is already taken, it swaps with the current assignment
- Available actions: screenshot, area, show/hide, clear all, edit mode, auto-replace

### 🔍 Monitor (for auto-replace)
- **Confidence threshold** — adjust detection sensitivity (0.5–1.0)
- **Scan interval** — screen check interval (0.1–2.0 sec)

---

## 🧠 How OCR of the entire window works (long press F3)

1. **Hold F3 for 500 ms** — program takes a screenshot of the entire window
2. **Translation via selected engine** — image is translated
3. **OCR recognition** — EasyOCR finds all text zones on the translated image
4. **Automatic overlay creation** — a separate overlay is created for each zone
5. **Add to monitor** — each overlay is added to the auto-replace system (F6)

> **Important:** OCR requires EasyOCR package to be installed. On first launch, it will download models (~500 MB).

---

## ⚙️ Requirements

### Browser
The program requires one of the following browsers:
- **Yandex Browser** (recommended)
- **Google Chrome**
- **Chromium**, **Brave**, **Vivaldi**, or **Edge**

If the browser is not found automatically, the program will prompt you to specify the path manually or use the "Find Browsers" button.

### OCR (for long press F3)
For the full window OCR feature, you need:
- **EasyOCR** — install via `pip install easyocr`
- On first launch, models are downloaded (~500 MB)

---

## 🛠️ Building from source

1. Clone the repository:
```bash
git clone https://github.com/AlexeyZam15/GoogleImagesScreenTranslator.git
cd GoogleImagesScreenTranslator
```

2. Install dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Run the build:

```bash
build_exe.bat
```

The built file will appear in the `dist/GoogleScreenTranslate.exe` folder

### Versioning

During build, the program checks the version in `version.txt`. If the version does not match the current one (
`APP_VERSION` in `version_checker.py`), the application folder in `Documents` is cleared to prevent conflicts.

---

## 🐛 Debug Mode

For troubleshooting, you can run the program with the `--debug` parameter:

```cmd
GoogleScreenTranslate.exe --debug
```

In debug mode:

- Browser will be shown (not hidden)
- Additional debug information is printed to the console
- Logging becomes more detailed

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is distributed under the MIT license. This means free use, modification, and distribution with attribution.

---

## 🙏 Acknowledgments

- Playwright — browser automation
- Pillow — image processing
- EasyOCR — text recognition
- tkinter — graphical interface
- Google Translate — image translation
- Yandex.Translator — OCR translation
- DXcam — screen capture for games
- keyboard — global hotkeys