# Instagram Posts Scraper

InstagramPostsScraper is a Python library for collect instagram users' data.

The data obtained by web crawlers is not real-time data, but rather data from a specific point in time on the same day.

I’d really appreciate your support! You can star ⭐ or fork this repository to help me keep sharing more interesting web scrapers.

# Support Me

If you enjoy this project and would like to support me, please consider donating 🙌  
Your support will help me continue developing this project and working on other exciting ideas!

## 💖 Ways to Support:

- **PayPal**: [https://www.paypal.me/faustren1z](https://www.paypal.me/faustren1z)
- **Buy Me a Coffee**: [https://buymeacoffee.com/faustren1z](https://buymeacoffee.com/faustren1z)

Thank you for your support!! 🎉


## Requirements
```bash
beautifulsoup4==4.13.4
cloudscraper==1.2.71
lxml==6.1.1
pandas==2.2.3
pytz==2024.2
requests==2.32.3
selenium==4.33.0
seleniumbase==4.39.2
```

## Installation

To install the latest release from PyPI:

```sh
pip install instagram-posts-scraper
```

## Usage - Sample

```python
from instagram_posts_scraper.instagram_posts_scraper import InstaPeriodScraper
from IPython.display import display

ig_posts_scraper = InstaPeriodScraper()
target_info = {"username": "stephencurry30", "days_limit": 5}
res = ig_posts_scraper.get_posts(target_info=target_info)
display(res)
```

### Optional parameters

- **username**: target instagram user 
- **days_limit**: Number of days within which to scrape posts..

## Version

You can check the installed version and module documentation:

```python
import instagram_posts_scraper

print(instagram_posts_scraper.__version__)  # e.g. 0.1.0
print(instagram_posts_scraper.__doc__)      # module documentation
```

## Sample Output

The scraper returns a single consolidated dictionary containing the target's
normalized `profile`, the `account_status`, the scraping timestamp
(`updated_at`), a `posts` list of normalized posts, plus the raw `init_posts`
(picnob first-page HTML posts) and `top_posts` (profile-scraper highlights)
collections, which are preserved verbatim so no source data is lost.

Profile metadata is normalized: `followers` comes from the profile scraper's
precise count, while `following` and the biography fallback come from picnob.
Each entry in `posts` is normalized to a single, consistent engagement shape
(`like_count` / `comment_count` as integers). `init_posts` and `top_posts` keep
their original shapes untouched.

Below is an **abbreviated** example (long media URLs are truncated with `...` for readability).
For the complete, real output see
[`examples/example_output.json`](examples/example_output.json).

```jsonc
{
  "profile": {
    "username": "1989ivyshao",
    "userid": "370962121",
    "full_name": "邵雨薇IvyShao",
    "biography": "噓！隱藏版的我 @venusv.magazine ...",
    "followers": 1015244,
    "following": 526,
    "posts_count": 3588,
    "profile_picture": "https://cdn.insta-stories-viewer.com/..."
  },
  "account_status": "public",
  "updated_at": "2026-06-30T12:16:47.909382+08:00",
  "posts": [
    {
      "shortcode": "6739181536421845293566",
      "caption": "生活就是一些小小的習慣堆起來的 ...",
      "media_type": "img_multi",
      "is_video": false,
      "timestamp": 1778063737,
      "like_count": 9160,
      "comment_count": 42,
      "thumbnail": "https://scontent-ord5-1.cdninstagram.com/...",
      "image_url": "https://scontent.cdninstagram.com/..."
    }
    // ... more posts
  ],
  "init_posts": [
    { "text": "...", "likes": "9,160", "comments": "42", "time": "1 month ago" }
    // ... picnob first-page posts, preserved verbatim
  ],
  "top_posts": [
    {
      "timestamp": 1782697176,
      "caption": "最近",
      "comment_count": 32,
      "like_count": 6522,
      "shortcode": "DaJtQsTmTPP"
    }
    // ... profile-scraper highlights, preserved verbatim
  ]
}
```