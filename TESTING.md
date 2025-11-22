# Testing Report

## Environment
- Repository: Intaract_map
- Date: 2025-11-21T10:10:00Z

## Actions
1. Attempted to install dependencies via: python -m pip install -r src/my_package/requirements.txt
2. Attempted to run the PyInstaller build with: python src/my_package/build_exe.py
3. Attempted to start the application in offscreen mode with: QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox" python src/my_package/map_app.py
4. Attempted to install system GL libraries with: sudo apt-get update

## Results
- Dependency installation again failed to download PyInstaller==6.16.0 because the proxy blocked the request (HTTP 403). Other packages were already present.
- Build could not proceed because PyInstaller is not installed and no offline wheel was provided via PYINSTALLER_WHEEL.
- Runtime launch failed because the system library libGL.so.1 is missing, which is required by PyQtWebEngine.
- The package index is unreachable via apt (403 proxy), so installing libGL from the distribution repositories was not possible.

## Notes
- Access to PyPI (or a local wheel provided via PYINSTALLER_WHEEL) is required to install PyInstaller and complete the build.
- Installing libGL.so.1 (for example via the libgl1 package on Debian/Ubuntu) is needed to run the Qt application in this environment.
- Proxy access to the apt repositories must be fixed or a local package mirror provided to fetch libGL.

## Latest Test (2025-11-22)
- Command: QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox" python src/my_package/map_app.py
- Result: failed to start because libGL.so.1 is missing from the container; PyQtWebEngine requires this system library even when running offscreen.
