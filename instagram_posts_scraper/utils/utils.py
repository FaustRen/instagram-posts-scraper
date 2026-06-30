# -*- coding: utf-8 -*-
import concurrent.futures as futures
from datetime import datetime
from functools import wraps
import os
from pathlib import Path
import json
import time

import cloudscraper
import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver


# ── decorators ─────────────────────────────────────────────────────────────────

def timeit(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        print(f'Function {func.__name__}{args} {kwargs} Took {total_time:.4f} seconds')
        return result
    return timeit_wrapper


def timeout(timelimit):
    def decorator(func):
        def decorated(*args, **kwargs):
            with futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    result = future.result(timelimit)
                except futures.TimeoutError:
                    print('Time out!')
                    raise TimeoutError from None
                else:
                    print(result)
                executor._threads.clear()
                futures.thread._threads_queues.clear()
                return result
        return decorated
    return decorator


# ── helpers ────────────────────────────────────────────────────────────────────

def get_current_time(timezone="Asia/Taipei"):
    current_time_utc = datetime.utcnow()
    target_timezone = pytz.timezone(timezone)
    return current_time_utc.replace(tzinfo=pytz.utc).astimezone(target_timezone)


def get_account_status(userid, profile_soup=None):
    if userid == "":
        return "missing"
    if profile_soup.find("span", class_="ident private icon icon_lock"):
        return "private"
    return "public"


def has_all_data_been_collected(scraped_items: list, counts_of_posts):
    return len({item["shortcode"] for item in scraped_items}) >= int(counts_of_posts)


def is_date_exceed_half_year(scraped_items: list, days_limit: int):
    current_time = datetime.now()
    days_ago_list = [
        int((current_time - pd.to_datetime(item["time"], unit="s")).days)
        for item in scraped_items
    ]
    return max(days_ago_list) > days_limit


def get_scraper_utils(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    userid   = soup.find('input', {'name': 'userid'})['value']
    username = soup.find('input', {'name': 'username'})['value']
    for btn in soup.select('a.more_btn'):
        data_next = btn.get('data-next')
        if data_next:
            return {
                "userid":          userid,
                "username":        username,
                "clean_data_next": data_next.rstrip('='),
                "data_maxid":      btn.get('data-maxid'),
            }


# ── browser session ────────────────────────────────────────────────────────────

class BrowserSession:
    """Manages a Selenium browser session that bypasses Cloudflare.

    Handles cookie caching, ad dismissal, and exposes the live driver
    so subsequent requests can reuse the same trusted session.
    Caller is responsible for calling driver.quit() when done.
    """

    _AUTH_FILE = "instagram_posts_scraper_headers.json"
    _CLOSE_SELECTORS = [
        '.demand-supply__sd-close-button',
        '[aria-label="Close"]',
        '[aria-label="關閉"]',
    ]
    _SKIP_XPATHS = [
        '//button[@aria-label="略過廣告"]',
        '//button[@aria-label="Close ad"]',
        '//button[@aria-label="Close"]',
        '//button[contains(@class,"skip")]',
        '//button[contains(@class,"close")]',
        '//button[contains(text(),"Skip")]',
    ]

    def __init__(self, username: str):
        self.username = username
        self.url = f"https://www.picnob.com/profile/{username}"
        self.driver = None
        self._cache_path = self._build_cache_path(username)
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Persistent Chrome profile: Cloudflare clearance (cf_clearance) lives in
        # the browser profile, not in the cookie jar. Reusing the same profile
        # across runs lets later launches skip the Cloudflare challenge entirely,
        # which is the single biggest speed win for repeated scrapes.
        self._profile_dir = self._build_profile_dir()

    @staticmethod
    def _http_get(url: str, headers: dict, cookies: dict, timeout: int = 20):
        """GET using cloudscraper (browser-like TLS) with a plain-requests fallback.

        Cloudflare binds cf_clearance to the TLS/JA3 fingerprint, so plain
        requests often returns 403 even with valid cookies. cloudscraper
        mimics a browser handshake and is far more likely to pass.
        """
        try:
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "darwin", "mobile": False}
            )
            return scraper.get(url, headers=headers, cookies=cookies, timeout=timeout)
        except Exception:
            return requests.get(url, headers=headers, cookies=cookies, timeout=timeout)

    @staticmethod
    def _sanitize_username(username: str) -> str:
        return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in username)

    def _build_cache_path(self, username: str) -> Path:
        cache_dir = os.getenv("INSTAGRAM_POSTS_SCRAPER_CACHE_DIR")
        if cache_dir:
            root = Path(cache_dir)
        else:
            root = Path.home() / ".cache" / "instagram_posts_scraper"
        return root / f"{self._AUTH_FILE[:-5]}_{self._sanitize_username(username)}.json"

    @staticmethod
    def _build_profile_dir() -> str:
        """Shared Chrome profile dir (Cloudflare clearance is domain-wide)."""
        cache_dir = os.getenv("INSTAGRAM_POSTS_SCRAPER_CACHE_DIR")
        root = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "instagram_posts_scraper"
        profile_dir = root / "chrome_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        return str(profile_dir)

    def _cache_api_is_valid(self, headers: dict, cookies: dict, userid: str) -> bool:
        try:
            api_url = f"https://www.picnob.com/api/posts?userid={userid}"
            resp = self._http_get(api_url, headers=headers, cookies=cookies)
            if resp.status_code != 200:
                return False
            data = resp.json()
            return isinstance(data, dict) and "posts" in data and isinstance(data["posts"], dict)
        except Exception:
            return False

    # ── cache ──────────────────────────────────────────────────────────────────

    def load_cache(self):
        """Return (headers, cookies, page_html, None) if cache is valid, else None."""
        if not self._cache_path.exists():
            return None
        try:
            data = json.load(self._cache_path.open())
            headers, cookies = data["headers"], data["cookies"]
            resp = self._http_get(self.url, headers=headers, cookies=cookies)
            if resp.status_code == 200 and 'name="userid"' in resp.text:
                soup = BeautifulSoup(resp.text, "html.parser")
                userid_input = soup.find('input', {'name': 'userid'})
                userid = getattr(userid_input, "attrs", {}).get("value", "") if userid_input else ""
                if userid and self._cache_api_is_valid(headers, cookies, userid):
                    print("Cache is valid")
                    return headers, cookies, resp.text, None
                print("Cache profile is valid but API is not. Refreshing via browser")
                return None
            print(f"Cache invalid (status={resp.status_code}). Refreshing via browser")
        except Exception:
            print("Failed to read cache. Refreshing via browser")
        return None

    def _save_cache(self, headers: dict, cookies: dict):
        json.dump({"headers": headers, "cookies": cookies},
                  self._cache_path.open("w"), indent=2)

    # ── browser ────────────────────────────────────────────────────────────────

    def launch(self):
        """Open the profile URL in an undetected Chrome instance."""
        print("Launching browser to bypass Cloudflare")
        self.driver = Driver(
            uc=True,
            headless=True,
            chromium_arg="--mute-audio",
            user_data_dir=self._profile_dir,
        )
        self.driver.uc_open_with_reconnect(self.url)
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='userid']"))
            )
            print("Page loaded successfully")
        except Exception as e:
            print(f"Page load timed out: {e}, continuing anyway")
        time.sleep(1.5)
        self._dismiss_ads()
        time.sleep(1)
        return self

    def _dismiss_ads(self):
        """Try to close ads: first inside iframes, then on the main page."""
        for iframe in self.driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                self.driver.switch_to.frame(iframe)
                for xpath in self._SKIP_XPATHS:
                    try:
                        self.driver.find_element(By.XPATH, xpath).click()
                        print(f"Clicked ad skip button: {xpath}")
                        self.driver.switch_to.default_content()
                        return
                    except Exception:
                        pass
            except Exception:
                pass
        self.driver.switch_to.default_content()
        for sel in self._CLOSE_SELECTORS:
            try:
                self.driver.execute_script(
                    "arguments[0].click();",
                    self.driver.find_element(By.CSS_SELECTOR, sel),
                )
                print(f"Clicked close button: {sel}")
                time.sleep(1)
            except Exception:
                pass

    def get_session(self):
        """Persist cookies and return (headers, cookies, page_html, driver)."""
        headers = {"User-Agent": self.driver.execute_script("return navigator.userAgent;")}
        cookies = {c["name"]: c["value"] for c in self.driver.get_cookies()}
        self._save_cache(headers, cookies)
        print("Headers and cookies updated successfully")
        return headers, cookies, self.driver.page_source, self.driver


def get_valid_headers_cookies(username: str, force_refresh: bool = False):
    # Cookie-jar HTTP caching cannot work for picnob: Selenium never captures
    # cf_clearance, so reusing cookies via requests/cloudscraper always returns
    # 403. Speed comes instead from the persistent Chrome profile, which keeps
    # Cloudflare clearance between runs so the browser launch skips the
    # challenge. We therefore always go through the live browser.
    session = BrowserSession(username)
    return session.launch().get_session()