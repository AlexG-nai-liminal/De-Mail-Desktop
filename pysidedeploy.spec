[app]
title = de-Mail Desktop
project_dir = .
input_file = main.py
exec_directory = dist
project_file = 
icon = src/demail/assets/de-mail.ico

[python]
python_path = .venv/Scripts/python.exe
packages = Nuitka==2.7.11

[qt]
qml_files = 
excluded_qml_plugins = 
modules = Core,Gui,Widgets
plugins =

[android]
wheel_pyside = 
wheel_shiboken = 
plugins = 

[nuitka]
macos.permissions = 
mode = standalone
extra_args = --quiet --noinclude-qt-translations --windows-console-mode=disable --include-package=demail --include-data-files=src/demail/assets/de-mail.ico=demail/assets/de-mail.ico --include-data-dir=src/demail/assets/tutorial=demail/assets/tutorial

[buildozer]
mode = debug
recipe_dir = 
jars_dir = 
ndk_path = 
sdk_path = 
local_libs = 
arch = 

