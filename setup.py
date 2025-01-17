from setuptools import setup, find_packages

setup(
    name="podcast2rss",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pendulum",
        "requests",
        "python-dotenv",
        "retrying",
        "pyyaml"
    ],
)
