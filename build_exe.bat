@echo off

chcp 65001 >nul

title Сборка GoogleScreenTranslate



echo ========================================

echo   СБОРКА GOOGLE SCREEN TRANSLATE

echo ========================================

echo.



echo Очистка старых сборок...

rmdir /s /q build 2>nul

rmdir /s /q dist 2>nul

del /q *.spec 2>nul



echo Очистка кэша...

rmdir /s /q __pycache__ 2>nul

rmdir /s /q src\__pycache__ 2>nul



echo Сборка исполняемого файла...

pyinstaller --onefile --windowed --name="GoogleScreenTranslate" --add-data "src;src" --hidden-import=encodings --hidden-import=codecs --hidden-import=locale --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=PIL.ImageTk --hidden-import=PIL.ImageGrab --hidden-import=keyboard --hidden-import=win32gui --hidden-import=win32ui --hidden-import=win32con --hidden-import=win32api --hidden-import=pywintypes --hidden-import=playwright --hidden-import=playwright.sync_api --hidden-import=logging --hidden-import=threading --hidden-import=tempfile --hidden-import=pathlib --hidden-import=datetime --hidden-import=time --hidden-import=json --hidden-import=winreg --hidden-import=subprocess --hidden-import=dxcam --hidden-import=numpy --hidden-import=ctypes --collect-all encodings --collect-all PIL --collect-all tkinter --collect-all playwright --collect-all keyboard --collect-all dxcam --collect-all numpy --clean --noconfirm --runtime-tmpdir="%TEMP%" main.py



echo.

echo ========================================

echo   СБОРКА ЗАВЕРШЕНА

echo ========================================

echo.

echo Исполняемый файл: dist\GoogleScreenTranslate.exe

echo.



pause