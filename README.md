# 1001Downloader

This repo contains a tool that is able to download the data from https://1001tracklists.com/!

The goal is to extract the semantic graph used in the background.

## Usage

To start scraping the web page:
```
cd src/
pip3 install -r requirements.txt
python3 main.py
```

To convert the scraped data to a turtle file:
```
cd src/
python3 main_transformttl.py
```
