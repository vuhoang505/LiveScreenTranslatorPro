from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("keyring")
hiddenimports = collect_submodules("keyring.backends")

