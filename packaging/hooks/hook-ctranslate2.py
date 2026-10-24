from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata


binaries = collect_dynamic_libs("ctranslate2")
datas = copy_metadata("ctranslate2")
hiddenimports = ["ctranslate2._ext"]
