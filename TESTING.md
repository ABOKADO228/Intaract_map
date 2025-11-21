# Testing Report

## Environment
- Repository: Intaract_map
- Date: 2025-11-21T09:50:12Z

## Actions
1. Attempted to install dependencies via: python -m pip install -r src/my_package/requirements.txt
2. Attempted to run the PyInstaller build with: python src/my_package/build_exe.py
3. Attempted to start the application in offscreen mode with: QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox" python src/my_package/map_app.py

## Results
- Dependency installation failed to download PyInstaller==6.16.0 because the proxy blocked the request (HTTP 403). Other packages were already present.
- Build could not proceed because PyInstaller is not installed.
- Runtime launch failed because the system library libGL.so.1 is missing, which is required by PyQtWebEngine.

## Notes
- Access to PyPI (or a local wheel) is required to install PyInstaller and complete the build.
- Installing libGL.so.1 (for example via the libgl1 package on Debian/Ubuntu) is needed to run the Qt application in this environment.
