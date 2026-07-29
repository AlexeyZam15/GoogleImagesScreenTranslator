"""
Модуль для управления настройками приложения с поддержкой профилей
"""

import json
from pathlib import Path
from src.strings import STRINGS


class Settings:
    """Класс для управления настройками"""

    DEFAULT_SETTINGS = {
        "language": "ru",
        "target_language": "ru",
        "confidence_threshold": 0.8,
        "monitor_delay": 0.3,
        "zoom_normal": 1.08,
        "hide_delay": 1500,
        "always_on_top": True,
        "current_profile": "default",
        "show_browser": True,
        "show_translation_indicator": True,
        "browser_path": "",
        "auto_hide_overlay": True,
        "auto_windowed_fullscreen": True,
        "edit_mode_enabled": False
    }

    # Значения горячих клавиш по умолчанию
    DEFAULT_HOTKEYS = {
        "screenshot": "f2",
        "area": "f3",
        "toggle_overlay": "f1",
        "clear_all": "f4",
        "edit_mode": "f5"
    }

    def __init__(self):
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.profiles = {}
        self.current_profile = "default"
        self._config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        self._config_file = self._config_dir / "settings.json"
        self.load()

    def get_edit_mode_enabled(self) -> bool:
        """Возвращает настройку режима редактирования."""
        return self.settings.get("edit_mode_enabled", False)

    def set_edit_mode_enabled(self, enabled: bool):
        """Устанавливает настройку режима редактирования."""
        self.settings["edit_mode_enabled"] = enabled
        self.save()

    def get_auto_windowed_fullscreen(self) -> bool:
        """Возвращает настройку автоматического преобразования в оконный полноэкранный режим"""
        return self.settings.get("auto_windowed_fullscreen", False)

    def set_auto_windowed_fullscreen(self, enabled: bool):
        """Устанавливает настройку автоматического преобразования в оконный полноэкранный режим"""
        self.settings["auto_windowed_fullscreen"] = enabled
        self.save()

    def load_values(self):
        """Загружает текущие настройки в поля"""
        current_path = self.settings.get_browser_path()
        self.browser_path_var.set(current_path)
        if hasattr(self, 'show_indicator_var'):
            self.show_indicator_var.set(self.settings.get_show_translation_indicator())
        if hasattr(self, 'auto_hide_var'):
            self.auto_hide_var.set(self.settings.get_auto_hide_overlay())
        if hasattr(self, 'auto_windowed_fullscreen_var'):
            self.auto_windowed_fullscreen_var.set(self.settings.get_auto_windowed_fullscreen())
        if hasattr(self, 'hotkey_vars'):
            for action, var in self.hotkey_vars.items():
                var.set(self.settings.get_hotkey(action))

    def get_browser_path(self) -> str:
        """Возвращает путь к браузеру из настроек"""
        return self.settings.get("browser_path", "")

    def set_browser_path(self, path: str):
        """Сохраняет путь к браузеру в настройки"""
        self.settings["browser_path"] = path
        self.save()

    def get_auto_hide_overlay(self) -> bool:
        """Возвращает настройку автоскрытия оверлея"""
        return self.settings.get("auto_hide_overlay", True)

    def set_auto_hide_overlay(self, enabled: bool):
        """Устанавливает настройку автоскрытия оверлея"""
        self.settings["auto_hide_overlay"] = enabled
        self.save()

    def _ensure_config_dir(self):
        """Создает директорию для конфигурации"""
        if not self._config_dir.exists():
            self._config_dir.mkdir(parents=True, exist_ok=True)

    def save(self):
        """Сохраняет настройки в файл"""
        try:
            self._ensure_config_dir()
            config_data = {
                "settings": self.settings,
                "profiles": self.profiles,
                "current_profile": self.current_profile
            }
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False, default=str)
            return True
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
            return False

    def load(self):
        """Загружает настройки из файла"""
        try:
            self._ensure_config_dir()
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                if "settings" in loaded:
                    for key, value in loaded["settings"].items():
                        self.settings[key] = value
                if "profiles" in loaded:
                    self.profiles = loaded["profiles"]
                if "current_profile" in loaded:
                    self.current_profile = loaded["current_profile"]
                if not self.profiles:
                    self.profiles = {
                        "default": {
                            "name": "Профиль по умолчанию",
                            "pairs": []
                        }
                    }
                    self.save()
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")

    def get(self, key, default=None):
        """Возвращает значение настройки"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Устанавливает значение настройки"""
        self.settings[key] = value
        self.save()

    def get_language(self):
        """Возвращает текущий язык интерфейса"""
        return self.settings.get("language", "ru")

    def set_language(self, lang):
        """Устанавливает язык интерфейса"""
        self.settings["language"] = lang
        self.save()

    def get_string(self, key):
        """Возвращает локализованную строку"""
        from src.strings import get_strings
        lang = self.get_language()
        strings = get_strings(lang)
        return strings.get(key, key)

    def get_show_browser(self):
        """Возвращает настройку показа браузера"""
        return self.settings.get("show_browser", True)

    def set_show_browser(self, show):
        """Устанавливает настройку показа браузера"""
        self.settings["show_browser"] = show
        self.save()

    def get_target_language(self):
        """Возвращает целевой язык перевода"""
        return self.settings.get("target_language", "ru")

    def set_target_language(self, lang_code):
        """Устанавливает целевой язык перевода"""
        self.settings["target_language"] = lang_code
        self.save()

    def get_show_translation_indicator(self):
        """Возвращает настройку показа индикатора перевода"""
        return self.settings.get("show_translation_indicator", True)

    def set_show_translation_indicator(self, show):
        """Устанавливает настройку показа индикатора перевода"""
        self.settings["show_translation_indicator"] = show
        self.save()

    def get_profiles_list(self):
        """Возвращает список всех профилей"""
        return list(self.profiles.keys())

    def get_profile_name(self, profile_id):
        """Возвращает имя профиля"""
        if profile_id in self.profiles:
            return self.profiles[profile_id].get("name", profile_id)
        return profile_id

    def get_current_profile(self):
        """Возвращает ID текущего профиля"""
        return self.current_profile

    def set_current_profile(self, profile_id):
        """Устанавливает текущий профиль"""
        if profile_id in self.profiles:
            self.current_profile = profile_id
            self.save()

    def create_profile(self, profile_id, name=None):
        """Создает новый профиль"""
        if profile_id in self.profiles:
            return False
        self.profiles[profile_id] = {
            "name": name or profile_id,
            "pairs": []
        }
        self.save()
        return True

    def delete_profile(self, profile_id):
        """Удаляет профиль"""
        if profile_id == "default":
            return False
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            if self.current_profile == profile_id:
                self.current_profile = "default"
            self.save()
            return True
        return False

    # ========== МЕТОДЫ ДЛЯ ГОРЯЧИХ КЛАВИШ ==========

    def get_hotkey(self, action: str) -> str:
        """
        Возвращает назначенную горячую клавишу для действия.
        Если клавиша не назначена, возвращает значение по умолчанию.
        """
        return self.settings.get(f"hotkey_{action}", self.DEFAULT_HOTKEYS.get(action, ""))

    def set_hotkey(self, action: str, key: str):
        """Устанавливает горячую клавишу для действия. Нормализует строку."""
        # Нормализуем: приводим к нижнему регистру, убираем лишние пробелы
        normalized = key.lower().strip()
        # Убираем дублирующиеся модификаторы
        parts = normalized.split('+')
        unique_parts = []
        seen = set()
        for p in parts:
            p = p.strip()
            if p and p not in seen:
                unique_parts.append(p)
                seen.add(p)
        normalized = '+'.join(unique_parts)
        self.settings[f"hotkey_{action}"] = normalized
        self.save()

    def get_all_hotkeys(self) -> dict:
        """Возвращает словарь всех горячих клавиш."""
        return {
            "screenshot": self.get_hotkey("screenshot"),
            "area": self.get_hotkey("area"),
            "toggle_overlay": self.get_hotkey("toggle_overlay"),
            "clear_all": self.get_hotkey("clear_all"),
            "edit_mode": self.get_hotkey("edit_mode")
        }

    def reset_hotkeys_to_default(self):
        """Сбрасывает все горячие клавиши к значениям по умолчанию."""
        for action, default_key in self.DEFAULT_HOTKEYS.items():
            self.settings[f"hotkey_{action}"] = default_key
        self.save()
