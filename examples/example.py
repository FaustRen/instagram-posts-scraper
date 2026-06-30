# -*- coding: utf-8 -*-
from instagram_posts_scraper.instagram_posts_scraper import InstaPeriodScraper
from IPython.display import display

ig_posts_scraper = InstaPeriodScraper()
target_info = {"username": "stephencurry30", "days_limit": 30}
res = ig_posts_scraper.get_posts(target_info=target_info)
display(res)
