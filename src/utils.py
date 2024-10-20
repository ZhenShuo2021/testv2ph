import logging
import re
import requests
import time
from pathlib import Path

from lxml import html
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from .const import HEADERS, RATE_LIMIT


def parse_content(html_content: str, logger: logging.Logger) -> html.HtmlElement | None:
    if "Failed" in html_content:
        return None

    try:
        return html.fromstring(html_content)
    except Exception as e:
        logger.error(f"Error parsing HTML content: {e}")
        return None


def parse_max_page(tree: html.HtmlElement) -> int:
    """Parse pagination count"""
    page_links = tree.xpath(
        '//li[@class="page-item"]/a[@class="page-link" and string-length(text()) <= 2]/@href'
    )

    if not page_links:
        return 1

    page_numbers = []
    for link in page_links:
        match = re.search(r"page=(\d+)", link)
        if match:
            page_number = int(match.group(1))
        else:
            page_number = 1
        page_numbers.append(page_number)

    return max(page_numbers)


def get_full_url(url: str, page: int) -> str:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    query_params["page"] = [str(page)]

    new_query = urlencode(query_params, doseq=True)
    new_url = parsed_url._replace(query=new_query)
    return urlunparse(new_url)  #'https://www.v2ph.com/album/YTY-7173?page=1'


def remove_page_param(url: str) -> str:
    """remove ?page=d or &page=d from URL"""
    # Parse the URL
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # Remove the 'page' parameter if it exists
    if "page" in query_params:
        del query_params["page"]

    # Rebuild the query string without 'page'
    new_query = urlencode(query_params, doseq=True)

    # Rebuild the full URL
    new_url = urlunparse(parsed_url._replace(query=new_query))
    return new_url


def download_images(album_name, image_links, destination, logger):
    folder = destination / Path(album_name)
    folder.mkdir(parents=True, exist_ok=True)

    for url, alt in image_links:
        print(alt)
        filename = re.sub(r'[<>:"/\\|?*]', "", alt)  # Remove invalid characters
        file_path = folder / f"{filename}.jpg"

        if file_path.exists():
            logger.info(f"File already exists: '{file_path}'")
            continue

        # requests module will log download url
        if download_file(url, file_path, logger):
            pass


def download_file(url: str, save_path: Path, logger: logging.Logger) -> bool:
    """
    Error control subfunction for download files.

    Return `True` for successful download, else `False`.
    """
    try:
        download_with_speed_limit(url, save_path, RATE_LIMIT)
        logger.info(f"Downloaded: '{save_path}'")
        return True
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return False
    except Exception as err:
        logger.error(f"An error occurred: {err}")
        return False


def download_with_speed_limit(url: str, save_path: Path, speed_limit_kbps: int = 1536) -> None:
    """
    Download with speed limit function.

    Default speed limit is 1536 KBps (1.5 MBps).
    """

    chunk_size = 1024  # 1 KB
    speed_limit_bps = speed_limit_kbps * 1024  # 轉換為 bytes per second

    response = requests.get(url, stream=True, headers=HEADERS)
    response.raise_for_status()  # 確認請求成功

    with open(save_path, "wb") as file:
        start_time = time.time()
        downloaded = 0

        for chunk in response.iter_content(chunk_size=chunk_size):
            file.write(chunk)
            downloaded += len(chunk)

            elapsed_time = time.time() - start_time
            expected_time = downloaded / speed_limit_bps

            if elapsed_time < expected_time:
                time.sleep(expected_time - elapsed_time)
