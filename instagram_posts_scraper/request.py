# -*- coding: utf-8 -*-
import json
import cloudscraper
from bs4 import BeautifulSoup
import requests


class PixwoxRequest(object):
    def __init__(self):
        self.__DEFAULT_SOUP_PARSER = "lxml"
        self.__scraper = cloudscraper.create_scraper(
            delay=10,
            browser={"custom": "ScraperBot/1.0",
                     "platform": "windows",
                     "mobile": "False"})

    def send_requests(self, url):
        # response = self.__scraper.get(url) # temporary stop this good method  :（
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
