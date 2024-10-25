import argparse
import logging
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .const import DEFAULT_CONFIG


@dataclass
class DownloadConfig:
    min_scroll_length: int
    max_scroll_length: int
    min_scroll_step: int
    max_scroll_step: int
    rate_limit: int
    download_dir: str


@dataclass
class PathConfig:
    download_log: str
    system_log: str


@dataclass
class ChromeConfig:
    exec_path: str
    profile_path: str


@dataclass
class Config:
    download: DownloadConfig
    paths: PathConfig
    chrome: ChromeConfig


class ConfigManager:
    def load(self) -> Config:
        """Load configuration from files and environment."""
        system_config_dir = ConfigManager.get_system_config_dir()
        system_config_dir.mkdir(parents=True, exist_ok=True)

        custom_config_path = system_config_dir / "config.yaml"
        custom_env_path = system_config_dir / ".env"

        config_data = DEFAULT_CONFIG

        # Load environment variables
        if custom_env_path.exists:
            load_dotenv(custom_env_path)

        # Load and merge configurations
        if custom_config_path.exists():
            with open(custom_config_path) as f:
                custom_config = yaml.safe_load(f)
                if custom_config:  # not empty
                    ConfigManager._merge_config(config_data, custom_config)

        # Check file paths
        for key, path in config_data["paths"].items():
            config_data["paths"][key] = self.resolve_path(path, system_config_dir)

        config_data["chrome"]["profile_path"] = self.resolve_path(
            config_data["chrome"]["profile_path"], system_config_dir
        )

        # Check download_dir path
        download_dir = config_data["download"].get("download_dir", "").strip()
        config_data["download"]["download_dir"] = self._get_download_dir(download_dir)

        return Config(
            download=DownloadConfig(**config_data["download"]),
            paths=PathConfig(**config_data["paths"]),
            chrome=ChromeConfig(
                exec_path=ConfigManager._get_chrome_exec_path(config_data),
                profile_path=config_data["chrome"]["profile_path"],
            ),
        )

    def resolve_path(self, path, base_dir):
        """Resolve '~', add path with base_dir if input is not absolute path"""
        path = os.path.expanduser(path)
        return os.path.join(base_dir, path) if not os.path.isabs(path) else path

    @staticmethod
    def get_system_config_dir() -> Path:
        """Return the config directory"""
        if platform.system() == "Windows":
            base = os.getenv("APPDATA", "")
        else:
            base = os.path.expanduser("~/.config")
        return Path(base) / "v2dl"

    @staticmethod
    def get_default_download_dir() -> Path:
        return Path.home() / "Downloads"

    def _get_download_dir(self, download_dir: str) -> str:
        sys_dl_dir = ConfigManager.get_default_download_dir()
        result_dir = self.resolve_path(download_dir, sys_dl_dir) if download_dir else sys_dl_dir
        result_dir = Path(result_dir)
        result_dir.mkdir(parents=True, exist_ok=True)
        return str(result_dir)

    @staticmethod
    def _get_chrome_exec_path(config_data: dict) -> str:
        current_os = platform.system()
        exec_path = config_data["chrome"]["exec_path"].get(current_os)
        if not exec_path:
            raise ValueError(f"Unsupported OS: {current_os}")
        return exec_path

    @staticmethod
    def _merge_config(base: dict[str, Any], custom: dict[str, Any]) -> None:
        """Recursively merge custom config into base config."""
        for key, value in custom.items():
            if isinstance(value, dict) and key in base:
                ConfigManager._merge_config(base[key], value)
            else:
                base[key] = value

def parse_arguments():
    parser = argparse.ArgumentParser(description="Web scraper for albums and images.")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument(
        "--bot",
        dest="bot_type",
        default="drission",
        type=str,
        choices=["selenium", "drission"],
        required=False,
        help="Type of bot to use (default: drission)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    group.add_argument("-v", "--verbose", action="store_true", help="Verbose mode")
    group.add_argument(
        "--log-level", default=None, type=int, choices=range(1, 6), help="Set log level (1~5)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run without downloading")
    parser.add_argument("--terminate", action="store_true", help="Terminate chrome after scraping")
    args = parser.parse_args()

    if args.quiet:
        log_level = logging.ERROR
    elif args.verbose:
        log_level = logging.DEBUG
    elif args.log_level is not None:
        log_level_mapping = {
            1: logging.DEBUG,
            2: logging.INFO,
            3: logging.WARNING,
            4: logging.WARNING,
            5: logging.CRITICAL,
        }
        log_level = log_level_mapping[args.verbose]
    else:
        log_level = logging.INFO

    return args, log_level
