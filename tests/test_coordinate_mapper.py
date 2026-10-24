from app.core.models import BoundingBox
from app.overlay.coordinate_mapper import CoordinateMapper


def test_coordinate_mapping_at_150_percent_dpi():
    physical = BoundingBox(0, 0, 1920, 1080)
    logical = BoundingBox(100, 50, 1280, 720)
    source = BoundingBox(960, 540, 300, 90)
    assert CoordinateMapper.map_box(source, physical, logical) == BoundingBox(
        740, 410, 200, 60
    )


def test_coordinate_mapping_handles_negative_monitor_origin():
    physical = BoundingBox(-1920, 0, 1920, 1080)
    logical = BoundingBox(-1536, 0, 1536, 864)
    source = BoundingBox(100, 100, 200, 100)
    assert CoordinateMapper.map_box(source, physical, logical) == BoundingBox(
        -1456, 80, 160, 80
    )

