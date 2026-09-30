from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

release_version = Path('build/release-version.json')
if not release_version.is_file():
    raise RuntimeError('Release version missing; build through scripts/build_installer.py')

a = Analysis(
    ['scripts/run_app.py'],
    pathex=['src'],
    binaries=collect_dynamic_libs('ctranslate2'),
    datas=collect_data_files('faster_whisper') + collect_data_files('whisper_desk') +
          [(str(release_version), 'whisper_desk/assets')],
    hiddenimports=['scipy.special', 'scipy.signal', '_sounddevice_data'],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'torch', 'matplotlib', 'pytest'],
)
pyz = PYZ(a.pure)
# These are acquired from the locked NVIDIA archives by Setup. Do not accidentally
# redistribute DLLs found on the build machine or give them loader precedence.
a.binaries = [entry for entry in a.binaries if not entry[0].replace('\\', '/').split('/')[-1].lower().startswith(
    ('cudnn', 'cublas', 'cudart', 'nvrtc', 'nvjitlink'))]
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='WhisperDesk',
          console=False, debug=False, upx=False, icon='src/whisper_desk/assets/app.ico')
coll = COLLECT(exe, a.binaries, a.datas, name='WhisperDesk', upx=False)
