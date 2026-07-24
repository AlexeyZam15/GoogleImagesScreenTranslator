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

## 💝 Support the project

If you find this program useful, you can support its development:

➡️ **[Support the author](https://dalink.to/wolfgunt)**

Thank you for your support! ❤️

---

## Features

📸 **Screenshot active window** — capture and translate any window on the screen  
🌍 **Translation via Google Translate** — using the "Images" tab  
🖼️ **Overlay with result** — display translated image over the original  
📋 **Hotkeys** — mouse-free control  
🌐 **Multiple languages** — support for 100+ languages  
⚙️ **Configurable browser** — browser selection, manual path  
🔒 **Security** — minimal permissions, no external requests

---

## 🎮 Usage

### Hotkeys

| Action | Hotkey |
|--------|--------|
| Take screenshot and translate | `F2` |
| Show/hide overlay | `F1` |
| Close overlay | `ESC` |

### Main Steps

1. **Launch the program** — the main window will open
2. **Activate the target window** — switch to the window you want to translate
3. **Press `F2`** — the program will take a screenshot and translate it
4. **View the result** — the translated image will appear over the original window
5. **Press `ESC`** — to close the overlay

### Main Window

| Element | Description |
|---------|-------------|
| Button "Take screenshot (F2)" | Capture and translate the active window |
| Button "Show/Hide (F1)" | Toggle overlay visibility |
| Target language selection | Language to translate the text into |
| Checkbox "Show translation indicator" | Display translation progress |
| Menu "File" → "Open App Folder" | Opens the folder with settings and logs |

---

## 📂 Data storage structure

On first launch, the program creates the following structure in the `Documents/GoogleScreenTranslate` folder:

```

Documents/GoogleScreenTranslate/
├── config/
│ └── settings.json # Program settings (language, target language, browser path, etc.)
├── logs/
│ └── app_*.log # Log files (only 5 most recent launches are kept)
└── temp/ # Temporary screenshot files

```

**Important:**

- Settings are saved automatically when the program closes
- Log files are automatically cleaned up, only the 5 most recent are kept
- Temporary files are deleted when the program exits

---

## 🔧 Program Settings

All settings are available in the settings window (opens via menu or by clicking ⚙️ in the main window):

### 🌐 Browser

- **Browser path** — manually specify the path to the browser executable
- **Automatic search** — the program will find Yandex Browser or Google Chrome
- **Recommended** — Yandex Browser for better compatibility

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

If the browser is not found automatically, the program will prompt you to specify the path manually.

### Installing dependencies (for developers)

```bash
pip install -r requirements.txt
playwright install chromium
```

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

---

<div align="center">

**⭐ Star this project if you find it useful!**

</div>