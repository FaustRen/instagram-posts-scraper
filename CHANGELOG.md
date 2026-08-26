# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-08-27

This release restores post collection, which was completely broken: every
account returned empty `posts` and `init_posts` while reporting success.

### Fixed

- **Empty `posts` and `init_posts` for every account.** Three independent
  causes had to be fixed together:
  - *Domain moved again.* `picnob.com` now answers `403` and redirects to
    `pixnoy.com`. Every URL is now derived from a single `BASE_URL` constant
    instead of being hard-coded in four places.
  - *Headless UC mode can no longer clear Cloudflare.* `uc_open_with_reconnect`
    stalls on the Turnstile interstitial ("Just a moment...") indefinitely, so
    the profile page was never reached. The browser now uses SeleniumBase CDP
    mode (`activate_cdp_mode`) with a bounded captcha-click retry loop, and
    verifies the real page actually loaded instead of assuming it did.
  - *Failures were silent.* A blocked run and a deleted account both yielded
    `account_status: "missing"` with empty lists and no error, so the breakage
    looked like valid data.
- **Truncated API responses.** `cdp.get_text()` caps body text at ~10k
  characters, which silently corrupted the posts JSON mid-string. Body text is
  now read via `cdp.evaluate("document.body.innerText")`, which returns the
  full payload.
- **`RuntimeError: Cannot run the event loop while another loop is running`.**
  CDP mode drives Chrome with `loop.run_until_complete()`, which fails inside
  Jupyter/IPython because the kernel already owns an event loop. A running loop
  is now detected and made re-entrant via `nest_asyncio`.

### Added

- `InstaPeriodScraper(posts_headless=...)` to control the posts browser
  independently of the existing `profile_headless`.
- `warning: "cloudflare_challenge_unsolved"` in the result when the challenge
  could not be cleared, so a blocked run is distinguishable from a genuinely
  missing account.
- `looks_like_cloudflare_challenge()` helper and a `BASE_URL` constant.

### Changed

- **The posts browser now runs headed by default.** Headless Chrome cannot pass
  Cloudflare's Turnstile, so `posts_headless` defaults to `False` and a browser
  window will appear during scraping. Set `posts_headless=True` to override
  (expect Cloudflare to block it).
- Requests through the live driver now navigate via CDP, falling back to plain
  WebDriver when CDP is unavailable.
- Ad dismissal and session capture degrade gracefully instead of raising: their
  WebDriver-only APIs (`switch_to`, `find_elements`, `get_cookies`) are not
  available while the driver is in CDP mode.
- Bumped `seleniumbase` to `>=4.50.2` (required for `activate_cdp_mode`) and
  added `nest_asyncio` as a dependency.

### Removed

- Unused `WebDriverWait` / `expected_conditions` imports, left over from the
  replaced page-load wait.

## [0.2.0] - 2026-08-21

## [0.2.0] - 2026-08-21

### Added

- `init_posts` entries now include a `thumbnail` field with the picnob cover
  image URL, extracted from the already-loaded browser DOM (no extra
  request). Falls back from `src` to `data-src`, and stays `None` when the
  image is unavailable. This is backward compatible — no existing fields or
  method signatures changed.

## [0.1.0] - 2026-06-30

This release redesigns the profile/post integration into a single, consolidated
output schema. **It contains breaking changes to the output structure and the
package layout.**

### Changed (breaking) — output schema

- The result is now a single consolidated dictionary. Top-level shape:
  `profile`, `account_status`, `updated_at`, `posts`, `init_posts`, `top_posts`.
- Renamed the broad post collection key `data` → `posts`. Each post in `posts`
  is normalized to a single, consistent shape:
  `shortcode`, `caption`, `media_type`, `is_video`, `timestamp`,
  `like_count` (int), `comment_count` (int), `thumbnail`, `image_url`.
- Redesigned the `profile` block with stable, normalized keys:
  `username`, `userid`, `full_name`, `biography`, `followers`, `following`,
  `posts_count`, `profile_picture`.
  - `introduction` (list) and `description` were merged into a single
    canonical `biography` string.
  - `counts_of_posts` → `posts_count`; `followings` → `following`
    (now returned as integers).
- Profile-metadata ownership is now explicit:
  - `followers` comes from the profile scraper's precise count
    (`followers_precise`); picnob HTML is only a fallback.
  - `following` comes from the picnob source (`followings`); the profile
    scraper value is only a fallback.
  - `posts_count` prefers the profile scraper's precise count, falling back to
    picnob.

### Added

- `instagram_posts_scraper/schema.py`: a small, pure normalization layer that
  owns the consolidated output schema (`build_profile`, `normalize_posts`,
  `build_result`) and the data-ownership rules. It is import-free of any
  scraping side effects and is unit-testable offline.
- `init_posts`: the raw picnob first-page HTML posts, preserved verbatim
  (original keys and content) so no source data is lost.
- `top_posts`: the profile scraper's highlight posts, preserved verbatim.
- `InstaPeriodScraper(use_profile_scraper=True, profile_headless=True)`: optional
  enrichment of profile metadata via the dedicated profile scraper, with a
  graceful fallback to picnob values when it is unavailable.
- `scrape_profile()`: a one-shot helper that fetches and parses a single
  profile while always releasing the browser.
- `InstagramProfileScraper` and `scrape_profile` are now exported from the
  package root.

### Moved / Removed

- Moved the profile scraper out of the generic `utils/` package:
  `utils/get_profile.py` → `instagram_posts_scraper/profile_scraper.py`.
- Removed the dead, shadowed top-level `utils.py` (it was unreachable because
  the `utils/` package shadowed it and duplicated its helpers).
- Removed the empty `ScrapedDataManager` placeholder and the three redundant
  result-builder methods (`get_public_account_res`, `get_private_account_res`,
  `get_missing_account_res`), now superseded by `schema.build_result`.

### Migration notes

- Read posts from `result["posts"]` instead of `result["data"]`.
- Read profile counts from `result["profile"]["followers"]` /
  `["following"]` / `["posts_count"]` (now integers) instead of
  `followers` / `followings` / `counts_of_posts` (strings).
- Read the biography from `result["profile"]["biography"]` instead of
  `introduction` / `description`.
- `init_posts` and `top_posts` remain available with their original shapes.

## [0.0.8]

- Previous baseline release.
