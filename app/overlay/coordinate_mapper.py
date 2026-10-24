from __future__ import annotations

from app.core.models import BoundingBox


class CoordinateMapper:
    @staticmethod
    def map_box(
        box: BoundingBox,
        physical_screen: BoundingBox,
        logical_screen: BoundingBox,
    ) -> BoundingBox:
        if physical_screen.width <= 0 or physical_screen.height <= 0:
            raise ValueError("Physical screen dimensions must be positive")
        scale_x = logical_screen.width / physical_screen.width
        scale_y = logical_screen.height / physical_screen.height
        # Map both edges independently. Mapping width in isolation can leave the
        # right/bottom edge one pixel away from the OCR rectangle at fractional DPI.
        left = logical_screen.x + round(box.x * scale_x)
        top = logical_screen.y + round(box.y * scale_y)
        right = logical_screen.x + round(box.right * scale_x)
        bottom = logical_screen.y + round(box.bottom * scale_y)
        left = max(logical_screen.x, min(left, logical_screen.right - 1))
        top = max(logical_screen.y, min(top, logical_screen.bottom - 1))
        right = max(left + 1, min(right, logical_screen.right))
        bottom = max(top + 1, min(bottom, logical_screen.bottom))
        return BoundingBox(
            x=left,
            y=top,
            width=right - left,
            height=bottom - top,
        )


def sample_background_color(image, box: BoundingBox) -> str:
    """Estimate the source background using a thin ring inside the OCR rectangle."""
    import numpy as np

    height, width = image.shape[:2]
    left = max(0, box.x)
    top = max(0, box.y)
    right = min(width, box.right)
    bottom = min(height, box.bottom)
    if right <= left or bottom <= top:
        return "#10182B"
    crop = image[top:bottom, left:right]
    ring_size = max(1, min(crop.shape[:2]) // 8)
    samples = np.concatenate(
        (
            crop[:ring_size].reshape(-1, 3),
            crop[-ring_size:].reshape(-1, 3),
            crop[:, :ring_size].reshape(-1, 3),
            crop[:, -ring_size:].reshape(-1, 3),
        ),
        axis=0,
    )
    blue, green, red = np.median(samples, axis=0).astype(int)
    return f"#{red:02X}{green:02X}{blue:02X}"

