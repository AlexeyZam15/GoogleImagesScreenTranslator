"""
Модуль для OCR обработки переведённых изображений
Использует EasyOCR для обнаружения текстовых зон
"""

import cv2
import easyocr
import numpy as np
import time
import logging
from pathlib import Path
from typing import List, Tuple, Optional


class OCRProcessor:
    """Обработчик OCR для обнаружения текстовых зон на изображении"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.reader = None
        self._initialized = False
        self._initializing = False

    def draw_bboxes_with_ids(self, image: np.ndarray, results: List, colors=None) -> np.ndarray:
        """Отрисовка bounding boxes с ID и разными цветами для отладки"""
        import cv2
        import numpy as np

        img_copy = image.copy()

        if colors is None:
            colors = [
                (0, 255, 0),  # Зеленый
                (255, 0, 0),  # Синий
                (0, 0, 255),  # Красный
                (255, 255, 0),  # Голубой
                (255, 0, 255),  # Пурпурный
                (0, 255, 255),  # Желтый
                (128, 128, 0),  # Оливковый
                (0, 128, 128),  # Бирюзовый
            ]

        for idx, (bbox, text, confidence) in enumerate(results):
            color = colors[idx % len(colors)]
            pts = np.array(bbox, dtype=np.int32)
            cv2.polylines(img_copy, [pts], True, color, 3)

            x, y = pts[0]
            label = f"#{idx + 1}: {text[:15]}"
            cv2.putText(img_copy, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            cv2.putText(img_copy, f"{confidence:.2f}", (x, y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return img_copy

    def initialize(self):
        """Инициализация EasyOCR (вызывается один раз при старте)"""
        if self._initialized:
            return

        if self._initializing:
            self.logger.info("EasyOCR уже инициализируется, ждём...")
            while self._initializing:
                time.sleep(0.1)
            return

        self._initializing = True
        self.logger.info("🔄 Инициализация EasyOCR (загрузка моделей)...")

        try:
            self.reader = easyocr.Reader(
                ['ru', 'en'],
                gpu=False,
                verbose=False
            )
            self._initialized = True
            self.logger.info("✅ EasyOCR инициализирован")
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации EasyOCR: {e}")
            raise
        finally:
            self._initializing = False

    def is_ready(self) -> bool:
        """Проверяет, инициализирован ли OCR"""
        return self._initialized

    def load_image(self, image_path: Path) -> np.ndarray:
        """Загрузка изображения"""
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Не удалось загрузить изображение: {image_path}")
        return image

    def resize_image_small(self, image: np.ndarray, max_size: int = 600) -> Tuple[np.ndarray, float]:
        """Уменьшение изображения для максимальной скорости"""
        h, w = image.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA), scale
        return image, 1.0

    def calculate_iou(self, bbox1: List, bbox2: List) -> float:
        """Вычисление IoU (Intersection over Union) для двух bounding boxes"""
        x1_1, y1_1 = bbox1[0]
        x2_1, y2_1 = bbox1[2]
        x1_2, y1_2 = bbox2[0]
        x2_2, y2_2 = bbox2[2]

        x_left = max(x1_1, x1_2)
        y_top = max(y1_1, y1_2)
        x_right = min(x2_1, x2_2)
        y_bottom = min(y2_1, y2_2)

        if x_right < x_left or y_bottom < y_top:
            return 0.0

        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - intersection_area

        if union_area == 0:
            return 0.0

        return intersection_area / union_area

    def calculate_gap(self, bbox1: List, bbox2: List) -> float:
        """
        Вычисляет расстояние между границами двух bounding boxes (вертикальный gap).
        Если зоны перекрываются по вертикали, возвращает 0.
        """
        y1_bottom = bbox1[2][1]
        y1_top = bbox1[0][1]
        y2_bottom = bbox2[2][1]
        y2_top = bbox2[0][1]

        if y1_bottom >= y2_top and y2_bottom >= y1_top:
            return 0.0

        if y1_bottom < y2_top:
            return y2_top - y1_bottom
        else:
            return y1_top - y2_bottom

    def shrink_bbox(self, bbox: List, shrink_pixels: int = 8) -> List:
        """Сжатие bounding box на заданное количество пикселей с каждой стороны"""
        x_coords = [p[0] for p in bbox]
        y_coords = [p[1] for p in bbox]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        x_min += shrink_pixels
        x_max -= shrink_pixels
        y_min += shrink_pixels
        y_max -= shrink_pixels

        if x_min >= x_max or y_min >= y_max:
            return bbox

        return [
            [x_min, y_min],
            [x_max, y_min],
            [x_max, y_max],
            [x_min, y_max]
        ]

    def merge_overlapping_boxes(self, results: List, iou_threshold: float = 0.05, shrink_pixels: int = 0,
                                gap_threshold: float = 30) -> List:
        """
        Объединение bounding boxes по расстоянию между границами (gap).

        Объединяет зоны если:
        1. Расстояние между границами (вертикальный gap) < gap_threshold
        2. И зоны перекрываются по X (находятся в одном столбце)
        """
        if not results:
            return results

        results = results.copy()

        self.logger.info(f"  Объединение ПО GAP: вертикальный gap < {gap_threshold}px")

        merged = []
        used_indices = set()

        for i in range(len(results)):
            if i in used_indices:
                continue

            current_bbox, current_text, current_conf = results[i]

            for j in range(i + 1, len(results)):
                if j in used_indices:
                    continue

                bbox_j, text_j, conf_j = results[j]

                x_overlap = max(0, min(current_bbox[2][0], bbox_j[2][0]) - max(current_bbox[0][0], bbox_j[0][0]))
                min_width = min(current_bbox[2][0] - current_bbox[0][0], bbox_j[2][0] - bbox_j[0][0])
                x_overlap_ratio = x_overlap / min_width if min_width > 0 else 0

                gap = self.calculate_gap(current_bbox, bbox_j)

                should_merge = (gap < gap_threshold and x_overlap_ratio > 0.1)

                if should_merge:
                    self.logger.info(
                        f"    ✅ ОБЪЕДИНЯЕМ '{current_text[:20]}' и '{text_j[:20]}' (gap={gap:.1f}px, X_ov={x_overlap_ratio:.2f})")

                    if text_j not in current_text:
                        current_text = current_text + " " + text_j

                    current_conf = max(current_conf, conf_j)

                    x_coords = [p[0] for p in current_bbox] + [p[0] for p in bbox_j]
                    y_coords = [p[1] for p in current_bbox] + [p[1] for p in bbox_j]
                    current_bbox = [
                        [min(x_coords), min(y_coords)],
                        [max(x_coords), min(y_coords)],
                        [max(x_coords), max(y_coords)],
                        [min(x_coords), max(y_coords)]
                    ]

                    used_indices.add(j)
                else:
                    if gap < gap_threshold * 2:
                        reason = []
                        if gap >= gap_threshold:
                            reason.append(f"gap={gap:.1f}px >= {gap_threshold}")
                        if x_overlap_ratio <= 0.1:
                            reason.append(f"X_ov={x_overlap_ratio:.2f} <= 0.1")
                        self.logger.info(
                            f"    ❌ НЕ объединяем '{current_text[:15]}' и '{text_j[:15]}' ({', '.join(reason)})")

            merged.append((current_bbox, current_text, current_conf))
            used_indices.add(i)

        return merged

    def process_image(self, image_path: Path, max_size: int = 600, save_debug: bool = False, debug_dir: Path = None,
                      debug_prefix: str = None) -> Tuple[List, float]:
        """
        Обработка изображения через OCR
        Возвращает: (список областей, время выполнения)
        """
        import re

        if not self._initialized:
            raise RuntimeError("EasyOCR не инициализирован. Вызовите initialize() сначала.")

        self.logger.info(f"OCR обработка: {image_path}")

        image = self.load_image(image_path)
        original_image = image.copy()

        resized_image, resize_scale = self.resize_image_small(image, max_size)

        self.logger.info(f"  Размер: {original_image.shape[:2]} -> {resized_image.shape[:2]}")

        start_time = time.time()

        results = self.reader.readtext(
            resized_image,
            detail=1,
            paragraph=False,
            text_threshold=0.4,
            low_text=0.25
        )

        elapsed_time = time.time() - start_time

        if resize_scale != 1.0 and results:
            scaled_results = []
            for bbox, text, confidence in results:
                scaled_bbox = [[int(x / resize_scale), int(y / resize_scale)] for x, y in bbox]
                scaled_results.append((scaled_bbox, text, confidence))
            results = scaled_results

        self.logger.info(f"  До фильтрации: {len(results)} областей")

        # === ФИЛЬТРУЕМ ЗОНЫ ДО ОБЪЕДИНЕНИЯ ===
        filtered_results = []
        for bbox, text, confidence in results:
            # Удаляем пробелы и спецсимволы для проверки
            clean_text = re.sub(r'[\s\-_/\\.,:;!?()#\'"`]', '', text)

            # Проверяем, есть ли буквы в тексте
            has_letters = any(c.isalpha() for c in clean_text)

            if has_letters:
                filtered_results.append((bbox, text, confidence))
            else:
                self.logger.debug(f"  Пропущена зона (только цифры/символы): '{text}'")

        self.logger.info(
            f"  После фильтрации: {len(filtered_results)} областей (удалено {len(results) - len(filtered_results)})")

        # Сохраняем копию ДО объединения для лога
        results_before_merge = filtered_results.copy()

        if save_debug:
            try:
                if filtered_results:
                    debug_image = self.draw_bboxes_with_ids(original_image.copy(), filtered_results)
                else:
                    # Если нет зон, показываем пустую картинку
                    debug_image = original_image.copy()

                if debug_dir is None:
                    debug_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                else:
                    debug_dir = Path(debug_dir)
                    debug_dir.mkdir(parents=True, exist_ok=True)

                if debug_prefix is None:
                    debug_prefix = image_path.stem

                debug_path = debug_dir / f"{debug_prefix}_debug_ids.png"
                cv2.imwrite(str(debug_path), debug_image)
                self.logger.info(f"  Отладка (исходные зоны) сохранена: {debug_path}")
            except Exception as e:
                self.logger.warning(f"  Не удалось сохранить отладку: {e}")

        # Объединяем области (ТОЛЬКО отфильтрованные)
        merged_results = self.merge_overlapping_boxes(filtered_results, iou_threshold=0.05, gap_threshold=30)

        self.logger.info(f"  После объединения: {len(merged_results)} областей")
        self.logger.info(f"  ⏱️ Время OCR: {elapsed_time:.2f}с")

        # Сохраняем лог зон
        if save_debug:
            try:
                if debug_dir is None:
                    debug_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                else:
                    debug_dir = Path(debug_dir)
                    debug_dir.mkdir(parents=True, exist_ok=True)

                if debug_prefix is None:
                    debug_prefix = image_path.stem

                self.save_zones_log(
                    results_before=results_before_merge,
                    results_after=merged_results,
                    image_path=image_path,
                    debug_dir=debug_dir,
                    debug_prefix=debug_prefix,
                    gap_threshold=30,
                    shrink_pixels=0
                )
            except Exception as e:
                self.logger.warning(f"  Не удалось сохранить лог зон: {e}")

        return merged_results, elapsed_time

    def get_regions_from_image(self, translated_image_path: Path, save_debug: bool = False, debug_dir: Path = None,
                               debug_prefix: str = None) -> List[Tuple[int, int, int, int]]:
        """
        Получает список прямоугольников областей с текстом на переведённом изображении
        Возвращает: [(x1, y1, x2, y2), ...] в координатах исходного изображения
        """
        results, _ = self.process_image(
            translated_image_path,
            save_debug=save_debug,
            debug_dir=debug_dir,
            debug_prefix=debug_prefix
        )

        regions = []
        for bbox, text, confidence in results:
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]

            x1 = int(min(x_coords))
            y1 = int(min(y_coords))
            x2 = int(max(x_coords))
            y2 = int(max(y_coords))

            if x2 > x1 and y2 > y1:
                regions.append((x1, y1, x2, y2))

        return regions

    def save_zones_log(self, results_before: List, results_after: List, image_path: Path, debug_dir: Path,
                       debug_prefix: str = None, gap_threshold: float = 30, shrink_pixels: int = 0) -> Path:
        """Сохраняет лог с информацией о зонах"""
        if debug_prefix is None:
            debug_prefix = image_path.stem

        log_path = debug_dir / f"{debug_prefix}_zones_log.txt"

        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write(f"  📊 ОТЧЁТ ПО ЗОНАМ OCR\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"📷 Изображение: {image_path.name}\n")
            f.write(f"🕐 Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

            image = self.load_image(image_path)
            h, w = image.shape[:2]
            f.write(f"📐 Размер: {w}x{h}\n")
            f.write(f"🔧 Параметры: gap порог = {gap_threshold}px, сжатие = {shrink_pixels}px\n")
            f.write("\n" + "-" * 70 + "\n\n")

            f.write(f"📌 ЗОНЫ ДО ОБЪЕДИНЕНИЯ ({len(results_before)} областей):\n")
            f.write("-" * 50 + "\n")
            for idx, (bbox, text, confidence) in enumerate(results_before, 1):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                x1, y1 = int(min(x_coords)), int(min(y_coords))
                x2, y2 = int(max(x_coords)), int(max(y_coords))
                f.write(f"  #{idx}: '{text}'\n")
                f.write(f"     Уверенность: {confidence:.3f}\n")
                f.write(f"     Координаты: ({x1}, {y1}) - ({x2}, {y2})\n")
                f.write(f"     Размер: {x2 - x1}x{y2 - y1}\n")
            f.write("\n" + "-" * 70 + "\n\n")

            f.write(f"🔍 ПРОВЕРКА GAP (вертикальный gap < {gap_threshold}px):\n")
            f.write("-" * 50 + "\n")

            any_merged = False
            for i in range(len(results_before)):
                for j in range(i + 1, len(results_before)):
                    bbox_i = results_before[i][0]
                    bbox_j = results_before[j][0]

                    x_overlap = max(0, min(bbox_i[2][0], bbox_j[2][0]) - max(bbox_i[0][0], bbox_j[0][0]))
                    min_width = min(bbox_i[2][0] - bbox_i[0][0], bbox_j[2][0] - bbox_j[0][0])
                    x_overlap_ratio = x_overlap / min_width if min_width > 0 else 0

                    gap = self.calculate_gap(bbox_i, bbox_j)

                    should_merge = (gap < gap_threshold and x_overlap_ratio > 0.1)

                    if gap < gap_threshold * 2:
                        text_i = results_before[i][1]
                        text_j = results_before[j][1]
                        status = "✅ ОБЪЕДИНЯЕМ" if should_merge else "❌ НЕ объединяем"
                        f.write(f"  {status}: '{text_i}' vs '{text_j}'\n")
                        f.write(f"     gap = {gap:.1f}px, X_ov = {x_overlap_ratio:.2f}\n")
                        any_merged = True

            if not any_merged:
                f.write("  (нет зон с gap < порога)\n")
            f.write("\n" + "-" * 70 + "\n\n")

            f.write(f"📌 ЗОНЫ ПОСЛЕ ОБЪЕДИНЕНИЯ ({len(results_after)} областей):\n")
            f.write("-" * 50 + "\n")
            for idx, (bbox, text, confidence) in enumerate(results_after, 1):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                x1, y1 = int(min(x_coords)), int(min(y_coords))
                x2, y2 = int(max(x_coords)), int(max(y_coords))
                f.write(f"  #{idx}: '{text}'\n")
                f.write(f"     Уверенность: {confidence:.3f}\n")
                f.write(f"     Координаты: ({x1}, {y1}) - ({x2}, {y2})\n")

            f.write("\n" + "=" * 70 + "\n")
            f.write(f"  ИТОГО: {len(results_before)} → {len(results_after)} областей\n")
            f.write("=" * 70 + "\n")

        self.logger.info(f"  📄 Лог зон сохранён: {log_path}")
        return log_path
