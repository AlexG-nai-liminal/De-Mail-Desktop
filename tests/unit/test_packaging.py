import configparser
import importlib.util
import tomllib
from pathlib import Path

from demail import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_deployment_configuration_uses_windows_gui_standalone_mode() -> None:
    config = configparser.ConfigParser()
    assert config.read(ROOT / "pysidedeploy.spec")
    assert config["app"]["title"] == "de-Mail Desktop"
    assert config["app"]["input_file"] == "main.py"
    assert config["app"]["icon"] == "src/demail/assets/de-mail.ico"
    assert config["nuitka"]["mode"] == "standalone"
    assert "--windows-console-mode=disable" in config["nuitka"]["extra_args"]
    assert "--include-package=demail" in config["nuitka"]["extra_args"]
    assert "--include-data-files=src/demail/assets/de-mail.ico=" in (
        config["nuitka"]["extra_args"]
    )
    assert "--include-data-dir=src/demail/assets/tutorial=" in (
        config["nuitka"]["extra_args"]
    )
    assert set(config["qt"]["modules"].split(",")) == {"Core", "Gui", "Widgets"}


def test_deployment_entry_point_imports_from_source_layout() -> None:
    spec = importlib.util.spec_from_file_location("demail_deploy_entry", ROOT / "main.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)


def test_package_and_runtime_versions_remain_identical() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)
    assert project["project"]["version"] == __version__


def test_runtime_dependency_surface_is_intentional_and_bounded() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        dependencies = tomllib.load(stream)["project"]["dependencies"]
    assert {item.split("<", 1)[0].split(">", 1)[0] for item in dependencies} == {
        "PySide6",
        "google-auth",
        "google-auth-oauthlib",
        "httpx",
    }
    assert all(">=" in item and ",<" in item for item in dependencies)
