from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata


binaries = collect_dynamic_libs("sentencepiece")
datas = copy_metadata("sentencepiece")
hiddenimports = ["sentencepiece._sentencepiece"]
