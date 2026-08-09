"""
Сборка GoogleScreenTranslate в .exe (оптимизированная, с поддержкой OCR)

Запуск: python build_exe.py
"""

import PyInstaller.__main__
import os
import sys
import shutil
import warnings
from pathlib import Path

# ============================================================
# ПОДАВЛЕНИЕ ПРЕДУПРЕЖДЕНИЙ
# ============================================================
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# ============================================================
# ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ДЛЯ ПОДАВЛЕНИЯ ПРЕДУПРЕЖДЕНИЙ
# ============================================================
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TORCH_USE_CUDA_DSA'] = '1'

# ============================================================
# НАСТРОЙКИ
# ============================================================
APP_NAME = "GoogleScreenTranslate"
APP_ICON = "app_icon.ico"
OUTPUT_DIR = "dist"
BUILD_DIR = "build"

# Флаг: удалять старую сборку перед новой
CLEAN_BEFORE_BUILD = True

# ============================================================
# ОПТИМИЗАЦИЯ: ИСКЛЮЧАЕМ НЕНУЖНЫЕ МОДУЛИ
# ============================================================
EXCLUDED_MODULES = [
    # GUI бэкенды
    'PyQt5', 'PySide2', 'PySide6', 'PyQt6',
    'matplotlib', 'mpl_toolkits',

    # Документация и тесты
    'test', 'tests', 'pytest',
    'doc', 'docs', 'examples', 'demo',

    # Jupyter/notebook
    'jupyter', 'notebook', 'ipykernel', 'ipython',
    'nbconvert', 'nbformat',

    # Веб-фреймворки
    'django', 'flask', 'fastapi', 'tornado',
    'aiohttp', 'requests',

    # Базы данных
    'sqlite3', 'psycopg2', 'mysql', 'pymongo',

    # Криптография
    'cryptography', 'openssl', 'pycryptodome',

    # Графика
    'mayavi', 'vtk', 'pygame', 'pyglet',

    # Научные (кроме torch, scipy, scikit-image)
    'pandas', 'sklearn', 'scikit-learn',
    'tensorflow', 'keras', 'theano',

    # Разное
    'pdb', 'distutils', 'setuptools', 'pip',
    'pkg_resources', 'site', 'venv',
    'bdb',

    # Специальные исключения (уменьшаем размер)
    'numpy.f2py.tests',
    'torch.utils.tensorboard',
    'torch.distributed',
    'torch.cuda',  # Исключаем CUDA для уменьшения размера (~500MB)
    'torch.jit',
    'torch._inductor',
    'torch._dynamo',
    'torch._functorch',
    'torch._prims',
]

# ============================================================
# ОПТИМИЗАЦИЯ: UPX сжатие
# ============================================================
USE_UPX = True
UPX_PATH = "upx"


# ============================================================
# ОСНОВНОЙ КОД СБОРКИ
# ============================================================


def clean_old_build():
    """Удаляет старые папки сборки"""
    if CLEAN_BEFORE_BUILD:
        for folder in [OUTPUT_DIR, BUILD_DIR]:
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder)
                    print(f"🗑️ Удалена папка: {folder}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить {folder}: {e}")


def get_version():
    """Пытается прочитать версию из src/version_checker.py"""
    try:
        version_file = Path("src/version_checker.py")
        if version_file.exists():
            with open(version_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'APP_VERSION' in line and '=' in line:
                        version = line.split('=')[-1].strip().strip('"\'')
                        return version
    except:
        pass
    return "0.5"


def build_exe():
    """Запускает сборку через PyInstaller"""

    print("=" * 60)
    print(f"🚀 СБОРКА {APP_NAME} (С ПОДДЕРЖКОЙ OCR)")
    print("=" * 60)

    version = get_version()
    print(f"📦 Версия: {version}")
    print(f"📁 Выходная папка: {OUTPUT_DIR}")
    print("=" * 60)

    # Аргументы для PyInstaller
    args = [
        'main.py',
        f'--name={APP_NAME}',
        '--windowed',
        '--noconsole',
        '--noconfirm',
        f'--distpath={OUTPUT_DIR}',
        f'--workpath={BUILD_DIR}',
    ]

    # Добавляем исключения
    for module in EXCLUDED_MODULES:
        args.append(f'--exclude-module={module}')

    # Добавляем UPX если доступен
    if USE_UPX:
        upx_path = UPX_PATH
        if shutil.which(upx_path):
            args.append(f'--upx-dir={os.path.dirname(shutil.which(upx_path))}')
            print("✅ UPX найден, будет использовано сжатие")
        else:
            upx_paths = [
                "C:/upx/upx.exe",
                "C:/Program Files/upx/upx.exe",
                os.path.expanduser("~/upx/upx.exe"),
            ]
            for path in upx_paths:
                if os.path.exists(path):
                    args.append(f'--upx-dir={os.path.dirname(path)}')
                    print(f"✅ UPX найден: {path}")
                    break
            else:
                print("⚠️ UPX не найден, сжатие будет стандартным")

    # ============================================================
    # ДОБАВЛЯЕМ ДАННЫЕ
    # ============================================================
    args.extend([
        '--add-data=src;src',
    ])

    # ============================================================
    # СКРЫТЫЕ ИМПОРТЫ
    # ============================================================
    args.extend([
        # Windows API
        '--hidden-import=win32gui',
        '--hidden-import=win32api',
        '--hidden-import=win32con',
        '--hidden-import=win32ui',
        '--hidden-import=win32process',
        '--hidden-import=win32file',

        # Playwright
        '--hidden-import=playwright',

        # OpenCV
        '--hidden-import=cv2',

        # EasyOCR и его зависимости
        '--hidden-import=easyocr',
        '--hidden-import=easyocr.recognition',
        '--hidden-import=easyocr.detection',
        '--hidden-import=easyocr.utils',

        # PyTorch
        '--hidden-import=torch',
        '--hidden-import=torch.backends',
        '--hidden-import=torch.nn',
        '--hidden-import=torch.optim',
        '--hidden-import=torch.utils',
        '--hidden-import=torch.autograd',
        '--hidden-import=torch.serialization',
        '--hidden-import=torch._C',
        '--hidden-import=torch._C._cudnn',
        '--hidden-import=torch._C._nvtx',

        # torchvision
        '--hidden-import=torchvision',
        '--hidden-import=torchvision.transforms',
        '--hidden-import=torchvision.models',
        '--hidden-import=torchvision.ops',

        # SciPy (необходим для easyocr)
        '--hidden-import=scipy',
        '--hidden-import=scipy.special',
        '--hidden-import=scipy.spatial',
        '--hidden-import=scipy.ndimage',
        '--hidden-import=scipy.stats',
        '--hidden-import=scipy.optimize',
        '--hidden-import=scipy.linalg',

        # scikit-image
        '--hidden-import=skimage',
        '--hidden-import=skimage.morphology',
        '--hidden-import=skimage.measure',
        '--hidden-import=skimage.feature',
        '--hidden-import=skimage.segmentation',
        '--hidden-import=skimage.filters',
        '--hidden-import=skimage.transform',
        '--hidden-import=skimage.util',
        '--hidden-import=skimage.exposure',
        '--hidden-import=skimage.color',

        # Shapely
        '--hidden-import=shapely',
        '--hidden-import=shapely.geometry',
        '--hidden-import=shapely.ops',
        '--hidden-import=shapely.algorithms',
        '--hidden-import=shapely.errors',

        # Pyclipper
        '--hidden-import=pyclipper',

        # Python-bidi
        '--hidden-import=bidi',
        '--hidden-import=bidi.algorithm',

        # СТАНДАРТНЫЕ МОДУЛИ, которые могут быть пропущены
        '--hidden-import=fileinput',
        '--hidden-import=filecmp',
        '--hidden-import=glob',
        '--hidden-import=fnmatch',
        '--hidden-import=abc',
        '--hidden-import=enum',
        '--hidden-import=weakref',
        '--hidden-import=contextlib',
        '--hidden-import=itertools',
        '--hidden-import=functools',
        '--hidden-import=operator',
        '--hidden-import=pprint',
        '--hidden-import=textwrap',
        '--hidden-import=string',
        '--hidden-import=warnings',
        '--hidden-import=dataclasses',
        '--hidden-import=typing',

        # Модули, которые были пропущены в предыдущих сборках
        '--hidden-import=pydoc',
        '--hidden-import=doctest',
        '--hidden-import=linecache',
        '--hidden-import=atexit',
        '--hidden-import=signal',

        # Другие зависимости из requirements.txt
        '--hidden-import=dxcam',
        '--hidden-import=keyboard',
        '--hidden-import=psutil',
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageDraw',
        '--hidden-import=PIL.ImageTk',
        '--hidden-import=numpy',
        '--hidden-import=numpy.core',
        '--hidden-import=numpy._core',

        # Стандартная библиотека
        '--hidden-import=tkinter',
        '--hidden-import=ctypes',
        '--hidden-import=queue',
        '--hidden-import=threading',
        '--hidden-import=asyncio',
        '--hidden-import=inspect',
        '--hidden-import=collections',
        '--hidden-import=datetime',
        '--hidden-import=pathlib',
        '--hidden-import=logging',
        '--hidden-import=json',
        '--hidden-import=re',
        '--hidden-import=hashlib',
        '--hidden-import=tempfile',
        '--hidden-import=time',
        '--hidden-import=shutil',
        '--hidden-import=subprocess',
        '--hidden-import=winreg',
        '--hidden-import=unittest',
        '--hidden-import=traceback',
        '--hidden-import=struct',
        '--hidden-import=math',
        '--hidden-import=random',
        '--hidden-import=statistics',
        '--hidden-import=binascii',
        '--hidden-import=zlib',
        '--hidden-import=gzip',
        '--hidden-import=bz2',
        '--hidden-import=lzma',
        '--hidden-import=csv',
        '--hidden-import=xml',
        '--hidden-import=xml.etree',
        '--hidden-import=xml.etree.ElementTree',
        '--hidden-import=html',
        '--hidden-import=html.parser',
        '--hidden-import=urllib',
        '--hidden-import=urllib.parse',
        '--hidden-import=urllib.request',
        '--hidden-import=http',
        '--hidden-import=http.client',
        '--hidden-import=ssl',
        '--hidden-import=socket',
        '--hidden-import=select',
        '--hidden-import=fcntl',
    ])

    # ============================================================
    # СБОР КОЛЛЕКЦИЙ
    # ============================================================
    args.extend([
        '--collect-all=playwright',
        '--collect-all=cv2',
        '--collect-all=easyocr',
        '--collect-all=numpy',
        '--collect-all=PIL',
        '--collect-all=torch',
        '--collect-all=torchvision',
        '--collect-all=scipy',
        '--collect-all=skimage',
        '--collect-all=shapely',
        '--collect-all=pyclipper',
    ])

    # Добавляем иконку, если есть
    if os.path.exists(APP_ICON):
        args.append(f'--icon={APP_ICON}')
        print(f"✅ Иконка: {APP_ICON}")

    # ============================================================
    # ОПТИМИЗАЦИЯ ДЛЯ OPENCV
    # ============================================================
    cv2_excludes = [
        'cv2.ml', 'cv2.ocl', 'cv2.optflow', 'cv2.plot', 'cv2.quality',
        'cv2.saliency', 'cv2.sfm', 'cv2.stereo', 'cv2.superres',
        'cv2.text', 'cv2.tracking', 'cv2.videostab', 'cv2.xfeatures2d',
        'cv2.ximgproc', 'cv2.xphoto', 'cv2.aruco', 'cv2.bgsegm',
        'cv2.bioinspired', 'cv2.ccm', 'cv2.cuda', 'cv2.dnn_superres',
        'cv2.dpm', 'cv2.face', 'cv2.fisheye', 'cv2.flann', 'cv2.gapi',
    ]
    for module in cv2_excludes:
        args.append(f'--exclude-module={module}')

    # ============================================================
    # ОПТИМИЗАЦИЯ ДЛЯ NUMPY
    # ============================================================
    args.append('--exclude-module=numpy.f2py')

    # ============================================================
    # ДОПОЛНИТЕЛЬНЫЕ ФЛАГИ
    # ============================================================
    args.append('--strip')
    args.append('--log-level=ERROR')

    # Запускаем сборку
    print("\n⏳ Начинается сборка... Это может занять 15-25 минут.")
    print(f"📦 Исключено модулей: {len(EXCLUDED_MODULES)}")
    print("📦 Собираются коллекции: torch, torchvision, easyocr, opencv, scipy, scikit-image, shapely")
    print("⚡ Оптимизация: включена (--strip, исключение ненужных модулей)")
    print("✅ unittest включён в сборку (нужен для OCR)")
    print("🔇 Предупреждения PyTorch отключены")
    print("📌 Добавлены стандартные модули: pydoc, doctest, linecache, atexit, signal")
    print("=" * 60 + "\n")

    try:
        PyInstaller.__main__.run(args)
        print("\n" + "=" * 60)
        print("✅ СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
        print(f"📁 Готовый .exe: {OUTPUT_DIR}\\{APP_NAME}\\{APP_NAME}.exe")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ ОШИБКА СБОРКИ: {e}")
        sys.exit(1)


def show_size_info():
    """Показывает информацию о размере собранного приложения"""
    app_dir = Path(OUTPUT_DIR) / APP_NAME
    exe_path = app_dir / f"{APP_NAME}.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n📊 Размер .exe: {size_mb:.2f} MB")

        if app_dir.exists():
            total_size = 0
            file_count = 0
            for item in app_dir.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
            total_mb = total_size / (1024 * 1024)
            print(f"📊 Общий размер папки: {total_mb:.2f} MB ({file_count} файлов)")


def copy_additional_files():
    """Копирует дополнительные файлы (если нужно)"""
    output_app_dir = Path(OUTPUT_DIR) / APP_NAME

    if os.path.exists(APP_ICON):
        try:
            shutil.copy(APP_ICON, output_app_dir / APP_ICON)
            print(f"✅ Иконка скопирована в {output_app_dir}")
        except Exception as e:
            print(f"⚠️ Не удалось скопировать иконку: {e}")


def create_launcher_bat():
    """Создаёт .bat файл для быстрого запуска"""
    output_app_dir = Path(OUTPUT_DIR) / APP_NAME

    bat_content = f'''@echo off
echo Запуск {APP_NAME}...
start "" "{output_app_dir}\\{APP_NAME}.exe"
'''

    bat_path = Path(OUTPUT_DIR) / f"Запустить_{APP_NAME}.bat"
    try:
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)
        print(f"✅ Создан файл запуска: {bat_path}")
    except Exception as e:
        print(f"⚠️ Не удалось создать .bat файл: {e}")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║   🛠️  СБОРЩИК GOOGLE SCREEN TRANSLATE                  ║
║   Оптимизированная версия с поддержкой OCR              ║
╚══════════════════════════════════════════════════════════╝
""")

    # Очищаем старую сборку
    clean_old_build()

    # Собираем
    build_exe()

    # Копируем дополнительные файлы
    copy_additional_files()

    # Показываем размер
    show_size_info()

    # Создаём .bat для запуска
    create_launcher_bat()

    print("\n" + "=" * 60)
    print("🎉 ГОТОВО! Запустите:")
    print(f"   {OUTPUT_DIR}\\{APP_NAME}\\{APP_NAME}.exe")
    print("=" * 60)
    print("\n📌 ПРИМЕЧАНИЯ:")
    print("   - Сборка может занимать 15-25 минут")
    print("   - Размер .exe будет около 500-800 MB (из-за PyTorch и моделей)")
    print("   - Все зависимости для OCR включены:")
    print("     - easyocr, scipy, scikit-image, shapely, pyclipper")
    print("   - Добавлены стандартные модули: pydoc, doctest, linecache, atexit, signal")
    print("   - CUDA исключена для уменьшения размера (OCR работает на CPU)")
    print("=" * 60)