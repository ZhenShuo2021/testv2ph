import platform
from dataclasses import dataclass

import yaml


@dataclass(slots=True, frozen=True)
class DownloadConfig:
    min_scroll_length: int
    max_scroll_length: int
    min_scroll_step: int
    max_scroll_step: int
    rate_limit: int
    download_dir: str


@dataclass(slots=True, frozen=True)
class PathConfig:
    profile: str
    album_log: str
    log_dir: str


@dataclass(slots=True, frozen=True)
class ChromePathsConfig:
    Linux: str
    Darwin: str
    Windows: str


@dataclass
class Config:
    download: DownloadConfig
    paths: PathConfig
    chrome_paths: ChromePathsConfig

    def get_chrome_path(self) -> str:
        current_os = platform.system()
        return getattr(self.chrome_paths, current_os)


def load_config(yaml_path: str) -> Config:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return Config(
        download=DownloadConfig(**data["download"]),
        paths=PathConfig(**data["paths"]),
        chrome_paths=ChromePathsConfig(**data["chrome"]["paths"]),
    )
