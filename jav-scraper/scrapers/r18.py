import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import BaseScraper
from models import Movie, Actor


class R18Scraper(BaseScraper):
    """Scrape JAV from r18.com / DMM proxy"""
    
    def __init__(self):
        super().__init__('https://www.r18.com')
    
    def _search_url(self, video_id: str) -> str:
        """Generate search URL for video ID"""
        return f'{self.base_url}/common/search/searchkey={video_id}/'
    
    def scrape(self, video_id: str) -> Movie:
        """Scrape movie by ID"""
        url = self._search_url(video_id)
        soup = self.fetch_url(url)
        
        movie = Movie(id=video_id, source='r18')
        
        # Title: cite[itemprop=name]
        title_elem = soup.select_one('cite[itemprop=name]')
        if not title_elem:
            title_elem = soup.select_one('h3.product-title')
        if title_elem:
            movie.title = title_elem.get_text(strip=True)
        
        # Cover: img[itemprop=image]
        cover_elem = soup.select_one('img[itemprop=image]')
        if not cover_elem:
            cover_elem = soup.select_one('div.product-image img')
        if cover_elem:
            movie.cover_url = cover_elem.get('src', '')
        
        # Actors: div.txt01 a
        actor_elems = soup.select('div.txt01 a')
        for a in actor_elems:
            name = a.get_text(strip=True)
            if name and name != 'MORE':
                movie.actors.append(Actor(name=name))
        
        # Genres: div.product-categories-list .pop-list a
        genre_elems = soup.select('div.product-categories-list .pop-list a')
        for g in genre_elems:
            genre = g.get_text(strip=True)
            if genre:
                movie.genres.append(genre)
        
        # Studio
        studio_elem = soup.select_one('div.maker-products a')
        if studio_elem:
            movie.studio = studio_elem.get_text(strip=True)
        
        return movie


def scrape_r18(video_id: str) -> Movie:
    """Scrape JAV from r18.com"""
    scraper = R18Scraper()
    try:
        return scraper.scrape(video_id)
    finally:
        scraper.close()