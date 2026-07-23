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
        "browser_path": ""
    }

    def __init__(self):
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.profiles = {}
        self.current_profile = "default"
        self._config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        self._config_file = self._config_dir / "settings.json"
        self.load()

    def get_browser_path(self) -> str:
        """Возвращает путь к браузеру из настроек"""
        return self.settings.get("browser_path", "")

    def set_browser_path(self, path: str):
        """Сохраняет путь к браузеру в настройки"""
        self.settings["browser_path"] = path
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
        lang = self.get_language()
        return STRINGS.get(lang, STRINGS['ru']).get(key, key)

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