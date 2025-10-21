#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="django-quickwit-log",
    version="0.1.2",
    author="Shaghayegh Ghorbanpoor",
    author_email="ghorbanpoor.shaghayegh@gmail.com",
    description="A Django package for integrating Quickwit with JSON log management and MinIO storage",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.sanaap.co/backend-base/modules/quickwit-log",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "django-quickwit-manage=django_quickwit_log.management:main",
        ],
    },
)
