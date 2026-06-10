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

print(instagram_posts_scraper.__version__)  # e.g. 0.0.8
print(instagram_posts_scraper.__doc__)      # module documentation
```

## Sample Output

The scraper returns a dictionary containing the target's `profile`, `account_status`,
the scraping timestamp (`updated_at`), and a `data` list of posts.

Below is an **abbreviated** example (long media URLs are truncated with `...` for readability).
For the complete, real output see
[`examples/example_output.json`](examples/example_output.json).

```jsonc
{
  "profile": {
    "introduction": [
      "Believer. Husband. Father. Founder. Philanthropist. Olympic Gold Medalist. NYT Best Selling Author. Philippians 4:13."
    ],
    "counts_of_posts": "1542",
    "followers": "57197761",
    "followings": "1277"
  },
  "account_status": "public",
  "updated_at": "2026-06-10T19:37:53.477096+08:00",
  "data": [
    {
      "type": "igtv",
      "sum": "#sponsored I won’t spoil it. You kinda have to see it for yourself 👀",
      "sum_pure": "#sponsored I won’t spoil it. You kinda have to see it for yourself",
      "shortcode": "6747491750303413544165",
      "time": 1774973529,
      "ftime": "2 months ago",
      "count_like": 140546,
      "count_comment": 753,
      "count_like_pure": "140k",
      "count_comment_pure": "753",
      "thum": "https://scontent-iad3-1.cdninstagram.com/...",
      "pic": "https://scontent-iad3-1.cdninstagram.com/...",
      "pic_p": "https://sp1.picnob.com/...",
      "down_pic": "https://scontent.cdninstagram.com/...",
      "is_video": true,
      "video": "https://scontent-iad3-1.cdninstagram.com/...",
      "down_video": "https://scontent.cdninstagram.com/..."
    }
    // ... more posts
  ]
}
```