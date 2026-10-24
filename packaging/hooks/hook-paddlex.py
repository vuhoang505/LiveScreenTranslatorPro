from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = collect_all("paddlex")

# PaddleX checks the installed distribution metadata (not just importability)
# before allowing the OCR pipeline to start. PyInstaller normally omits the
# metadata for these optional-extra packages, so include the OCR-core set.
for distribution in (
    "imagesize",
    "opencv-contrib-python",
    "pyclipper",
    "pypdfium2",
    "python-bidi",
    "shapely",
):
    datas += copy_metadata(distribution)

