import argparse
import logging
import os
import re
import threading
from queue import Queue
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from lxml import html

from .bot import CloudflareBypass, HumanLikeBehavior
from .const import ALBUM_LOG_FILE, BASE_URL, DOWNLOAD_DIR, DRY_RUN_MSG
from .custom_logger import setup_logging
from .utils import download_images, parse_content, parse_max_page, get_full_url, remove_page_param

XPATH_ALTS = '//div[@class="album-photo my-2"]/img/@alt'
XPATH_ALBUM = '//div[@class="album-photo my-2"]/img/@data-src'
XPATH_ALBUM_LIST = '//a[@class="media-cover"]/@href'

# Queue for download tasks
download_queue = Queue()


class Scraper:
    def __init__(self, url: str, dry_run: bool, logger: logging.Logger, terminate: bool = True):
        self.url: str = url
        parsed_url = urlparse(url)
        self.path_parts: list[str] = parsed_url.path.split("/")
        query_params = parse_qs(parsed_url.query)
        self.start_page: int = int(query_params.get("page", [1])[0])  # default page=1

        self.destination: str = DOWNLOAD_DIR
        self.dry_run: bool = dry_run
        self.terminate: bool = terminate
        self.cf_bypass: CloudflareBypass = CloudflareBypass(logger)
        self.logger = logger

    def scrape_start(self):
        try:
            if self.path_parts[1] == "album":
                self.scrape_album(self.url)
            elif self.path_parts[1] in {"actor", "company", "category", "country"}:
                self.scrape_album_list(self.url)
            else:
                raise ValueError(f"Unsupported URL type: {self.url}")
        finally:
            self.cf_bypass.close_driver()
            if self.terminate:
                self.cf_bypass.chrome_process.terminate()

    def scrape_album_list(self, actor_url: str):
        """Scrape albums in album list page"""
        album_links = self.scrape_link(actor_url, is_album_list=True)
        valid_album_links = [album_url for album_url in album_links if isinstance(album_url, str)]
        self.logger.info(f"Found {len(valid_album_links)} albums")

        for album_url in valid_album_links:
            if self.dry_run:
                self.logger.info(f"{DRY_RUN_MSG} Album URL: {album_url}")
            else:
                self.scrape_album(album_url)

    def scrape_album(self, album_url: str):
        if self.is_album_downloaded(album_url):
            self.logger.info(f"Album {album_url} already downloaded, skipping.")
            return

        image_links = self.scrape_link(album_url, is_album_list=False)
        if image_links:
            album_name = re.sub(r"\s*\d+$", "", image_links[0][1])  # remove postfix digits
            self.logger.info(f"Found {len(image_links)} images in album {album_name}")
            if self.dry_run:
                for link, alt in image_links:
                    self.logger.info(f"{DRY_RUN_MSG} Image URL: {link}")
            else:
                self.log_downloaded_album(album_url)  # Log after download

    def scrape_link(self, url: str, is_album_list: bool) -> list[str] | list[tuple[str, str]]:
        """Download and return links

        Args:
            url (str): url to scrape, can be a album list page or a album page.
            is_album_list (bool): check if the page is a album list page.

        Returns:

        """
        self.logger.info(
            f"Starting to scrape {'album' if is_album_list else 'image'} links from {url}"
        )
        image_links = []
        page = self.start_page
        alt_ctr = 0
        xpath_page_links = XPATH_ALBUM_LIST if is_album_list else XPATH_ALBUM

        while True:
            full_url = get_full_url(url, page)
            html_content = self.cf_bypass.selenium_retry_request(full_url, retries=3, sleep_time=5)
            tree = parse_content(html_content, self.logger)
            self.logger.info(f"Fetching content from {full_url}")

            if tree is None:
                self.logger.warning(f"Failed to get content from {full_url}")
                break

            page_links = tree.xpath(xpath_page_links)
            if not page_links:
                self.logger.info(
                    f"No more {'albums' if is_album_list else 'images'} found on page {page}"
                )
                break

            self.process_links(is_album_list, page_links, alt_ctr, image_links, tree, page)

            if page >= parse_max_page(tree):
                self.logger.info("Reached last page, stopping")
                break

            page += 1
            HumanLikeBehavior.random_sleep()

        self.logger.info(
            f"Scraping completed, found {len(image_links)} {'album' if is_album_list else 'image'} links"
        )
        return image_links

    def process_links(
        self,
        is_album_list: bool,
        page_links: list[str],
        alt_ctr: int,
        links: list[str] | list[tuple[str, str]],
        tree: html.HtmlElement,
        page: int,
    ):
        """Process found links: log or queue downloads."""

        # If scraping an album list page, returns a list of album urls
        if is_album_list:
            links.extend([BASE_URL + album_link for album_link in page_links])  # type: ignore
            self.logger.info(f"Found {len(page_links)} albums on page {page}")

        # Scraping an album page, return a list of tuple, each tuple consists of image url and file name
        else:
            alts: list[str] = tree.xpath(XPATH_ALTS)

            # process for missing alts
            if len(alts) < len(page_links):
                missing_alts = [str(i + alt_ctr) for i in range(len(page_links) - len(alts))]
                alts.extend(missing_alts)
                alt_ctr += len(missing_alts)

            links.extend(zip(page_links, alts))  # type: ignore
            self.logger.info(f"Found {len(page_links)} images on page {page}")

            if not self.dry_run:
                page_image_links = list(zip(page_links, alts))
                album_name = re.sub(r"\s*\d+$", "", page_image_links[0][1])
                download_queue.put((album_name, page_image_links))  # Add task to queue

    def is_album_downloaded(self, album_url: str) -> bool:
        """Check if the album has been downloaded"""
        if os.path.exists(ALBUM_LOG_FILE):
            with open(ALBUM_LOG_FILE, "r") as f:
                downloaded_albums = f.read().splitlines()
            return album_url in downloaded_albums
        return False

    def log_downloaded_album(self, album_url: str):
        """Log the downloaded album URL"""
        album_url = remove_page_param(album_url)
        with open(ALBUM_LOG_FILE, "a") as f:
            f.write(album_url + "\n")


def download_worker(logger):
    """Worker function to process downloads from the queue"""
    while True:  # run until receiving exit signal
        album_name, page_image_links = download_queue.get()  # get job from queue
        if album_name is None:
            break  # exit signal received
        download_images(album_name, page_image_links, DOWNLOAD_DIR, logger)
        download_queue.task_done()


def main():
    parser = argparse.ArgumentParser(description="Web scraper for albums and images.")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without downloading")
    parser.add_argument("--terminate", action="store_true", help="Terminate chrome after scraping")
    args = parser.parse_args()

    # Initialize logger
    setup_logging(logging.INFO)
    logger = logging.getLogger(__name__)

    # Download worker thread start listening
    download_thread = threading.Thread(target=download_worker, args=(logger,), daemon=True)
    download_thread.start()

    # Start scrolling and downloading
    scraper = Scraper(args.url, args.dry_run, logger, args.terminate)
    scraper.scrape_start()

    # Block until all tasks are done.
    download_queue.join()

    # Signal the worker to exit
    download_queue.put((None, None))


if __name__ == "__main__":
    main()
