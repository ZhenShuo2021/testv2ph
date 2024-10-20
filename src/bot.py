import os

os.environ["CHROMEDRIVER_PATH"] = "./chromedriver"

import time
import platform
import random
import subprocess

from dotenv import load_dotenv
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
from .const import (
    PROFILE_PATH,
    MIN_SCROLL_LENGTH,
    MAX_SCROLL_LENGTH,
    MIN_SCROLL_STEP,
    MAX_SCROLL_STEP,
)


class CloudflareBypass:
    def __init__(self, logger):
        self.logger = logger
        self.driver: WebDriver
        self.chrome_process: Popen
        self.driver, self.chrome_process = self.init_driver()
        self.scroller = ScrollBehavior(self.driver, self.logger)
        load_dotenv()
        self.email = os.getenv("USERNAME")
        self.password = os.getenv("PASSWORD")

    def init_driver(self):
        options = Options()

        os.makedirs(PROFILE_PATH, exist_ok=True)
        user_data_dir = os.path.join(os.getcwd(), PROFILE_PATH)

        CHROME_PATHS = {
            "Linux": "/usr/bin/google-chrome",
            "Darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", 
            "Windows": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        }
        chrome_path = CHROME_PATHS[platform.system()]
        subprocess_cmd = [
            chrome_path,
            "--remote-debugging-port=9222", 
            f"--user-data-dir={user_data_dir}",
            "--disable-infobars",
            "--disable-extensions",
            "--start-maximized",
        ]
        chrome_process = subprocess.Popen(subprocess_cmd)

        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-gpu")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.59 Safari/537.36"
        )

        try:
            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
            service = (
                Service(chromedriver_path)
                if chromedriver_path and os.path.exists(chromedriver_path)
                else Service()
            )
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            self.logger.error(f"無法啟動 Selenium WebDriver: {e}")
            raise e

        width = random.randint(1024, 1920)
        height = random.randint(768, 1080)
        driver.set_window_size(width, height)
        return driver, chrome_process

    def close_driver(self):
        if self.driver is not None:
            self.driver.quit()
            self.driver = None  # type: ignore

    def selenium_retry_request(self, url: str, retries: int = 3, sleep_time: int = 5) -> str:
        response = ""
        for attempt in range(retries):
            try:
                self.driver.get(url)
                HumanLikeBehavior.random_sleep(3, 5)

                # 等到body載入後才開始行動
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )

                # 確認是否被cloudflare封鎖並且處理
                if self.handle_cloudflare(attempt, retries):
                    continue

                # 主業務
                self.scroller.scroll_page()
                # self.handle_login()
                HumanLikeBehavior.random_sleep(5, 15)

                response = self.driver.page_source
                break

            except TimeoutException:
                self.logger.warning(
                    f"Timeout occurred. Retrying... Attempt {attempt + 1}/{retries}"
                )
            except WebDriverException as e:
                self.logger.error(
                    f"WebDriver error occurred: {e}. Retrying... Attempt {attempt + 1}/{retries}"
                )

            self.logger.debug("捲動結束，暫停作業避免封鎖。")
            HumanLikeBehavior.random_sleep(sleep_time, sleep_time + 5)

        if not response:
            error_msg = f"Failed to retrieve URL after {retries} attempts: '{url}'"
            response = error_msg
            self.logger.error(error_msg)
        return response

    def handle_login(self):
        if "用戶登錄" in self.driver.page_source:
            self.logger.info("Login page detected. Attempting to log in.")
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "email"))
                )

                email_field = self.driver.find_element(By.ID, "email")
                password_field = self.driver.find_element(By.ID, "password")

                HumanLikeBehavior.human_like_mouse_movement(self.driver, email_field)
                HumanLikeBehavior.human_like_type(email_field, self.email)

                HumanLikeBehavior.human_like_mouse_movement(self.driver, password_field)
                HumanLikeBehavior.human_like_type(password_field, self.password)

                remember_checkbox = self.driver.find_element(By.ID, "remember-me")
                HumanLikeBehavior.human_like_click(self.driver, remember_checkbox)

                self.handle_cloudflare_recaptcha()

                login_button = self.driver.find_element(
                    By.XPATH, "//button[contains(text(), '登錄')]"
                )
                HumanLikeBehavior.human_like_click(self.driver, login_button)

                HumanLikeBehavior.random_sleep(3, 5)

                if "用戶登錄" not in self.driver.page_source:
                    self.logger.info("Login successful.")
                else:
                    self.logger.error("Login failed. Checking for error messages.")
                    self.check_login_errors()

            except NoSuchElementException as e:
                self.logger.error(f"Login form element not found: {e}")
            except Exception as e:
                self.logger.error(f"An error occurred during login: {e}")

    def handle_cloudflare(self, attempt: int, retries: int) -> bool:
        """檢測並處理 Cloudflare 挑戰"""
        blocked = False
        if self.is_cloudflare_blocked():
            self.logger.info(
                f"Detected Cloudflare challenge, attempting to solve... Attempt {attempt + 1}/{retries}"
            )
            self.handle_cloudflare_turnstile()
            blocked = True
        return blocked

    def is_cloudflare_blocked(self) -> bool:
        """檢測是否被 Cloudflare 封鎖"""
        title_check = any(text in self.driver.title for text in ["請稍候...", "Just a moment..."])
        page_source_check = "Checking your" in self.driver.page_source
        return title_check or page_source_check

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
            HumanLikeBehavior.human_like_click(self.driver, checkbox)

            if "Select all squares with" in self.driver.page_source:
                self.solve_image_captcha()

            self.driver.switch_to.default_content()
            HumanLikeBehavior.random_sleep(5, 10)
        except (TimeoutException, NoSuchElementException):
            self.logger.error("Unable to solve Cloudflare challenge.")

    def handle_cloudflare_recaptcha(self):
        try:
            recaptcha_checkbox = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
            )
            HumanLikeBehavior.human_like_click(self.driver, recaptcha_checkbox)

            verify_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), '驗證您是人類')]"))
            )
            HumanLikeBehavior.human_like_click(self.driver, verify_button)

            HumanLikeBehavior.random_sleep(3, 5)
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.warning(
                f"reCAPTCHA checkbox or verify button not found or unable to interact: {e}"
            )

    def check_login_errors(self):
        error_messages = self.driver.find_elements(By.CLASS_NAME, "alert-danger")
        if error_messages:
            for message in error_messages:
                self.logger.error(f"Login error: {message.text}")
        else:
            self.logger.warning(
                "No specific error message found. Login might have failed for unknown reasons."
            )

    def solve_image_captcha(self):
        raise NotImplementedError


class HumanLikeBehavior:
    @staticmethod
    def random_sleep(min_time=1.0, max_time=5.0):
        time.sleep(random.uniform(min_time, max_time))

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
        HumanLikeBehavior.random_sleep(0.5, 1.5)

    @staticmethod
    def human_like_click(driver, element):
        HumanLikeBehavior.human_like_mouse_movement(driver, element)
        action = ActionChains(driver)
        action.click()
        action.perform()
        HumanLikeBehavior.random_sleep(0.5, 1.5)

    @staticmethod
    def human_like_type(element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
        HumanLikeBehavior.random_sleep(0.5, 1.5)


class ScrollBehavior:
    def __init__(self, driver, logger):
        self.driver = driver
        self.logger = logger
        self.scroll_position = 0
        self.last_content_height = 0
        self.continuous_scroll_count = 0
        self.max_continuous_scrolls = random.randint(5, 10)

    def scroll_page(self):
        self.logger.info("開始捲動頁面")
        scroll_attempts = 0
        max_attempts = 30
        same_position_count = 0
        last_position = 0

        while scroll_attempts < max_attempts:
            scroll_attempts += 1

            current_position = self.get_scroll_position()
            page_height = self.get_page_height()

            if current_position == last_position:
                same_position_count += 1
                if same_position_count >= 3:
                    self.logger.debug(
                        f"連續三次偵測到相同位置，停止捲動。總共捲動 {scroll_attempts} 次"
                    )
                    break
            else:
                same_position_count = 0

            last_position = current_position

            # if current_position >= page_height - self.driver.execute_script("return window.innerHeight"):
            #     self.logger.info("已捲動到頁面底部")
            #     break

            self.perform_scroll_action()

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
            self.logger.info(f"達到最大嘗試次數 ({max_attempts})，可能未完全捲動到底")

        self.logger.info("頁面捲動完成")

    def perform_scroll_action(self):
        action = random.choices(
            ["scroll_down", "scroll_up", "pause", "jump"], weights=[0.7, 0.1, 0.1, 0.1]
        )[0]

        current_position = self.get_scroll_position()

        if action == "scroll_down":
            scroll_length = random.randint(MIN_SCROLL_LENGTH, MAX_SCROLL_LENGTH)
            target_position = current_position + scroll_length
            self.logger.debug(f"嘗試向下捲動 {scroll_length} 像素")
            actual_position = self.safe_scroll(target_position)
            self.logger.debug(f"實際捲動到 {actual_position} 像素")
            time.sleep(random.uniform(0.5, 1.5))
        elif action == "scroll_up":
            scroll_length = random.randint(50, 150)
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
        step = random.uniform(MIN_SCROLL_STEP, MAX_SCROLL_STEP)
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
