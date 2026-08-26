# -*- coding: utf-8 -*-
from types import SimpleNamespace
from instagram_posts_scraper.request import *
from instagram_posts_scraper.parse import *
from instagram_posts_scraper.utils import *
from instagram_posts_scraper.scraper import *
from instagram_posts_scraper.utils.utils import *
from instagram_posts_scraper.file_operation import *
from instagram_posts_scraper import schema
from instagram_posts_scraper.profile_scraper import scrape_profile
from datetime import datetime


class InstaPeriodScraper(object):
    def __init__(self, use_profile_scraper: bool = True, profile_headless: bool = True,
                 posts_headless: bool = False) -> None:
        self.pixwox_request = PixwoxRequest()
        self.parser=Parser()
        self.api_parser=ApiParser()
        self.scraper=Scraper( 
            pixwox_request=self.pixwox_request, 
            parser=self.parser, 
            api_parser=self.api_parser
        )
        # When enabled, profile metadata (followers / following / posts_count /
        # biography / full_name / profile picture) is enriched from the
        # dedicated profile scraper, which is more reliable than picnob HTML.
        self.use_profile_scraper = use_profile_scraper
        self.profile_headless = profile_headless
        # Headless Chrome cannot clear Cloudflare's Turnstile challenge, so the
        # posts browser runs headed by default.
        self.posts_headless = posts_headless
        self._profile_meta = None
        self._picnob_profile = None

    def check_account_is_public(self, init_html=None):
        if init_html is not None:
            self.init_response = SimpleNamespace(text=init_html)
        else:
            self.init_response = self.pixwox_request.send_requests(url=self.scraper.init_url)
        self.profile_soup = self.parser.get_soup(response=self.init_response)
        self.userid = self.parser.get_userid(profile_soup=self.profile_soup)
        self.account_status = get_account_status(userid=self.userid, profile_soup=self.profile_soup)
        return self.account_status == "public"
    
    def collect_picnob_profile(self):
        """Scrape the raw profile values exposed by picnob HTML.

        These act as a fallback for profile metadata when the dedicated
        profile scraper is unavailable, and ``counts_of_posts`` is also used as
        a pagination stop-condition during post collection.
        """
        self.followings = self.parser.get_followings(self.profile_soup)
        self.followers = self.parser.get_followers(self.profile_soup)
        self.counts_of_posts = self.parser.get_counts_of_posts(self.profile_soup)
        try:
            self.introduction = self.parser.get_introduction(self.profile_soup)
        except Exception:
            self.introduction = None

        self._picnob_profile = {
            "userid": self.userid,
            "introduction": self.introduction,
            "counts_of_posts": self.counts_of_posts,
            "followers": self.followers,
            "followings": self.followings,
        }
        return self._picnob_profile

    def _fetch_profile_meta(self):
        """Lazily scrape authoritative profile metadata, caching the result.

        Returns ``None`` (and degrades gracefully) when the profile scraper is
        disabled or fails for any reason.
        """
        if not self.use_profile_scraper:
            return None
        if self._profile_meta is not None:
            return self._profile_meta
        try:
            self._profile_meta = scrape_profile(
                username=self.username,
                headless=self.profile_headless,
            )
        except Exception as exc:
            print(f"Instagram-profile-scraper unavailable, using picnob fallback: {exc}")
            self._profile_meta = None
        return self._profile_meta

    def _build_result(self, account_status, picnob_profile=None,
                      api_posts=None, html_posts=None, init_posts=None, warning=None):
        """Assemble the consolidated result from both data sources.

        ``init_posts`` (raw picnob first-page HTML posts) and ``top_posts``
        (raw profile-scraper highlights) are passed through untouched so no
        source data is dropped.
        """
        profile_meta = self._fetch_profile_meta()
        profile = schema.build_profile(
            username=self.username,
            picnob_profile=picnob_profile,
            profile_meta=profile_meta,
        )
        posts = schema.normalize_posts(api_items=api_posts, html_items=html_posts)
        top_posts = (profile_meta or {}).get("top_posts") or []
        return schema.build_result(
            account_status=account_status,
            profile=profile,
            updated_at=get_current_time(timezone="Asia/Taipei"),
            posts=posts,
            init_posts=init_posts,
            top_posts=top_posts,
            warning=warning,
        )

    def get_init_api_data(self):
        init_api_data = self.scraper.get_init_api_data(userid=self.userid)
        return init_api_data
    
    def get_next_api_data(self, next_maxid:str, next_:str,username:str):
        next_api_data = self.scraper.get_next_api_data(userid=self.userid, next_maxid=next_maxid, next_=next_, username=username)
        return next_api_data

    # @timeout(300)
    def get_period_data(self, days_limit: int, init_maxid: str, init_api_data: dict, username: str) -> list:
        """
        Fetches social media posts within specified days with retry mechanism and deduplication.
        
        Implements pagination handling with error resilience and detailed logging for Apify platform.

        Args:
            days_limit: Maximum number of pagination rounds to attempt
            init_maxid: Initial pagination identifier
            init_api_data: Initial API response data
            username: Target account username

        Returns:
            list: Deduplicated list of post items

        Raises:
            ValueError: If initial API data structure is invalid
        """
        # Validate initial API structure
        if 'posts' not in init_api_data or 'items' not in init_api_data['posts']:
            raise ValueError("Invalid initial API data structure")

        # Initialize data containers
        scraped_posts_res = init_api_data.get('posts', {}).get('items', [])[:]  # Create list copy
        next_metadata = {
            'maxid': init_api_data.get('posts', {}).get('maxid', init_maxid),
            'next': init_api_data.get('posts', {}).get('next', 0),
            'has_next': init_api_data.get('posts', {}).get('has_next', False)
        }
        
        # Deduplication setup
        processed_shortcodes = {item['shortcode'] for item in scraped_posts_res if 'shortcode' in item}
        
        rounds = 0
        MAX_RETRIES = 3
        RETRY_DELAY = 3

        while rounds < days_limit:
            retry_count = 0
            success = False

            while retry_count < MAX_RETRIES and not success:
                try:
                    # Fetch next page data
                    next_api_data = self.get_next_api_data(
                        next_maxid=next_metadata['maxid'],
                        next_=next_metadata['next'],
                        username=username
                    )

                    if not isinstance(next_api_data, dict):
                        raise ValueError("Invalid next API response")

                    # Process API response
                    posts_data = next_api_data.get('posts', {})
                    new_items = posts_data.get('items', [])
                    
                    # Validate data format
                    if not isinstance(new_items, list):
                        new_items = []
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"{current_time} | WARNING | {self.__class__.__name__}(get_period_data) - "
                            f"Invalid data format at round {rounds}, resetting to empty list")

                    # Deduplication processing
                    new_items_deduplicated = [
                        item for item in new_items 
                        if 'shortcode' in item and item['shortcode'] not in processed_shortcodes
                    ]
                    scraped_posts_res.extend(new_items_deduplicated)
                    processed_shortcodes.update(item['shortcode'] for item in new_items_deduplicated)

                    # Termination conditions
                    termination_conditions = [
                        has_all_data_been_collected(scraped_posts_res, self.counts_of_posts),
                        is_date_exceed_half_year(new_items_deduplicated, days_limit),
                        len(new_items_deduplicated) == 0  # No new data
                    ]
                    if any(termination_conditions):
                        return scraped_posts_res

                    # Update pagination parameters
                    next_metadata = {
                        'maxid': posts_data.get('maxid', ''),
                        'next': posts_data.get('next', 0),
                        'has_next': posts_data.get('has_next', False)
                    }

                    if not next_metadata['has_next']:
                        return scraped_posts_res

                    success = True
                    rounds += 1

                except Exception as e:
                    retry_count += 1
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    ## display the entire failed details
                    # error_type = type(e).__name__                    
                    # # Structured error logging
                    # print(f"\n{current_time} | ERROR | {self.__class__.__name__}(get_period_data) - "
                    #     f"Round {rounds} Attempt {retry_count}/{MAX_RETRIES} failed\n"
                    #     f"Error Type: {error_type}\n"
                    #     f"Message: {str(e)}\n"
                    #     "Traceback Details:")
                    
                    # # Detailed traceback printing
                    # traceback_str = traceback.format_exc()
                    # print(f"{'-'*100}\n{traceback_str}\n{'-'*100}\n")
                    
                    ## display failed resone
                    # print(f"[第 {rounds} 輪] 第 {retry_count} 次重試失敗，原因: {str(e)}")
                    
                    ## display retry rounds
                    print(f"Instagram-posts-scraper Round {retry_count} retry.")
                    
                    time.sleep(RETRY_DELAY * retry_count)  # Progressive backoff

            if not success:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # print(f"\n{current_time} | CRITICAL | {self.__class__.__name__}(get_period_data) - "
                #     f"Round {rounds} failed after {MAX_RETRIES} retries\n"
                #     f"{'='*100}\n")
                rounds += 1

        return scraped_posts_res
    
    def get_posts(self, target_info:dict):
        self.target_info = target_info
        self.username = self.target_info["username"]
        username = self.target_info["username"]
        self.scraper.set_username(username)
        days_limit = target_info["days_limit"]

        # check if user-agent & cookies are valid first
        print("# check if user-agent & cookies are valid first")
        headers, cookies, init_html, driver = get_valid_headers_cookies(
            username=username,
            headless=self.posts_headless,
        )
        self.pixwox_request.set_valid_headers_cookies(valid_headers_cookies=(headers, cookies))
        # Wire the live Selenium driver so all API requests bypass Cloudflare.
        # driver is None only when the requests-based cache path succeeded.
        if driver is not None:
            self.pixwox_request.set_driver(driver)

        try:
            if not self.check_account_is_public(init_html=init_html):
                print("This is private account")
                if self.account_status == "private":
                    picnob_profile = self.collect_picnob_profile()
                    return self._build_result(
                        account_status=self.account_status,
                        picnob_profile=picnob_profile,
                    )
                elif self.account_status == "missing":
                    # An unsolved Cloudflare challenge looks identical to a
                    # deleted account (no userid in the HTML), so tell them apart
                    # instead of silently returning an empty result.
                    if looks_like_cloudflare_challenge(init_html):
                        print("Cloudflare challenge was not cleared: "
                              "cannot tell whether this account exists")
                        return self._build_result(
                            account_status=self.account_status,
                            warning="cloudflare_challenge_unsolved",
                        )
                    return self._build_result(account_status=self.account_status)

            if self.check_account_is_public(init_html=init_html):
                self.scraper_utils = get_scraper_utils(html=self.init_response.text)
                print(f"This is public account")
                init_response = self.init_response

                # Prefer the paginated endpoint when page metadata is available.
                # Some public profiles do not expose a.more_btn; in that case,
                # fallback to the initial API to avoid NoneType errors.
                if self.scraper_utils is not None:
                    userid = self.scraper_utils["userid"]
                    username = self.scraper_utils["username"]
                    next_maxid = self.scraper_utils["data_maxid"]
                    next_ = self.scraper_utils["clean_data_next"]
                    next_api = f"{BASE_URL}/api/posts?username={username}&userid={userid}&next={next_}==&maxid={next_maxid}"
                    init_api_data = self.pixwox_request.send_requests(url=next_api) # actually, this is next..
                    init_api_data = init_api_data.json()
                else:
                    init_api_data = self.get_init_api_data()

                if (not isinstance(init_api_data, dict) or "posts" not in init_api_data) and driver is None:
                    # Cached requests session can pass profile checks but still be blocked on API.
                    # Force a fresh browser-backed session and retry once.
                    print("Cached session cannot access API. Refreshing via browser")
                    headers, cookies, init_html, driver = get_valid_headers_cookies(
                        username=username,
                        force_refresh=True,
                        headless=self.posts_headless,
                    )
                    self.pixwox_request.set_valid_headers_cookies(valid_headers_cookies=(headers, cookies))
                    if driver is not None:
                        self.pixwox_request.set_driver(driver)

                    self.check_account_is_public(init_html=init_html)
                    self.scraper_utils = get_scraper_utils(html=self.init_response.text)
                    if self.scraper_utils is not None:
                        userid = self.scraper_utils["userid"]
                        username = self.scraper_utils["username"]
                        next_maxid = self.scraper_utils["data_maxid"]
                        next_ = self.scraper_utils["clean_data_next"]
                        next_api = f"{BASE_URL}/api/posts?username={username}&userid={userid}&next={next_}==&maxid={next_maxid}"
                        init_api_data = self.pixwox_request.send_requests(url=next_api).json()
                    else:
                        init_api_data = self.get_init_api_data()

                if not isinstance(init_api_data, dict) or "posts" not in init_api_data:
                    # Some public accounts can pass profile checks but still
                    # return non-standard API payloads. Degrade gracefully
                    # with HTML-visible posts instead of failing hard.
                    picnob_profile = self.collect_picnob_profile()
                    init_posts = self.parser.extract_init_posts(init_response.text)
                    return self._build_result(
                        account_status=self.account_status,
                        picnob_profile=picnob_profile,
                        html_posts=init_posts,
                        init_posts=init_posts,
                        warning="api_unavailable_for_account",
                    )

                picnob_profile = self.collect_picnob_profile()
                init_posts = self.parser.extract_init_posts(init_response.text)
                # can scrape next round's posts
                if init_api_data["posts"]["has_next"] != False:
                    maxid = init_api_data["posts"]["maxid"]
                    period_posts = self.get_period_data(
                        init_maxid=maxid,
                        days_limit=days_limit,
                        init_api_data=init_api_data,
                        username=username
                        )
                    return self._build_result(
                        account_status=self.account_status,
                        picnob_profile=picnob_profile,
                        api_posts=period_posts,
                        init_posts=init_posts,
                    )
                # # no more posts
                elif init_api_data["posts"]["has_next"] == False: # (表示該帳號貼文數<=12, 無法繼續往下找)
                    return self._build_result(
                        account_status=self.account_status,
                        picnob_profile=picnob_profile,
                        api_posts=init_api_data["posts"]["items"],
                        init_posts=init_posts,
                    )
        finally:
            # Always close the Selenium driver when scraping is done or an error occurs.
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
