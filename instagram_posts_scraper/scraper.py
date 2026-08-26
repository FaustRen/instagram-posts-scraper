# -*- coding: utf-8 -*-
import json

from instagram_posts_scraper.utils.utils import BASE_URL


class Scraper(object):
    def __init__(self, pixwox_request=None, parser=None,api_parser=None):
        self.pixwox_request = pixwox_request
        self.parser = parser
        self.api_parser = api_parser
        # self.target_info = target_info

    def set_username(self, username:str):
        self.__username = username
    
    @property
    def username(self):
        return self.__username

    @property
    def init_url(self) -> str:
        self._init_url = f"{BASE_URL}/profile/{self.username}"
        return self._init_url
    
    def get_init_api(self, userid:str) -> str:
        self._init_api = f"{BASE_URL}/api/posts?userid={userid}"
        return self._init_api
    
    def get_next_api(self, userid:str, next_maxid:str, next_:str, username:str) -> str:
        next_api = f"{BASE_URL}/api/posts?username={username}&userid={userid}&next={next_}&maxid={next_maxid}"
        return next_api
    
    def send_api(self,api_url:str):
        api_response = self.pixwox_request.send_requests(url=api_url)
        return api_response

    def get_api_data(self, api_response):
        if api_response.status_code != 200:
            print("status code from init api request is not equal 200")
            return None
        else:
            json_data = json.loads(api_response.content)
            return json_data

    def get_init_api_data(self,userid:str) -> dict:
        init_api = self.get_init_api(userid=userid)
        init_api_response = self.send_api(api_url=init_api)
        return self.get_api_data(api_response=init_api_response)
    
    def get_next_api_data(self, userid:str, next_maxid:str,next_:str, username:str):
        next_api = self.get_next_api(userid=userid, next_maxid=next_maxid,next_=next_, username=username)
        api_response = self.send_api(api_url=next_api)
        next_api_data = self.get_api_data(api_response)
        return next_api_data