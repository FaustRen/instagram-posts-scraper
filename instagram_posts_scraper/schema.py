# -*- coding: utf-8 -*-
"""Consolidated output schema for the Instagram scraper.

This module owns the single, authoritative shape of the scraper's result and
the rules for which source owns each field.  Keeping all normalization here
(instead of scattering it across the scraper) makes the schema easy to read,
test, and evolve.

Data ownership
--------------
* Profile metadata (followers / following / posts_count / biography /
  full_name / userid / profile_picture) is owned by the *profile scraper*
  (``InstagramProfileScraper``), which exposes precise Instagram values.
  The picnob HTML profile is used only as a fallback when the profile
  scraper is unavailable.
* The post collection is owned by the *posts scraper* (picnob API), which
  provides the broadest coverage.  Each post is normalized to a single,
  consistent engagement shape.

The output intentionally avoids duplicated semantic fields (e.g. the old
``introduction`` vs ``description`` pair, or the ``count_like`` /
``count_like_pure`` pair).
"""
from typing import Any, Dict, List, Optional


# ── primitive helpers ───────────────────────────────────────────────────────

def to_int(value: Any) -> Optional[int]:
    """Best-effort conversion of scraped count values to ``int``.

    Accepts plain ints, numeric strings such as ``"3,588"`` and ``"526"``.
    Returns ``None`` when the value cannot be interpreted as a whole number.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_positive(*values: Any) -> Optional[int]:
    """Return the first value that is a positive integer, else the first
    non-None integer, else ``None``.

    Profile-scraper precise counts use ``-1`` / ``0`` as "unknown" sentinels,
    so positive values are always preferred over the picnob fallback.
    """
    fallback: Optional[int] = None
    for value in values:
        number = to_int(value)
        if number is None:
            continue
        if number > 0:
            return number
        if fallback is None:
            fallback = number
    return fallback


# ── post normalization ──────────────────────────────────────────────────────

def normalize_api_post(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single picnob API post into the canonical post schema."""
    return {
        "shortcode": item.get("shortcode"),
        "caption": _clean_text(item.get("sum_pure") or item.get("sum")),
        "media_type": item.get("type"),
        "is_video": item.get("is_video"),
        "timestamp": item.get("time"),
        "like_count": to_int(item.get("count_like")),
        "comment_count": to_int(item.get("count_comment")),
        "thumbnail": item.get("thum"),
        "image_url": item.get("down_pic") or item.get("pic"),
    }


def normalize_html_post(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a first-page HTML post (degraded fallback) into the same
    canonical post schema.  HTML posts lack shortcodes and precise timestamps,
    so those fields are ``None``.
    """
    return {
        "shortcode": None,
        "caption": _clean_text(item.get("text")),
        "media_type": None,
        "is_video": None,
        "timestamp": None,
        "like_count": to_int(item.get("likes")),
        "comment_count": to_int(item.get("comments")),
        "thumbnail": None,
        "image_url": None,
    }


def normalize_posts(
    api_items: Optional[List[Dict[str, Any]]] = None,
    html_items: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build the canonical post collection.

    Prefers the broad picnob API collection; falls back to the HTML first-page
    posts only when the API collection is empty.
    """
    if api_items:
        return [normalize_api_post(item) for item in api_items]
    if html_items:
        return [normalize_html_post(item) for item in html_items]
    return []


# ── profile normalization ───────────────────────────────────────────────────

def _biography_from_picnob(introduction: Any) -> Optional[str]:
    """Collapse picnob's ``introduction`` list into a single canonical string."""
    if introduction is None:
        return None
    if isinstance(introduction, str):
        return _clean_text(introduction)
    if isinstance(introduction, list):
        joined = "\n".join(str(part).strip() for part in introduction if str(part).strip())
        return _clean_text(joined)
    return _clean_text(introduction)


def build_profile(
    username: str,
    picnob_profile: Optional[Dict[str, Any]] = None,
    profile_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the canonical profile block from the two sources.

    Args:
        username: The requested account handle.
        picnob_profile: Raw profile values scraped from picnob HTML, using the
            legacy keys ``introduction`` / ``followers`` / ``followings`` /
            ``counts_of_posts`` / ``userid``.  May be ``None``.
        profile_meta: The result of ``InstagramProfileScraper.parse_profile``.
            Authoritative for metadata.  May be ``None`` when the profile
            scraper is disabled or failed.

    Returns:
        A normalized profile dict with stable field names.
    """
    picnob_profile = picnob_profile or {}
    profile_meta = profile_meta or {}

    biography = (
        _clean_text(profile_meta.get("description"))
        or _biography_from_picnob(picnob_profile.get("introduction"))
    )

    return {
        "username": username,
        "userid": (
            _clean_text(profile_meta.get("userid"))
            or _clean_text(picnob_profile.get("userid"))
        ),
        "full_name": _clean_text(profile_meta.get("full_name")),
        "biography": biography,
        # followers is owned by the profile scraper's precise count
        # (``followers_precise``); picnob HTML is only a last-resort fallback.
        "followers": _first_positive(
            profile_meta.get("followers_precise"),
            picnob_profile.get("followers"),
        ),
        # following stays on the original picnob source (``followings``);
        # the profile scraper value is only a fallback.
        "following": _first_positive(
            picnob_profile.get("followings"),
            profile_meta.get("follows"),
        ),
        "posts_count": _first_positive(
            profile_meta.get("posts_precise"),
            profile_meta.get("posts"),
            picnob_profile.get("counts_of_posts"),
        ),
        "profile_picture": _clean_text(profile_meta.get("profile_picture")),
    }


# ── result assembly ─────────────────────────────────────────────────────────

def build_result(
    account_status: str,
    profile: Dict[str, Any],
    updated_at: Any,
    posts: Optional[List[Dict[str, Any]]] = None,
    init_posts: Optional[List[Dict[str, Any]]] = None,
    top_posts: Optional[List[Dict[str, Any]]] = None,
    warning: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the final consolidated scraper result.

    ``posts`` is the normalized, broad-coverage collection.  ``init_posts`` and
    ``top_posts`` are preserved verbatim from their owning scrapers (picnob
    first-page HTML and the profile scraper respectively); their keys and
    contents are intentionally left untouched so no source data is lost.
    """
    result: Dict[str, Any] = {
        "profile": profile,
        "account_status": account_status,
        "updated_at": updated_at,
        "posts": posts or [],
        "init_posts": init_posts or [],
        "top_posts": top_posts or [],
    }
    if warning:
        result["warning"] = warning
    return result
