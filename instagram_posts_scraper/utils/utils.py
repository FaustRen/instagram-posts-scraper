# -*- coding: utf-8 -*-
import concurrent.futures as futures
from datetime import datetime
import pytz
import pandas as pd
from functools import wraps
import time
import os
from selenium.webdriver.common.by import By
import json
import requests
from seleniumbase import Driver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from pathlib import Path
from bs4 import BeautifulSoup


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

def get_current_time(timezone="Asia/Taipei"):
    current_time_utc = datetime.utcnow()
    target_timezone = pytz.timezone(timezone)
    target_current_time = current_time_utc.replace(
        tzinfo=pytz.utc).astimezone(target_timezone)
    return target_current_time

def get_account_status(userid, profile_soup=None):
    if userid == "":
        return "missing"
    else:
        private_span = profile_soup.find(
            "span", class_="ident private icon icon_lock")
        if private_span:
            return "private"
        return "public"

def has_all_data_been_collected(scraped_items:pd.DataFrame,counts_of_posts):
    """Whether program get all posts already."""
    if len(set([each["shortcode"] for each in scraped_items])) >= int(counts_of_posts):
        return True
    return False

def is_date_exceed_half_year(scraped_items:pd.DataFrame, days_limit:int):
    """Check if scraped posts' published date exceed half year"""
    current_time = datetime.now()
    days_ago_list = [int(
        (current_time - pd.to_datetime(each["time"], unit="s")).days) for each in scraped_items]
    
    max_days_ago = max(days_ago_list) # 爬到的貼文裡, 發文時間距離當前時間最遠的日期
    if max_days_ago > days_limit:  # 半年內
        return True
    return False

def get_valid_headers_cookies(username: str):
    url = f"https://www.pixnoy.com/profile/{username}"

    main_dir = Path(__file__).resolve().parent.parent
    json_dir = main_dir / "auth_data"
    json_dir.mkdir(exist_ok=True)
    json_path = json_dir / "instagram_posts_scraper_headers.json"

    def crawl_and_save():
        print("Launching browser to bypass Cloudflare")
        driver = Driver(uc=True, headless=True, chromium_arg="--mute-audio")
        driver.uc_open_with_reconnect(url)

        # Wait for page to load
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='userid']"))
            )
            print("Page loaded successfully")
        except Exception as e:
            print(f"Page load wait timed out: {e}, continuing anyway")

        # Try to dismiss any overlay ads (non-blocking)
        try:
            time.sleep(3)
            print("Searching for iframes to skip ad")
            try_skip_ads(driver)
        except Exception as e:
            print(f"Ad skip attempt failed (non-critical): {e}")

        # Try clicking any visible close/dismiss buttons on main page
        for selector in [
            '.demand-supply__sd-close-button',
            '[aria-label="Close"]',
            '[aria-label="關閉"]',
        ]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, selector)
                driver.execute_script("arguments[0].click();", btn)
                print(f"Clicked close button: {selector}")
                time.sleep(1)
            except:
                pass

        time.sleep(3)

        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        user_agent = driver.execute_script("return navigator.userAgent;")
        headers = {"User-Agent": user_agent}

        with open(json_path, "w") as f:
            json.dump({"headers": headers, "cookies": cookies}, f, indent=2)

        driver.quit()
        print("Headers and cookies updated successfully")
        return headers, cookies

    if json_path.exists():
        with open(json_path, "r") as f:
            try:
                data = json.load(f)
                headers = data["headers"]
                cookies = data["cookies"]

                print("Attempting to use cached headers and cookies")
                resp = requests.get(url, headers=headers, cookies=cookies)
                if resp.status_code == 200:
                    print("Cache is valid")
                    return headers, cookies
                else:
                    print(f"Cache invalid. Status code: {resp.status_code}. Getting new data")
                    return crawl_and_save()
            except Exception as e:
                print("Failed to read cache file. Getting new data")
                return crawl_and_save()
    else:
        return crawl_and_save()
def try_skip_ads(driver):
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    found = False

    skip_xpaths = [
        '//button[@aria-label="略過廣告"]',
        '//button[@aria-label="Close ad"]',
        '//button[@aria-label="Close"]',
        '//button[contains(@class,"skip")]',
        '//button[contains(@class,"close")]',
        '//button[contains(text(),"Skip")]',
    ]

    for i, iframe in enumerate(iframes):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(iframe)

            for xpath in skip_xpaths:
                try:
                    btn = driver.find_element(By.XPATH, xpath)
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"Found and clicked button '{xpath}' in iframe {i}")
                    found = True
                    break
                except:
                    pass

            if found:
                break
        except:
            continue

    driver.switch_to.default_content()
    if not found:
        print("No skip or close buttons found in any iframe")

def get_scraper_utils(html:str):
    soup = BeautifulSoup(html, 'html.parser')
    userid = soup.find('input', {'name': 'userid'})['value']
    username = soup.find('input', {'name': 'username'})['value']
    more_btns = soup.select('a.more_btn') # find all a.more_btn
    for btn in more_btns: # Filter data-next (exists value)
        data_next = btn.get('data-next')
        if data_next:
            clean_data_next = data_next.rstrip('=')
            data_maxid = btn.get('data-maxid')
            break
    return {
        "userid":userid,
        "username":username,
        "clean_data_next":clean_data_next,
        "data_maxid":data_maxid
    }