# -*- coding: utf-8 -*-
import json
import time
import cloudscraper
from bs4 import BeautifulSoup
import requests


class _SeleniumResponse:
    """Minimal requests.Response-compatible wrapper for Selenium page fetches."""
    def __init__(self, text: str):
        self._text = text
        self.status_code = 200

    @property
    def text(self):
        return self._text

    @property
    def content(self):
        return self._text.encode("utf-8")

    def json(self, **kwargs):
        return json.loads(self._text)


class PixwoxRequest(object):
    def __init__(self):
        self.__DEFAULT_SOUP_PARSER = "lxml"
        self.__driver = None
        self.__scraper = cloudscraper.create_scraper(
            delay=10,
            browser={"custom": "ScraperBot/1.0",
                     "platform": "windows",
                     "mobile": "False"})

    def set_driver(self, driver):
        """Use a live Selenium driver for all requests (bypasses Cloudflare)."""
        self.__driver = driver

    def __wait_for_body(self, url, timeout=8, poll=0.2):
        """Poll body.innerText until the response is ready instead of a fixed sleep.

        For JSON API endpoints this returns as soon as the payload starts with
        '{' or '[' (usually well under 0.5s), replacing the old hard 2s wait per
        request. Falls back to whatever is present after `timeout` seconds.
        """
        is_api = "/api/" in url
        deadline = time.time() + timeout
        text = ""
        while time.time() < deadline:
            text = self.__driver.execute_script("return document.body.innerText") or ""
            stripped = text.lstrip()
            if is_api:
                if stripped.startswith("{") or stripped.startswith("["):
                    return text
            elif stripped:
                return text
            time.sleep(poll)
        return text

    def send_requests(self, url):
        if self.__driver is not None:
            self.__driver.get(url)
            # For JSON API endpoints Chrome wraps content in <pre>; for HTML pages
            # we want the full source. Use innerText of body to get clean content.
            text = self.__wait_for_body(url)
            return _SeleniumResponse(text)
        # Fallback: plain requests (works only when Cloudflare is not blocking)
        response = requests.get(
            url=url, 
            headers={"User-Agent":self.__user_agent}, 
            cookies=self.__cookies
        )
        return response
    
    def set_valid_headers_cookies(self, valid_headers_cookies):
        self.__valid_headers_cookies = valid_headers_cookies
        self.__user_agent = self.__valid_headers_cookies[0].get("User-Agent")
        self.__cookies = self.__valid_headers_cookies[1]
        
    def get_init_content(self, username: str) -> str:
        get_url = f"https://www.pixnoy.com/profile/{username}"
        res = self.send_requests(get_url)
        soup = BeautifulSoup(res.text, self.__DEFAULT_SOUP_PARSER)
        userid_input_element = soup.find(
            "input", {"name": "userid", "type": "hidden"})

        if userid_input_element:
            return userid_input_element["value"], soup

        return "", ""
    
    def get_init_soup(self, profile_response):
        soup = BeautifulSoup(profile_response.text, self.__DEFAULT_SOUP_PARSER)
        return soup

    def get_maxid(self, response):
        maxid = json.loads(response.text)["posts"]["maxid"]
        return maxid

    def get_data(self, response):
        scraped_data = json.loads(response.text)
        return scraped_data
