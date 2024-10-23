import os
import sys

import time
import random
import subprocess

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)
from subprocess import Popen

from .base import BaseBot, BaseBehavior, BaseScroll
from ..const import SELENIUM_AGENT


class SeleniumBot(BaseBot):
    def __init__(self, config, close_browser, logger):
        super().__init__(config, close_browser, logger)
        self.init_driver()
        self.scroller = SelScroll(self.driver, self.config, self.logger)
        self.cloudflare = SelCloudflareHandler(self.driver, self.logger)

    def init_driver(self):
        self.driver: WebDriver
        self.chrome_process: Popen
        options = Options()

        user_data_dir = self.config.paths.profile
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)
            self.new_profile = True
        else:
            self.new_profile = False

        chrome_path = self.config.get_chrome_path()
        subprocess_cmd = [
            chrome_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--disable-infobars",
            "--disable-extensions",
            "--start-maximized",
        ]
        self.chrome_process = subprocess.Popen(subprocess_cmd)

        options.add_argument(SELENIUM_AGENT)
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument("--no-sandbox")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        try:
            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
            service = (
                Service(chromedriver_path)
                if chromedriver_path and os.path.exists(chromedriver_path)
                else Service()
            )
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            self.logger.critical(f"無法啟動 Selenium WebDriver: {e}")
            sys.exit("無法啟動 Selenium WebDriver")

        # width = random.randint(1024, 1920)
        # height = random.randint(768, 1080)
        self.driver.set_window_size(1920, 1080)

    def close_driver(self):
        if self.close_browser:
            self.driver.quit()
            self.chrome_process.terminate()

    def auto_page_scroll(
        self, url: str, max_retry: int = 3, page_sleep: int = 5, fast_scroll: bool = False
    ) -> str:
        """
        Scroll page automatically with retries and Cloudflare challenge handle.

        The main function of this class.

        Args:
            url (str): Target URL
            max_retry (int): Maximum number of retry attempts. Defaults to 3
            page_sleep (int): The sleep time after reaching page bottom
            fast_scroll (bool): Whether to use fast scroll. Might be blocked by Cloudflare

        Returns:
            str: Page HTML content or error message
        """
        response: str = ""
        for attempt in range(max_retry):
            try:
                self.driver.get(url)
                SelBehavior.random_sleep(0.1, 0.5)

                if not self.handle_redirection_fail(url, max_retry, 5):
                    self.logger.error(
                        f"Unable to solve redirection fail. Attempt {attempt + 1}/{max_retry}"
                    )
                    continue

                if self.cloudflare.handle_simple_block(attempt, max_retry):
                    continue

                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.album-photo.my-2"))
                )

                # 主業務
                self.handle_login()
                self.scroller.scroll_to_bottom()
                SelBehavior.random_sleep(5, 15)

                response = self.driver.page_source
                break

            except TimeoutException:
                self.logger.warning(
                    f"Timeout occurred. Retrying... Attempt {attempt + 1}/{max_retry}"
                )
            except WebDriverException as e:
                self.logger.error(
                    f"WebDriver error occurred: {e}. Retrying... Attempt {attempt + 1}/{max_retry}"
                )

            self.logger.debug("捲動結束，暫停作業避免封鎖。")
            SelBehavior.random_sleep(page_sleep, page_sleep + 5)

        if not response:
            error_msg = f"Failed to retrieve URL after {max_retry} attempts: '{url}'"
            response = error_msg
            self.logger.error(error_msg)
        return response

    def handle_redirection_fail(self, url: str, max_retry: int, sleep_time: int) -> bool:
        if self.driver.current_url == url:
            return True
        retry = 1
        while retry <= max_retry:
            self.logger.error(f"Connection failed - Attempt {retry + 1}/{max_retry}")
            SelBehavior.random_sleep(sleep_time, sleep_time + 5 * random.uniform(1, retry * 5))

            if self.cloudflare.handle_simple_block(retry, max_retry):
                self.logger.critical("Failed to solve Cloudflare turnstile challenge")
                continue

            self.driver.get(url)
            retry += 1
            if self.driver.current_url == url:
                return True

        return self.driver.current_url == url

    def handle_login(self):
        success = False
        if "用戶登錄" in self.driver.page_source:
            self.logger.info("Login page detected - Starting login process")
            try:
                email_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "email"))
                )
                BaseBehavior.random_sleep(0.1, 0.3)
                password_field = self.driver.find_element(By.ID, "password")

                SelBehavior.human_like_mouse_movement(self.driver, email_field)
                SelBehavior.human_like_click(self.driver, email_field)
                SelBehavior.human_like_type(email_field, self.email)
                BaseBehavior.random_sleep(0.01, 0.3)

                SelBehavior.human_like_mouse_movement(self.driver, password_field)
                SelBehavior.human_like_click(self.driver, email_field)
                SelBehavior.human_like_type(password_field, self.password)
                BaseBehavior.random_sleep(0.01, 0.5)

                # try:
                #     remember_checkbox = self.driver.find_element(By.ID, "remember")
                #     if not remember_checkbox.is_selected():
                #         SelBehavior.human_like_click(self.driver, remember_checkbox)
                # except NoSuchElementException:
                #     self.logger.warning("Remember me checkbox not found")

                try:
                    self.cloudflare.handle_cloudflare_recaptcha()
                except Exception as e:
                    self.logger.error(f"Error handling Cloudflare reCAPTCHA: {e}")

                try:
                    login_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '登錄')]"))
                    )
                    SelBehavior.human_like_click(self.driver, login_button)
                except TimeoutException:
                    self.logger.error("Login button not clickable")
                    raise

                SelBehavior.random_sleep(3, 5)

                if "用戶登錄" not in self.driver.page_source:
                    self.logger.info("Login successful")
                    success = True
                else:
                    self.logger.error("Login failed - Checking for error messages")
                    self.check_login_errors()

            except NoSuchElementException as e:
                self.logger.error(f"Login form element not found: {str(e)}")
            except TimeoutException as e:
                self.logger.error(f"Timeout waiting for element: {str(e)}")
            except Exception as e:
                self.logger.error(f"Unexpected error during login: {str(e)}")
        else:
            success = True
        if not success:
            self.logger.critical("Automated login failed. Please login yourself.")
            sys.exit("Automated login failed.")

    def check_login_errors(self):
        error_messages = self.driver.find_elements(By.CLASS_NAME, "alert-danger")
        if error_messages:
            for message in error_messages:
                self.logger.error(f"Login error: {message.text}")
        else:
            self.logger.warning(
                "No specific error message found. Login might have failed for unknown reasons."
            )


class SelCloudflareHandler:
    """
    Handles Cloudflare protection detection and bypass attempts.
    Includes methods for dealing with various Cloudflare challenges.
    """

    def __init__(self, driver: WebDriver, logger):
        self.driver = driver
        self.logger = logger

    def handle_simple_block(self, attempt: int, retries: int) -> bool:
        """check and handle Cloudflare challenge"""
        blocked = False
        if self.is_simple_blocked():
            self.logger.info(
                f"Detected Cloudflare challenge, attempting to solve... Attempt {attempt + 1}/{retries}"
            )
            self.handle_cloudflare_turnstile()
            blocked = True
        return blocked

    def handle_hard_block(self) -> bool:
        """Check, log critical, and return whether blocked or not (This is a cloudflare WAF block)"""
        blocked = False
        if self.is_hard_block():
            self.logger.critical("Hard block detected by Cloudflare - Unable to proceed")
            blocked = True
        return blocked

    def is_simple_blocked(self) -> bool:
        """check if blocked by Cloudflare"""
        title_check = any(text in self.driver.title for text in ["請稍候...", "Just a moment..."])
        page_source_check = "Checking your" in self.driver.page_source
        return title_check or page_source_check

    def is_hard_block(self) -> bool:
        is_blocked = "Attention Required! | Cloudflare" in self.driver.title
        if is_blocked:
            self.logger.critical("Cloudflare hard block detected")
        return is_blocked

    def handle_cloudflare_turnstile(self):
        try:
            iframe = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//iframe[contains(@src, 'challenges.cloudflare.com')]")
                )
            )
            self.driver.switch_to.frame(iframe)

            checkbox = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "cf-turnstile-response"))
            )
            SelBehavior.human_like_click(self.driver, checkbox)

            if "Select all squares with" in self.driver.page_source:
                self.solve_image_captcha()

            self.driver.switch_to.default_content()
            SelBehavior.random_sleep(10, 20)
        except (TimeoutException, NoSuchElementException):
            self.logger.error("Unable to solve Cloudflare challenge.")

    def handle_cloudflare_recaptcha(self):
        try:
            recaptcha_checkbox = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
            )
            SelBehavior.human_like_click(self.driver, recaptcha_checkbox)

            verify_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), '驗證您是人類')]"))
            )
            SelBehavior.human_like_click(self.driver, verify_button)

            SelBehavior.random_sleep(3, 5)
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.warning(
                f"reCAPTCHA checkbox or verify button not found or unable to interact: {e}"
            )

    def solve_image_captcha(self):
        raise NotImplementedError


class SelBehavior(BaseBehavior):
    @staticmethod
    def human_like_mouse_movement(driver, element):
        action = ActionChains(driver)
        action.move_by_offset(random.randint(-100, 100), random.randint(-100, 100))
        action.move_to_element_with_offset(
            element, random.randint(-10, 10), random.randint(-10, 10)
        )
        action.pause(random.uniform(0.1, 0.3))
        action.move_to_element(element)
        action.perform()
        SelBehavior.random_sleep(*BaseBehavior.pause_time)

    @staticmethod
    def human_like_click(driver, element):
        SelBehavior.human_like_mouse_movement(driver, element)
        action = ActionChains(driver)
        action.click()
        action.perform()
        SelBehavior.random_sleep(*BaseBehavior.pause_time)

    @staticmethod
    def human_like_type(element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.001, 0.2))
        SelBehavior.random_sleep(*BaseBehavior.pause_time)


class SelScroll(BaseScroll):
    def __init__(self, driver: WebDriver, config, logger):
        super().__init__(config, logger)
        self.driver = driver

    def scroll_to_bottom(self):
        self.logger.info("開始捲動頁面")
        scroll_attempts = 0
        max_attempts = 45

        scroll_pos_init = self.driver.execute_script("return window.pageYOffset;")
        step_scroll = random.randint(
            self.config.download.min_scroll_length,
            self.config.download.max_scroll_length,
        )

        while scroll_attempts < max_attempts:
            scroll_attempts += 1

            self.driver.execute_script(f"window.scrollBy(0, {step_scroll});")
            scroll_pos_end = self.driver.execute_script("return window.pageYOffset;")
            time.sleep(0.75)

            if scroll_pos_init >= scroll_pos_end:
                self.logger.debug("已到達頁面底部")
                break

            scroll_pos_init = scroll_pos_end

            step_scroll = random.randint(
                self.config.download.min_scroll_length, self.config.download.max_scroll_length
            )

            self.wait_for_content_load()

            self.continuous_scroll_count += 1
            if self.continuous_scroll_count >= self.max_continuous_scrolls:
                pause_time = random.uniform(3, 7)
                self.logger.debug(
                    f"連續捲動 {self.continuous_scroll_count} 次，暫停 {pause_time:.2f} 秒"
                )
                time.sleep(pause_time)
                self.continuous_scroll_count = 0
                self.max_continuous_scrolls = random.randint(3, 7)

        if scroll_attempts == max_attempts:
            self.logger.info(f"捲動結束，達到最大嘗試次數 ({max_attempts})，可能未完全捲動到底")
        else:
            self.logger.info("頁面捲動完成")

    def perform_scroll_action(self):
        action = random.choices(
            ["scroll_down", "scroll_up", "pause", "jump"],
            weights=[0.7, 0.1, 0.1, 0.1],
        )[0]

        current_position = self.get_scroll_position()

        if action == "scroll_down":
            scroll_length = random.randint(
                self.config.download.min_scroll_length,
                self.config.download.max_scroll_length,
            )
            target_position = current_position + scroll_length
            self.logger.debug(f"嘗試向下捲動 {scroll_length} 像素")
            actual_position = self.safe_scroll(target_position)
            self.logger.debug(f"實際捲動到 {actual_position} 像素")
            time.sleep(random.uniform(*BaseBehavior.pause_time))
        elif action == "scroll_up":
            scroll_length = random.randint(
                self.config.download.min_scroll_length,
                self.config.download.max_scroll_length,
            )
            target_position = max(0, current_position - scroll_length)
            self.logger.debug(f"嘗試向上捲動 {scroll_length} 像素")
            actual_position = self.safe_scroll(target_position)
            self.logger.debug(f"實際捲動到 {actual_position} 像素")
        elif action == "pause":
            pause_time = random.uniform(1, 3)
            self.logger.debug(f"暫停 {pause_time:.2f} 秒")
            time.sleep(pause_time)
        elif action == "jump":
            jump_position = current_position + random.randint(100, 500)
            self.logger.debug(f"嘗試跳轉到位置 {jump_position}")
            actual_position = self.safe_scroll(jump_position)
            self.logger.debug(f"實際跳轉到 {actual_position} 像素")

    def safe_scroll(self, target_position):
        current_position = self.get_scroll_position()
        step = random.uniform(
            self.config.download.min_scroll_step,
            self.config.download.max_scroll_step,
        )
        # step = 50 if target_position > current_position else -50
        # while abs(current_position - target_position) > abs(step):

        while abs(current_position - target_position) > step:
            self.driver.execute_script(f"window.scrollTo(0, {current_position + step});")
            time.sleep(random.uniform(0.01, 0.2))
            new_position = self.get_scroll_position()
            if new_position == current_position:
                self.logger.debug(
                    f"無法繼續捲動，目標: {target_position}，當前: {current_position}"
                )
                break
            current_position = new_position
        self.driver.execute_script(f"window.scrollTo(0, {target_position});")
        return self.get_scroll_position()

    def get_scroll_position(self):
        return self.driver.execute_script("return window.pageYOffset")

    def get_page_height(self):
        return self.driver.execute_script("return document.body.scrollHeight")

    def wait_for_content_load(self):
        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            self.logger.warning("等待新內容加載超時")
