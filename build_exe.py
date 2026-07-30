# build_exe.py
import os
import sys
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw


def create_icon():
    """Создает файл иконки .ico"""
    print("🎨 Создание иконки...")

    size = 256
    img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_color = (33, 33, 33, 255)
    accent_color = (76, 175, 80, 255)
    white = (255, 255, 255, 255)
    radius = 30

    draw.rounded_rectangle(
        [(8, 8), (size - 8, size - 8)],
        radius=radius,
        fill=bg_color,
        outline=accent_color,
        width=4
    )

    center_x = size // 2
    center_y = size // 2 + 4

    cam_w = 120
    cam_h = 88
    x1 = center_x - cam_w // 2
    y1 = center_y - cam_h // 2
    x2 = center_x + cam_w // 2
    y2 = center_y + cam_h // 2

    draw.rounded_rectangle(
        [(x1, y1), (x2, y2)],
        radius=8,
        fill=white,
        outline=accent_color,
        width=4
    )

    lens_radius = 32
    draw.ellipse(
        [(center_x - lens_radius, center_y - lens_radius),
         (center_x + lens_radius, center_y + lens_radius)],
        fill=accent_color,
        outline=white,
        width=4
    )

    draw.ellipse(
        [(center_x - 16, center_y - 20),
         (center_x - 4, center_y - 8)],
        fill=white
    )

    flash_x = center_x + 48
    flash_y = center_y - cam_h // 2 - 8
    draw.rectangle(
        [(flash_x - 8, flash_y - 8),
         (flash_x + 12, flash_y + 12)],
        fill=white,
        outline=accent_color,
        width=2
    )

    text_y = y2 + 24
    draw.rounded_rectangle(
        [(center_x - 48, text_y - 4),
         (center_x + 48, text_y + 36)],
        radius=6,
        fill=accent_color
    )

    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 32)
        draw.text(
            (center_x - 28, text_y + 4),
            "SC",
            fill=white,
            font=font
        )
    except:
        draw.text(
            (center_x - 24, text_y + 4),
            "SC",
            fill=white
        )

    img.save("app_icon.ico", format='ICO', sizes=[(256, 256)])
    print("✅ Иконка создана: app_icon.ico")
    return "app_icon.ico"


def build_exe():
    """Компилирует приложение в папку с файлами (быстрый запуск) с показом процесса"""
    print("🔨 Компиляция приложения (режим папки)...")
    print("=" * 60)

    icon_path = create_icon()

    try:
        import PyInstaller
    except ImportError:
        print("❌ PyInstaller не установлен! Установите: pip install pyinstaller")
        return False

    # Формируем команду
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--windowed",
        f"--icon={icon_path}",
        "--name=ScreenTranslator",
        "--clean",
        "--noconfirm",
        "main.py"
    ]

    print(f"📦 Команда: {' '.join(cmd)}")
    print("=" * 60)
    print("⏳ Начинается компиляция... (вывод будет показываться в реальном времени)")
    print("-" * 60)

    try:
        # Используем Popen для потокового вывода
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Объединяем stdout и stderr
            text=True,
            bufsize=1,  # Построчный буфер
            universal_newlines=True
        )

        # Читаем и выводим строки по мере поступления
        for line in process.stdout:
            print(line, end='')  # Выводим каждую строку сразу

        # Ждем завершения процесса
        return_code = process.wait()

        print("-" * 60)

        if return_code == 0:
            print("✅ Компиляция завершена успешно!")
            print(f"📁 Папка создана: dist/ScreenTranslator/")
            print(f"📁 Файл: dist/ScreenTranslator/ScreenTranslator.exe (с иконкой)")
            print("⚡ Запуск БЫСТРЫЙ, без распаковки при каждом старте!")
            return True
        else:
            print(f"❌ Ошибка компиляции! Код возврата: {return_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Сборка ScreenTranslator (БЫСТРЫЙ запуск)")
    print("=" * 60)
    build_exe()