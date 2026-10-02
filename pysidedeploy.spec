[app]
title = de-Mail Desktop
project_dir = .
input_file = main.py
exec_directory = dist
project_file = 
icon = src/demail/assets/de-mail.ico

[python]
python_path = C:\Users\riogr\Documents\GitHub\De-Mail-Desktop\.venv\Scripts\python.exe
packages = Nuitka==2.7.11

[qt]
qml_files = 
excluded_qml_plugins = 
modules = Core,Gui,Widgets
plugins = accessiblebridge,egldeviceintegrations,generic,iconengines,imageformats,platforminputcontexts,platforms,platforms/darwin,platformthemes,styles,xcbglintegrations

[android]
wheel_pyside = 
wheel_shiboken = 
plugins = 

[nuitka]
macos.permissions = 
mode = standalone
extra_args = --quiet --noinclude-qt-translations --windows-console-mode=disable --include-package=demail --include-data-dir=src/demail/assets=demail/assets --include-data-files=CHANGELOG.md=CHANGELOG.md --file-version=0.2.0.0 --product-version=0.2.0.0 --company-name=de-Mail --product-name="de-Mail Desktop" --file-description="de-Mail Desktop"

[buildozer]
mode = debug
recipe_dir = 
jars_dir = 
ndk_path = 
sdk_path = 
local_libs = 
arch = 

