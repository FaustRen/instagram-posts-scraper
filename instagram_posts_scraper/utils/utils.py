# -*- coding: utf-8 -*-
import concurrent.futures as futures
from datetime import datetime
from functools import wraps
from pathlib import Path
import json
import time

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
        self.url = f"https://www.picnob.com/profile/{username}"
        self.driver = None
        self._cache_path = (
            Path(__file__).resolve().parent.parent / "auth_data" / self._AUTH_FILE
        )
        self._cache_path.parent.mkdir(exist_ok=True)

    # ── cache ──────────────────────────────────────────────────────────────────

    def load_cache(self):
        """Return (headers, cookies, page_html, None) if cache is valid, else None."""
        if not self._cache_path.exists():
            return None
        try:
            data = json.load(self._cache_path.open())
            headers, cookies = data["headers"], data["cookies"]
            resp = requests.get(self.url, headers=headers, cookies=cookies)
            if resp.status_code == 200 and 'name="userid"' in resp.text:
                print("Cache is valid")
                return headers, cookies, resp.text, None
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
        self.driver = Driver(uc=True, headless=True, chromium_arg="--mute-audio")
        self.driver.uc_open_with_reconnect(self.url)
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='userid']"))
            )
            print("Page loaded successfully")
        except Exception as e:
            print(f"Page load timed out: {e}, continuing anyway")
        time.sleep(3)
        self._dismiss_ads()
        time.sleep(3)
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


def get_valid_headers_cookies(username: str):
    session = BrowserSession(username)
    return session.load_cache() or session.launch().get_session()