import runpy
from pathlib import Path
from unittest.mock import patch

import yaml


PACKAGE = Path(__file__).parents[1]


def test_package_requires_supported_official_wuji_sdk() -> None:
    setup_kwargs = {}
    setup_path = PACKAGE / "setup.py"

    with patch(
        "setuptools.setup", side_effect=lambda **kwargs: setup_kwargs.update(kwargs)
    ):
        runpy.run_path(str(setup_path), run_name="__main__")

    assert "wuji-sdk==2026.10.12" in setup_kwargs["install_requires"]


def test_driver_config_disables_cross_process_sdk_bridge() -> None:
    config = yaml.safe_load((PACKAGE / "config/wuji_hand_2.yaml").read_text())

    assert config["/**"]["ros__parameters"]["enable_sdk_bridge"] is False
