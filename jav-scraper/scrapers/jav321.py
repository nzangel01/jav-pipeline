import httpx
from lxml import html
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Movie, Actor


class Jav321Scraper:
    """Scrape JAV from jav321.com"""
    
    def __init__(self):
        self.base_url = 'https://www.jav321.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ja,en-US;q=0.9',
        }
        self.client = httpx.Client(timeout=30.0, headers=self.headers, follow_redirects=True)
    
    def fetch_url(self, url: str):
        resp = self.client.get(url)
        resp.raise_for_status()
        return html.fromstring(resp.text)
    
    def scrape(self, video_id: str) -> Movie:
        # POST search - follow_redirects goes to video page directly
        search_url = f'{self.base_url}/search'
        resp = self.client.post(search_url, data={'sn': video_id})
        tree = html.fromstring(resp.text)
        
        movie = Movie(id=video_id, source='jav321')
        
        # Title: //div[@class="panel-heading"]/h3/text()
        title_elem = tree.xpath('//div[@class="panel-heading"]//text()')
        if title_elem:
            # Get first non-empty text which is the title
            for t in title_elem:
                if t.strip():
                    movie.title = t.strip()
                    break
        
        # Genres: //a[contains(@href,"/genre/")]/text()
        genre_elems = tree.xpath('//a[contains(@href,"/genre/")]/text()')
        for g in genre_elems:
            if g.strip():
                movie.genres.append(g.strip())
        
        # Actors: //a[contains(@href,"/star/")]/text() - unique names
        seen_actors = set()
        actress_elems = tree.xpath('//a[contains(@href,"/star/")]/text()')
        for a in actress_elems:
            if a.strip() and a.strip() not in seen_actors:
                seen_actors.add(a.strip())
                movie.actors.append(Actor(name=a.strip()))
        
        # Cover: //img[@class="img-responsive"]/@src
        cover_elems = tree.xpath('//img[@class="img-responsive"]/@src')
        if cover_elems:
            movie.cover_url = cover_elems[0]
        
        # Studio: //a[contains(@href,"/studio/")]/text()
        studio_elems = tree.xpath('//a[contains(@href,"/studio/")]/text()')
        if studio_elems:
            movie.studio = studio_elems[0].strip()
        
        # Date: //div[@class="panel-heading"]//text() - get date from title
        # (date is embedded in the title or separate)
        
        return movie
    
    def close(self):
        self.client.close()


def scrape_jav321(video_id: str) -> Movie:
    """Scrape JAV from jav321.com"""
    scraper = Jav321Scraper()
    try:
        return scraper.scrape(video_id)
    finally:
        scraper.close()