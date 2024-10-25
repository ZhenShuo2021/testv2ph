import logging
import os
import re
import time
import threading
from queue import Queue

from lxml import html

from .const import BASE_URL, XPATH_ALTS, XPATH_ALBUM, XPATH_ALBUM_LIST
from .config import Config, ConfigManager, parse_arguments
from .custom_logger import setup_logging
from .utils import LinkParser, download_album
from .web_bot import get_bot


class ScrapeManager:
    """Manage how to scrape the given URL"""

    def __init__(
        self,
        url: str,
        web_bot,
        dry_run: bool,
        config: Config,
        logger: logging.Logger,
    ):
        self.url = url
        self.path_parts, self.start_page = LinkParser.parse_input_url(url)

        self.web_bot = web_bot
        self.dry_run = dry_run
        self.config = config
        self.logger = logger

        # 初始化
        self.download_service = DownloadService(config, logger)
        self.link_scraper = LinkScraper(web_bot, dry_run, self.download_service, logger)
        self.album_tracker = AlbumTracker(config.paths.download_log)

        if not dry_run:
            self.download_service.start_workers()

    def start_scraping(self):
        album_list_name = {"actor", "company", "category", "country"}
        try:
            if "album" in self.path_parts:
                self.scrape_album(self.url)
            elif any(part in album_list_name for part in self.path_parts):
                self.scrape_album_list_page(self.url)
            else:
                raise ValueError(f"Unsupported URL type: {self.url}")
        finally:
            if not self.dry_run:
                self.download_service.wait_completion()
            self.web_bot.close_driver()

    def scrape_album_list_page(self, actor_url: str):
        """Scrape all albums in album list page"""
        album_links = self.link_scraper.scrape_link(actor_url, self.start_page, True)
        valid_album_links = [album_url for album_url in album_links if isinstance(album_url, str)]
        self.logger.info(f"Found {len(valid_album_links)} albums")

        for album_url in valid_album_links:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Album URL: {album_url}")
            else:
                self.scrape_album(album_url)

    def scrape_album(self, album_url: str):
        """Scrape a single album page"""
        if self.album_tracker.is_downloaded(album_url):
            self.logger.info(f"Album {album_url} already downloaded, skipping.")
            return

        image_links = self.link_scraper.scrape_link(album_url, self.start_page, False)
        if image_links:
            album_name = re.sub(r"\s*\d+$", "", image_links[0][1])
            self.logger.info(f"Found {len(image_links)} images in album {album_name}")

            if self.dry_run:
                for link, alt in image_links:
                    self.logger.info(f"[DRY RUN] Image URL: {link}")
            else:
                self.album_tracker.log_downloaded(album_url)


class LinkScraper:
    """Scrape logic"""

    def __init__(self, web_bot, dry_run: bool, download_service, logger: logging.Logger):
        self.web_bot = web_bot
        self.dry_run = dry_run
        self.download_service: DownloadService = download_service
        self.logger = logger

    def scrape_link(
        self, url: str, start_page: int, is_album_list: bool
    ) -> list[str] | list[tuple[str, str]]:
        """Scrape all pages after the given URL (not URLs).

        Args:
            url (str): URL to scrape, can be a album list page or a album page.
            is_album_list (bool): Check if the page is a album list page.

        Returns:
            page_result (list): A list of URL if is_album_list=True. Otherwise, returns a list of
            tuples consists of URL/filename.
        """
        self.logger.info(
            f"Starting to scrape {'album' if is_album_list else 'image'} links from {url}"
        )
        page_result = []
        page = start_page
        consecutive_page = 0
        alt_ctr = 0
        xpath_page_links = XPATH_ALBUM_LIST if is_album_list else XPATH_ALBUM

        while True:
            full_url = LinkParser.add_page_num(url, page)
            html_content = self.web_bot.auto_page_scroll(full_url)
            tree = LinkParser.parse_html(html_content, self.logger)
            if tree is None:
                break

            self.logger.info(f"Fetching content from {full_url}")
            page_links = tree.xpath(xpath_page_links)
            if not page_links:
                self.logger.info(
                    f"No more {'albums' if is_album_list else 'images'} found on page {page}"
                )
                break

            if is_album_list:
                self._process_album_list_links(page_links, page_result, page)
            else:
                self._process_album_image_links(page_links, page_result, alt_ctr, tree, page)

            if page >= LinkParser.get_max_page(tree):
                self.logger.info("Reached last page, stopping")
                break

            page += 1
            consecutive_page += 1
            if consecutive_page == 3:
                consecutive_page = 0
                time.sleep(15)

        return page_result

    def _process_album_list_links(
        self,
        page_links: list[str],
        page_result: list[str],
        page: int,
    ):
        """Process and collect album URLs from list page"""
        page_result.extend([BASE_URL + album_link for album_link in page_links])
        self.logger.info(f"Found {len(page_links)} images on page {page}")

    def _process_album_image_links(
        self,
        page_links: list[str],
        page_result: list[tuple[str, str]],
        alt_ctr: int,
        tree: html.HtmlElement,
        page: int,
    ):
        """Handle image links extraction and queueing for download"""
        alts: list[str] = tree.xpath(XPATH_ALTS)

        if len(alts) < len(page_links):
            missing_alts = [str(i + alt_ctr) for i in range(len(page_links) - len(alts))]
            alts.extend(missing_alts)
            alt_ctr += len(missing_alts)

        page_result.extend(zip(page_links, alts))

        # Download file
        if not self.dry_run:
            album_name = self.extract_album_name(alts)
            image_links = list(zip(page_links, alts))
            self.download_service.add_download_task(album_name, image_links)  # add task to queue
        self.logger.info(f"Found {len(page_links)} images on page {page}")

    @staticmethod
    def extract_album_name(alts: list[str]) -> str:
        # Find the first non-digits element
        album_name = next((alt for alt in alts if not alt.isdigit()), None)
        if album_name:  # remove postfix digits and spaces
            album_name = re.sub(r"\s*\d*$", "", album_name).strip()
        if not album_name:  # empty string check
            album_name = BASE_URL.rstrip("/").split("/")[-1]
        return album_name


class AlbumTracker:
    """Download log in units of albums"""

    def __init__(self, download_log: str):
        self.album_log_path = download_log

    def is_downloaded(self, album_url: str) -> bool:
        if os.path.exists(self.album_log_path):
            with open(self.album_log_path, "r") as f:
                downloaded_albums = f.read().splitlines()
            return album_url in downloaded_albums
        return False

    def log_downloaded(self, album_url: str):
        album_url = LinkParser.remove_page_num(album_url)
        if not self.is_downloaded(album_url):
            with open(self.album_log_path, "a") as f:
                f.write(album_url + "\n")


class DownloadService:
    """Initialize multiple threads with a queue for downloading."""

    def __init__(self, config: Config, logger: logging.Logger, num_workers: int = 1):
        self.download_queue = Queue()
        self.config = config
        self.logger = logger
        self.num_workers = num_workers  # one worker is enough, too many workers would be blocked
        self.worker_threads = []

    def start_workers(self):
        """Start up multiple worker threads to listen download needs"""
        for _ in range(self.num_workers):
            worker = threading.Thread(target=self._download_worker, daemon=True)
            self.worker_threads.append(worker)
            worker.start()

    def _download_worker(self):
        """Worker function to process downloads from the queue"""
        dest = self.config.download.download_dir
        rate = self.config.download.rate_limit
        while True:  # run until receiving exit signal
            album_name, page_image_links = self.download_queue.get()  # get job from queue
            if album_name is None:
                break  # exit signal received
            download_album(album_name, page_image_links, dest, rate, self.logger)
            self.download_queue.task_done()

    def add_download_task(self, album_name: str, image_links: list[tuple[str, str]]):
        """Add task to queue"""
        self.download_queue.put((album_name, image_links))

    def wait_completion(self):
        """Block until all tasks are done and stop all workers."""
        self.download_queue.join()  # Block until all tasks are done.

        # Signal all workers to exit
        for _ in range(self.num_workers):
            self.download_queue.put((None, None))

        # Wait for all worker threads to finish
        for worker in self.worker_threads:
            worker.join()


class ScrapeError(Exception):
    pass


class FileProcessingError(Exception):
    pass


class DownloadError(Exception):
    pass


def main():
    args, log_level = parse_arguments()
    config = ConfigManager().load()
    setup_logging(log_level, log_path=config.paths.system_log)
    logger = logging.getLogger(__name__)

    web_bot = get_bot(args.bot_type, config, args.terminate, logger)
    scraper = ScrapeManager(args.url, web_bot, args.dry_run, config, logger)
    scraper.start_scraping()
