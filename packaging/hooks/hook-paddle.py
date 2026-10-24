from PyInstaller.utils.hooks import (
    collect_all,
    is_module_or_submodule,
)

# Paddle's optional SOT/JIT and TensorRT packages execute native capability
# probes while PyInstaller scans them.  On a CPU-only Windows installation the
# probe can terminate PyInstaller's isolated helper process (0xC0000005).
# PaddleOCR inference does not use either package; normal static analysis still
# follows every core module imported by Paddle itself.
_UNUSED_NATIVE_PLUGINS = (
    "paddle.jit.sot",
    "paddle.tensorrt",
)


def _is_runtime_module(name: str) -> bool:
    return not any(
        is_module_or_submodule(name, excluded)
        for excluded in _UNUSED_NATIVE_PLUGINS
    )


datas, binaries, hiddenimports = collect_all(
    "paddle",
    include_py_files=False,
    filter_submodules=_is_runtime_module,
    on_error="ignore",
)

