<div align="center">

# 📸 Google Screen Translate

**Application for translating screenshots via Google Translate**

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

➡️ **[Join Discord](https://discord.gg/TSRFfRUwn)**

---

## 💝 Support the project

If you find this program useful, you can support its development:

➡️ **[Support the author](https://dalink.to/wolfgunt)**

Thank you for your support! ❤️

---

## Features

📸 **Window screenshot** — capture and translate the active window (F2)  
🖥️ **Area selection** — choose any area on the screen (F3)  
🌍 **Translation via Google Translate** — using the "Images" tab  
🖼️ **Overlay with result** — display translated image over the original  
📋 **Hotkeys** — fully customizable hotkeys in settings (Hotkeys tab)  
🗑️ **Overlay removal** — remove all overlays (F4) or remove a specific overlay under the cursor (ESC in edit mode)  
✏️ **Edit mode** — move and remove overlays (F5)  
🌐 **Multiple languages** — support for 100+ languages  
⚙️ **Configurable browser** — browser selection (automatic search or manual path) with "Find Browsers" button  
🔍 **Browser search** — automatic system scan for Yandex Browser and Google Chrome  
🔒 **Security** — minimal permissions, no external requests  
🌍 **Bilingual interface** — support for Russian and English

---

## ⚠️ Important: Administrator Rights

### The Problem
If the application you want to translate is **running with administrator rights** (for example, a game, code editor, or system utility), then the **Google Screen Translate hotkeys WILL NOT WORK** if the program itself is running without administrator privileges.

### The Reason
Windows blocks global hotkey interception from applications with standard privileges if the target window belongs to an application with elevated rights. This is a security measure.

### The Solution
**Run Google Screen Translate with administrator rights.**

**How to do it:**

1. **Via context menu:**
   - Right-click on the `GoogleScreenTranslate.exe` file
   - Select **"Run as administrator"**

2. **Via shortcut properties (for permanent launch):**
   - Right-click on the program shortcut
   - Select **"Properties"**
   - Go to the **"Compatibility"** tab
   - Check **"Run this program as an administrator"**
   - Click **"Apply"** and **"OK"**

3. **Via command line:**
   ```cmd
   runas /user:Administrator "P:\Users\Alexey\Desktop\GoogleScreenTranslate\GoogleScreenTranslate.exe"
   ```

> **💡 Tip:** If you frequently use the program to translate windows of applications running with administrator rights,
configure the shortcut to always run with administrator privileges (method 2).

---

## 🎮 Usage

### Default Hotkeys

| Action | Hotkey |
|--------|--------|
| Window screenshot and translate | `F2` |
| Select area on screen | `F3` |
| Show/hide overlay | `F1` |
| Clear all overlays | `F4` |
| Edit mode | `F5` |
| Remove overlay under cursor | `ESC` (in edit mode) |

> **💡 All hotkeys can be reassigned in the settings window (Hotkeys tab)**

### Features Overview

- **F2 (window screenshot)** — takes a screenshot of the active window, removes all old overlays, and shows the
  translation result
- **F3 (area selection)** — takes a screenshot of the entire screen, allows you to select any area with the mouse (old
  overlays remain visible)
- **F4 (clear all)** — instantly removes all overlays from the screen
- **F5 (edit mode)** — toggles edit mode, allowing you to drag overlays with the mouse and remove them with ESC
- **ESC** — in edit mode removes the overlay under the cursor; in normal mode hides all overlays

### Main Window

| Element | Description |
|---------|-------------|
| Button "Take screenshot (F2)" | Capture and translate the active window |
| Button "Clear all (F4)" | Remove all overlays |
| Button "Show/Hide (F1)" | Toggle overlay visibility |
| Button "Edit mode (F5)" | Toggle edit mode |
| Target language selection | Language to translate the text into |
| Button "⚙️" | Open settings |
| Button "RU/EN" | Switch interface language |

---

## 🔧 Program Settings

All settings are available in the settings window (opens via menu or by clicking ⚙️ in the main window).

### 🌐 Browser

- **Browser path** — manually specify the path to the browser executable
- **Automatic search** — the program will find Yandex Browser or Google Chrome
- **"Find Browsers" button** — scans the system for browsers and shows a list to choose from
- **Recommended** — Yandex Browser for better compatibility

### 🎨 Interface

- **Show translation indicator** — display progress during translation
- **Auto-hide overlay** — automatically hide when switching to another window
- **Fullscreen → windowed fullscreen** — automatic conversion when capturing area (F3)
- **Edit mode** — allow moving and removing overlays

### ⌨️ Hotkeys (NEW TAB)

- **Reassign hotkeys** — click the button with the key, then press a new key
- **Automatic key swapping** — if a key is already taken, it automatically swaps with the current assignment
- Available actions to customize:
    - Window screenshot
    - Area selection
    - Show/Hide overlay
    - Clear all overlays
    - Edit mode

### 🌍 Language

- **Русский** — interface in Russian
- **English** — interface in English

### Target Translation Language

- Selection from 100+ languages
- Supports all Google Translate languages
- Search by language name

---

## ⚙️ Requirements

### Browser

The program requires one of the following browsers:

- **Yandex Browser** (recommended)
- **Google Chrome**
- **Chromium**
- **Brave** or **Vivaldi** (alternatives)

If the browser is not found automatically, the program will prompt you to specify the path manually or use the "Find
Browsers" button.

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

---

## 🐛 Debug Mode

For troubleshooting, you can run the program with the `--debug` parameter:

```cmd
GoogleScreenTranslate.exe --debug
```

or via shortcut (add `--debug` to the end of the "Target" field in shortcut properties).

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

- [Playwright](https://playwright.dev/) — browser automation
- [Pillow](https://python-pillow.org/) — image processing
- [tkinter](https://docs.python.org/3/library/tkinter.html) — graphical interface
- [Google Translate](https://translate.google.com/) — image translation
- [DXcam](https://github.com/ra1nty/DXcam) — screen capture for games
- [keyboard](https://github.com/boppreh/keyboard) — global hotkeys

---