from typing import Any, Dict, List, Optional
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
import re
import json


class InstagramProfileScraper:
    def __init__(self, wait_sec: int = 10, headless: bool = True):
        
        self.prefix_url = "https://insta-stories-viewer.com/"
        self.wait_sec = wait_sec

        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1200,900")
        # 可選：避免被擋 UA
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

        self.driver = webdriver.Chrome(options=options)
        self.soup = None
        self._requests_session: Optional[requests.Session] = None
        self._user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    def fetch_page(self, username:str):
        """開啟頁面並等到關鍵元素出現後再解析 HTML。"""
        # Strip leading '@' if present
        if username:
            username = username.lstrip('@')
        self.username = username
        self.is_valid_profile = True
        url = self.prefix_url + username
        self.driver.get(url)

        # 等到任一 profile 區塊或統計數值出現
        try:
            WebDriverWait(self.driver, self.wait_sec).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "div.profile__description, span.profile__stats-item-value"
                ))
            )
        except TimeoutException:
            self.is_valid_profile = False
        self.soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # Build a requests.Session from the driver's cookies so subsequent
        # usernames can be fetched without launching another browser.
        if self._requests_session is None:
            self._requests_session = requests.Session()
        self._requests_session.headers.update({
            'User-Agent': self._user_agent,
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        for cookie in self.driver.get_cookies():
            self._requests_session.cookies.set(
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', ''),
            )

    def fetch_page_with_requests(self, username: str) -> None:
        """Fetch a profile page using the requests session seeded from the first
        driver load.  Falls back to marking the profile invalid if the page
        does not contain the expected profile elements (JS-rendered sites will
        return empty markup)."""
        if not self._requests_session:
            raise RuntimeError("fetch_page() must be called at least once before fetch_page_with_requests()")
        if username:
            username = username.lstrip('@')
        self.username = username
        self.is_valid_profile = True
        url = self.prefix_url + username

        try:
            response = self._requests_session.get(url, timeout=self.wait_sec)
            response.raise_for_status()
        except Exception:
            self.is_valid_profile = False
            self.soup = BeautifulSoup("", "html.parser")
            return

        self.soup = BeautifulSoup(response.text, "html.parser")

    @staticmethod
    def _to_int(text: str) -> int:
        """將 '248.9K', '1,234', '375', '2.3M' 等字串轉成整數。"""
        if not text:
            return 0
        s = text.strip().replace(",", "").replace(" ", "")
        m = re.match(r"^([0-9]*\.?[0-9]+)\s*([KkMmBb]?)$", s)
        if not m:
            # 若完全不是數字格式，回 0
            return 0
        num = float(m.group(1))
        suf = m.group(2).lower()
        mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suf, 1)
        return int(num * mult)

    def _empty_profile(self) -> dict:
        """Return the default result for an invalid / non-existent profile."""
        return {
            "description": "",
            "posts": 0,
            "followers": 0,
            "follows": 0,
            "userid": "0",
            "followers_precise": -1,
            "full_name": "",
            "posts_precise": -1,
            "top_posts": [],
            "profile_picture": "",
        }

    def _extract_profile_picture(self) -> str:
        """Best-effort extraction of the profile avatar URL.

        Returns an absolute URL when an avatar is found, or an empty string
        when there is no avatar (e.g. placeholder image) or parsing fails.
        This is intentionally defensive so it can never break profile scraping.
        """
        try:
            if not self.soup:
                return ""

            # Try a few selectors in order of specificity; fall back to any
            # <img> whose class hints at an avatar. Avoids depending on a
            # single class that the third-party viewer might rename.
            candidates = []
            for sel in ("img.profile__avatar-pic", "img.popup__avatar-pic"):
                candidates.extend(self.soup.select(sel))
            if not candidates:
                candidates = [
                    img for img in self.soup.find_all("img")
                    if any("avatar" in c for c in (img.get("class") or []))
                ]

            for img in candidates:
                src = (img.get("src") or img.get("data-src") or "").strip()
                if not src:
                    continue
                # Treat known placeholders / missing-avatar images as empty.
                if "no-avatar" in src or "default" in src or src.startswith("data:"):
                    continue
                # Normalise protocol-relative and root-relative URLs.
                if src.startswith("//"):
                    return "https:" + src
                if src.startswith("/"):
                    # Build the viewer domain root and prepend it.
                    m = re.match(r"^(https?://[^/]+)", self.prefix_url)
                    if m:
                        return m.group(1) + src
                    return src
                return src

            return ""
        except Exception:
            # Avatar parsing is optional/best-effort: never propagate errors.
            return ""

    def parse_profile(self) -> dict:
        """解析描述與 posts/followers/follows 數值（自動轉為 int）。"""
        if not self.soup:
            raise ValueError("請先呼叫 fetch_page()")

        if not getattr(self, 'is_valid_profile', True):
            _, followers_precise, _ = InstagramProfileScraper.get_embed_contents(username=self.username)
            result = self._empty_profile()
            result["followers_precise"] = followers_precise
            return result

        result = {}

        # 1) Description
        desc_tag = self.soup.find("div", class_="profile__description")
        result["description"] = desc_tag.get_text() if desc_tag else ""
        

        # 2) Stats (用 CSS selector 比對兩個 class)
        selectors = {
            "posts": "span.profile__stats-item-value.profile__stats-posts",
            "followers": "span.profile__stats-item-value.profile__stats-followers",
            "follows": "span.profile__stats-item-value.profile__stats-follows",
        }

        for key, sel in selectors.items():
            tag = self.soup.select_one(sel)
            raw = tag.get_text(strip=True) if tag else ""
            result[key] = self._to_int(raw)

        # --- Fallback（保險）：若上面沒抓到，嘗試從 li 的文字判斷 ---
        if result["posts"] == 0:
            li = self.soup.find("li", string=lambda t: t and "Posts" in t)
            if li:
                span = li.find("span", class_="profile__stats-item-value")
                result["posts"] = self._to_int(span.get_text(strip=True)) if span else result["posts"]

        if result["followers"] == 0:
            li = self.soup.find("li", string=lambda t: t and "Followers" in t)
            if li:
                span = li.find("span", class_="profile__stats-item-value")
                result["followers"] = self._to_int(span.get_text(strip=True)) if span else result["followers"]

        if result["follows"] == 0:
            li = self.soup.find("li", string=lambda t: t and ("Following" in t or "Follows" in t))
            if li:
                span = li.find("span", class_="profile__stats-item-value")
                result["follows"] = self._to_int(span.get_text(strip=True)) if span else result["follows"]

        context, followers_precise, full_name = InstagramProfileScraper.get_embed_contents(username=self.username)
        self.context = context

        # Fetch userid
        script_tag = self.soup.find("script", text=re.compile("USER_ID"))
        result["userid"] = "0"
        if script_tag:
            match = re.search(r"var\s+USER_ID\s*=\s*(\d+);", script_tag.string)
            if match:
                result["userid"] = match.group(1)
        
        # Get result
        result["followers_precise"] = followers_precise
        result["full_name"] = full_name
        result["posts_precise"] = context.get("posts_count", -1)
        result["top_posts"] = []
        graphql_media = context.get("graphql_media", None)
        if graphql_media:
            top_posts = InstagramProfileScraper.extract_posts(items=graphql_media)
            result["top_posts"] = top_posts
        result["profile_picture"] = self._extract_profile_picture()
        return result

    def close(self):
        self.driver.quit()


    
    @staticmethod
    def extract_contextJSON(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script")
        if not scripts:
            return ""

        # 掃描每個 script
        for script in scripts:
            js_text = script.string or script.get_text()
            if not js_text:
                continue
            match = re.search(r'contextJSON":"((?:\\.|[^"\\])*)"', js_text)
            if match:
                return match.group(1)

        return ""

    @staticmethod
    def extract_parsed_res(json_str_escaped:str):
        cleaned_str = json.loads(f'"{json_str_escaped}"').strip()
        try:
            parsed_res = json.loads(cleaned_str)
        except json.JSONDecodeError:
            # Some responses wrap the object as a JSON string; decode twice.
            parsed_res = json.loads(json.loads(f'"{json_str_escaped}"'))
        InstagramProfileScraper.parsed_res = parsed_res
        return parsed_res

    @staticmethod
    def get_context(parsed_res:dict) -> dict:
        context = parsed_res.get("context", {})
        return context

    @staticmethod
    def get_follwers_and_fullname(context:dict):
        if context != {}:
            followers = context.get("followers_count", -1)
            full_name = context.get("full_name", "")
            return followers, full_name
        return -1, ""

    @staticmethod
    def get_embed_contents(username:str):
        url = f"https://www.instagram.com/{username}/embed/?cr=1&v=12&wp=558&rd=file%3A%2F%2F&rp=%2Fprivate%2Fvar%2Fcontainers%2FBundle%2FApplication%2FE9786B06-828E-40D3-9B15-901CC8EAD855%2FAmeba.app%2F"
        response = requests.get(url=url)
        json_str_escaped = InstagramProfileScraper.extract_contextJSON(html=response.text)
        if not json_str_escaped or not isinstance(json_str_escaped, str):
            return {}, -1, ""
        parsed_res = InstagramProfileScraper.extract_parsed_res(json_str_escaped=json_str_escaped)
        context = InstagramProfileScraper.get_context(parsed_res=parsed_res)
        followers, full_name = InstagramProfileScraper.get_follwers_and_fullname(context=context)
        return context, followers, full_name

    @staticmethod
    def safe_get(obj: Any, *path) -> Optional[Any]:
        """Safely get a nested value by following the given path.
        The path can mix string keys (for dict) and integer indices (for list).
        Returns None if any step is invalid or missing."""
        cur = obj
        for p in path:
            if isinstance(p, int):
                if isinstance(cur, list) and 0 <= p < len(cur):
                    cur = cur[p]
                else:
                    return None
            else:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    return None
        return cur

    @staticmethod
    def extract_posts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract a list of simplified dicts with the five required fields.
        Handles missing values gracefully by returning None.
        Supports different input structures (shortcode_media, node, or direct fields)."""
        results: List[Dict[str, Any]] = []

        for item in items:
            # 兼容不同包裝層級：shortcode_media > node > 自身
            media = (
                item.get("shortcode_media")
                if isinstance(item, dict) else None
            )
            if media is None and isinstance(item, dict):
                media = item.get("node", item)

            result = {
                "timestamp": InstagramProfileScraper.safe_get(media, "taken_at_timestamp"),
                "caption": InstagramProfileScraper.safe_get(
                    media, "edge_media_to_caption", "edges", 0, "node", "text"
                ),
                "comment_count": InstagramProfileScraper.safe_get(
                    media, "edge_media_to_comment", "count"
                ),
                "like_count": InstagramProfileScraper.safe_get(
                    media, "edge_liked_by", "count"
                ),
                "shortcode": InstagramProfileScraper.safe_get(media, "shortcode"),
            }
            results.append(result)

        return results


def scrape_profile(username: str, wait_sec: int = 15, headless: bool = True) -> dict:
    """Fetch and parse a single profile, always releasing the browser.

    This is the one-shot entry point used by ``InstaPeriodScraper`` to enrich
    its output with authoritative profile metadata.  The caller is expected to
    handle exceptions; the browser is closed even on failure.
    """
    scraper = InstagramProfileScraper(wait_sec=wait_sec, headless=headless)
    try:
        scraper.fetch_page(username=username)
        return scraper.parse_profile()
    finally:
        scraper.close()