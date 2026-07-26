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



📸 **Window screenshot** — capture and translate the active window (F2)  

🖥️ **Area selection** — choose any area on the screen (F3)  

🌍 **Translation via Google Translate** — using the "Images" tab  

🖼️ **Overlay with result** — display translated image over the original  

📋 **Hotkeys** — mouse-free control  

🗑️ **Clear all overlays** — quickly remove all translations from the screen (F4)  

🌐 **Multiple languages** — support for 100+ languages  

⚙️ **Configurable browser** — browser selection, manual path  

🔒 **Security** — minimal permissions, no external requests



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

### Hotkeys

| Action | Hotkey |

|--------|--------|

| Window screenshot and translate | `F2` |

| Select area on screen | `F3` |

| Show/hide overlay | `F1` |

| Clear all overlays | `F4` |

| Close overlay (ESC) | `ESC` |

### Features Overview

- **F2 (window screenshot)** — takes a screenshot of the active window, removes all old overlays, and shows the
  translation result

- **F3 (area selection)** — takes a screenshot of the entire screen, allows you to select any area with the mouse (old
  overlays remain visible)

- **F4 (clear all)** — instantly removes all overlays from the screen

- **ESC** — hides all overlays (works globally)

### Main Steps

1. **Launch the program** — the main window will open

2. **Choose capture method:**

    - Press `F2` to translate the active window

    - Press `F3` to select an area on the screen

3. **View the result** — the translated image will appear over the original

4. **Press `ESC` or `F4`** — to hide or remove overlays

### Main Window

| Element | Description |

|---------|-------------|

| Button "Take screenshot (F2)" | Capture and translate the active window |

| Button "Select area (F3)" | Capture an area on the screen |

| Button "Show/Hide (F1)" | Toggle overlay visibility |

| Button "Clear all (F4)" | Remove all overlays |

| Target language selection | Language to translate the text into |

| Checkbox "Show translation indicator" | Display translation progress |

| Checkbox "Auto-hide overlay" | Automatically hide when switching windows |

| Menu "File" → "Open App Folder" | Opens the folder with settings and logs |



---

## 📂 Data storage structure

On first launch, the program creates the following structure in the `Documents/GoogleScreenTranslate` folder:

```



Documents/GoogleScreenTranslate/

├── config/

│ ├── settings.json # Program settings

│ └── overlay_positions.json # Saved overlay positions

├── logs/

│ └── app_*.log # Log files (only 5 most recent launches are kept)

└── temp/ # Temporary screenshot files



```

**Important:**

- Settings are saved automatically when the program closes

- Overlay positions are saved between sessions

- Log files are automatically cleaned up, only the 5 most recent are kept

- Temporary files are deleted when the program exits

---

## 🔧 Program Settings

All settings are available in the settings window (opens via menu or by clicking ⚙️ in the main window):

### 🌐 Browser

- **Browser path** — manually specify the path to the browser executable

- **Automatic search** — the program will find Yandex Browser or Google Chrome

- **Recommended** — Yandex Browser for better compatibility

### 🎨 Interface

- **Show translation indicator** — display progress during translation

- **Auto-hide overlay** — automatically hide when switching to another window

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