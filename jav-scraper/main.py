#!/usr/bin/env python
"""JAV Scraper CLI"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.jav321 import scrape_jav321
from models import Movie


def save_json(movie: Movie, output_path: str):
    """Save movie data as JSON"""
    data = {
        'id': movie.id,
        'title': movie.title,
        'original_title': movie.original_title,
        'plot': movie.plot,
        'tagline': movie.tagline,
        'year': movie.year,
        'release_date': movie.release_date,
        'runtime': movie.runtime,
        'rating': movie.rating,
        'mpaa': movie.mpaa,
        'studio': movie.studio,
        'director': movie.director,
        'series': movie.series,
        'actors': [{'name': a.name, 'thumb': a.thumb, 'role': a.role} for a in movie.actors],
        'genres': movie.genres,
        'tags': movie.tags,
        'cover_url': movie.cover_url,
        'fanart_urls': movie.fanart_urls,
        'trailer': movie.trailer,
        'source': movie.source,
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description='JAV Metadata Scraper')
    parser.add_argument('video_id', help='Video ID (e.g., SSIS-001)')
    parser.add_argument('--output', '-o', default='./output', help='Output directory')
    parser.add_argument('--source', '-s', default='jav321', choices=['jav321', 'r18'], help='Scraper source')
    parser.add_argument('--format', '-f', default='json', choices=['json', 'nfo'], help='Output format')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    # Scrape
    print(f'Scraping {args.video_id} from {args.source}...')
    
    if args.source == 'jav321':
        movie = scrape_jav321(args.video_id)
    else:
        print(f'Source {args.source} not implemented yet')
        return 1
    
    if not movie.title:
        print(f'Error: No title found for {args.video_id}')
        return 1
    
    print(f'Title: {movie.title}')
    print(f'Actors: {[a.name for a in movie.actors]}')
    
    # Save JSON
    output_file = os.path.join(args.output, f'{args.video_id}.{args.format}')
    save_json(movie, output_file)
    print(f'Saved: {output_file}')
    
    return 0


if __name__ == '__main__':
    sys.exit(main())