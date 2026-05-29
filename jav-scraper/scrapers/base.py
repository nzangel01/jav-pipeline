from abc import ABC, abstractmethod
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
from bs4 import BeautifulSoup
from models import Movie, Actor


class BaseScraper(ABC):
    """Abstract base class for JAV scrapers"""
    
    def __init__(self, base_url: str = "", headers: dict = None):
        self.base_url = base_url
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self.client = httpx.Client(timeout=30.0, headers=self.headers, follow_redirects=True)
    
    def fetch_url(self, url: str) -> BeautifulSoup:
        """Fetch URL and return BeautifulSoup object"""
        resp = self.client.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'lxml')
    
    @abstractmethod
    def scrape(self, video_id: str):
        """Scrape movie by ID"""
        pass
    
    def close(self):
        """Close HTTP client"""
        self.client.close()