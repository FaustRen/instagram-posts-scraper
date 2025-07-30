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
    # Define the URL for the user's profile
    url = f"https://www.pixnoy.com/profile/{username}"

    # Define the path where headers and cookies will be stored
    main_dir = Path(__file__).resolve().parent.parent
    json_dir = main_dir / "auth_data"
    json_dir.mkdir(exist_ok=True)
    json_path = json_dir / "instagram_posts_scraper_headers.json"

    # Launch browser and extract headers and cookies
    def crawl_and_save():
        print("Launching browser to bypass Cloudflare")
        driver = Driver(uc=True, headless=True, chromium_arg="--mute-audio")
        driver.uc_open_with_reconnect(url)

        # Attempt to click the "watch ad" button if it appears
        try:
            watch_ad_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "fc-rewarded-ad-button"))
            )
            watch_ad_btn.click()
            print("Clicked to watch ad")
        except Exception as e:
            print("Ad button not found", e)

        time.sleep(10)
        print("Searching for iframes to skip ad")
        try_skip_ads(driver)

        time.sleep(3)
        driver.find_element(By.XPATH, '//*[@id="button"]/span').click()
        time.sleep(5)

        # Extract cookies and user-agent
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        user_agent = driver.execute_script("return navigator.userAgent;")
        headers = {"User-Agent": user_agent}

        # Save headers and cookies to file
        with open(json_path, "w") as f:
            json.dump({"headers": headers, "cookies": cookies}, f, indent=2)

        driver.quit()
        print("Headers and cookies updated successfully")
        return headers, cookies

    # Check if cache file exists
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


# Try to skip ads by clicking "skip" or "close" buttons inside iframes
def try_skip_ads(driver):
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    found = False

    for i, iframe in enumerate(iframes):
        driver.switch_to.default_content()
        driver.switch_to.frame(iframe)

        try:
            skip_button = driver.find_element(By.XPATH, '//button[@aria-label="略過廣告"]')
            print(f"Found skip button in iframe {i}")
            driver.execute_script("arguments[0].click();", skip_button)
            found = True
        except:
            pass

        if found:
            break

        try:
            close_button = driver.find_element(By.XPATH, '//button[@aria-label="Close ad"]')
            print(f"Found close button in iframe {i}")
            driver.execute_script("arguments[0].click();", close_button)
            found = True
        except:
            pass

        if found:
            break

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