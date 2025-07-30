# -*- coding: utf-8 -*-
import setuptools
from setuptools import setup, find_packages

setup(
    name='instagram-posts-scraper',
    version='0.0.5',
    packages=[
        "instagram_posts_scraper",
        "instagram_posts_scraper.utils"
    ],
    license='MIT',
    description='Implement Instagram Posts Scraper for post data retrieval',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='FaustRen',
    author_email='faustren1z@gmail.com',
    url='https://github.com/FaustRen/instagram-posts-scraper',
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.11',
)