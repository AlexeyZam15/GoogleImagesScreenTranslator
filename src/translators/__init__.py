"""
Модуль для работы с различными сервисами перевода изображений.
"""

from .base_translator import BaseTranslator
from .google_translator import GoogleTranslateDebug
from .yandex_translator import YandexOcrTranslator

__all__ = [
    'BaseTranslator',
    'GoogleTranslateDebug',
    'YandexOcrTranslator',
]