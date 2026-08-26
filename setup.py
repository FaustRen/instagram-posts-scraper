# -*- coding: utf-8 -*-
import re
from pathlib import Path

from setuptools import setup


def read_version():
    """Read __version__ from the package __init__.py (single source of truth)."""
    init_file = Path(__file__).parent / "instagram_posts_scraper" / "__init__.py"
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_file.read_text())
    if not match:
        raise RuntimeError("Unable to find __version__ in __init__.py")
    return match.group(1)


setup(
    name='instagram-posts-scraper',
    version=read_version(),
    packages=[
        "instagram_posts_scraper",
        "instagram_posts_scraper.utils"
    ],
    license='MIT',
    description='Implement Instagram Posts Scraper for post data retrieval',
    long_description=Path('readme.md').read_text(encoding='utf-8'),
    long_description_content_type='text/markdown',
    author='FaustRen',
    author_email='faustren1z@gmail.com',
    url='https://github.com/FaustRen/instagram-posts-scraper',
    install_requires=[
        # Lower bounds only: require at least the versions tested against,
        # but don't force-downgrade a user's newer packages.
        "beautifulsoup4>=4.13.4",
        "cloudscraper>=1.2.71",
        "lxml>=6.1.1",
        # Lets CDP mode run inside Jupyter/IPython, which already owns a loop.
        "nest_asyncio>=1.6.0",
        "pandas>=2.2.3",
        "pytz>=2024.2",
        "requests>=2.32.3",
        "selenium>=4.33.0",
        # 4.50+ is required for activate_cdp_mode(), the only working CF bypass.
        "seleniumbase>=4.50.2",
    ],
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.11',
)