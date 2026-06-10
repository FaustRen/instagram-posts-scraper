# -*- coding: utf-8 -*-
"""Instagram Posts Scraper.

A Python library for collecting Instagram users' public post data via picnob.com.
The data obtained is not real-time, but a snapshot from a specific point of the
same day.

Basic usage::

    from instagram_posts_scraper.instagram_posts_scraper import InstaPeriodScraper

    target_info = {"username": "kaicenat", "days_limit": 60}
    scraper = InstaPeriodScraper()
    result = scraper.get_posts(target_info=target_info)

Project: https://github.com/FaustRen/instagram-posts-scraper
"""

__version__ = "0.0.8"
__author__ = "FaustRen"
__license__ = "MIT"

from instagram_posts_scraper.instagram_posts_scraper import InstaPeriodScraper

__all__ = ["InstaPeriodScraper", "__version__"]
