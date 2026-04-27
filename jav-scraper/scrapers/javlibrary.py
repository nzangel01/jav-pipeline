import httpx
from bs4 import BeautifulSoup
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Movie, Actor


class JavLibraryScraper:
    """Scrape JAV from javlibrary.com"""
    
    def __init__(self):
        self.base_url = 'https://www.y78k.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9',
            'Referer': 'https://www.javlibrary.com/',
        }
        self.client = httpx.Client(timeout=30.0, headers=self.headers, follow_redirects=True)
    
    def fetch_url(self, url: str) -> BeautifulSoup:
        resp = self.client.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'lxml')
    
    def _search_url(self, video_id: str) -> str:
        return f'{self.base_url}/cn/vl_searchbyid.php?keyword={video_id}'
    
    def scrape(self, video_id: str) -> Movie:
        url = self._search_url(video_id)
        soup = self.fetch_url(url)
        
        movie = Movie(id=video_id, source='javlibrary')
        
        # Title: h3.post-title text a
        title_elem = soup.select_one('h3.post-title a')
        if title_elem:
            movie.title = title_elem.get_text(strip=True)
        
        # Cover: img#video_jacket_img
        cover_elem = soup.select_one('img#video_jacket_img')
        if cover_elem:
            movie.cover_url = cover_elem.get('src', '')
        
        # Actors: span.cast span.star a
        actor_elems = soup.select('span.cast span.star a')
        for a in actor_elems:
            name = a.get_text(strip=True)
            if name:
                movie.actors.append(Actor(name=name))
        
        # Genres: .genre
        genre_elems = soup.select('.genre')
        for g in genre_elems:
            genre = g.get_text(strip=True)
            if genre:
                movie.genres.append(genre)
        
        # Studio
        studio_elem = soup.select_one('.studio a')
        if studio_elem:
            movie.studio = studio_elem.get_text(strip=True)
        
        # Release date
        date_elem = soup.select_one('.date')
        if date_elem:
            movie.release_date = date_elem.get_text(strip=True)
        
        # Runtime
        runtime_elem = soup.select_one('.runtime')
        if runtime_elem:
            movie.runtime = runtime_elem.get_text(strip=True)
        
        return movie
    
    def close(self):
        self.client.close()


def scrape_javlibrary(video_id: str) -> Movie:
    """Scrape JAV from javlibrary.com"""
    scraper = JavLibraryScraper()
    try:
        return scraper.scrape(video_id)
    finally:
        scraper.close()