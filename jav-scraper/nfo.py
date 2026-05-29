"""NFO Generator for Jellyfin/Kodi"""
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlretrieve
from dataclasses import dataclass


@dataclass
class Actor:
    name: str
    thumb: str = None
    role: str = None


@dataclass
class Movie:
    id: str = ""
    title: str = ""
    original_title: str = ""
    plot: str = ""
    tagline: str = ""
    year: str = ""
    release_date: str = ""
    runtime: str = ""
    rating: float = 0.0
    votes: int = 0
    mpaa: str = ""
    studio: str = ""
    director: str = ""
    series: str = ""
    actors: list = None
    genres: list = None
    tags: list = None
    cover_url: str = ""
    fanart_urls: list = None
    trailer: str = ""
    source: str = ""

    def __post_init__(self):
        if self.actors is None:
            self.actors = []
        if self.genres is None:
            self.genres = []
        if self.tags is None:
            self.tags = []
        if self.fanart_urls is None:
            self.fanart_urls = []


def write_nfo(movie: Movie, output_path: Path) -> None:
    """Write NFO file for Jellyfin/Kodi
    
    Args:
        movie: Movie object with metadata
        output_path: Path to write the .nfo file
    """
    root = ET.Element("movie")
    
    # Title
    if movie.title:
        ET.SubElement(root, "title").text = movie.title
    
    # Original title
    if movie.original_title:
        ET.SubElement(root, "originaltitle").text = movie.original_title
    
    # Plot
    if movie.plot:
        ET.SubElement(root, "plot").text = movie.plot
    
    # Tagline
    if movie.tagline:
        ET.SubElement(root, "tagline").text = movie.tagline
    
    # Year
    if movie.year:
        ET.SubElement(root, "year").text = str(movie.year)
    
    # Release date (premiered)
    if movie.release_date:
        ET.SubElement(root, "premiered").text = movie.release_date
    
    # Runtime (in minutes)
    if movie.runtime:
        ET.SubElement(root, "runtime").text = str(movie.runtime)
    
    # Rating
    if movie.rating > 0:
        ET.SubElement(root, "rating").text = f"{movie.rating:.1f}"
    
    # Votes
    if movie.votes > 0:
        ET.SubElement(root, "votes").text = str(movie.votes)
    
    # MPAA
    mpaa = movie.mpaa or "NC-17"
    ET.SubElement(root, "mpaa").text = mpaa
    
    # Studio
    if movie.studio:
        ET.SubElement(root, "studio").text = movie.studio
    
    # Director
    if movie.director:
        ET.SubElement(root, "director").text = movie.director
    
    # Series (set)
    if movie.series:
        set_elem = ET.SubElement(root, "set")
        ET.SubElement(set_elem, "name").text = movie.series
    
    # Unique ID
    if movie.id:
        ET.SubElement(root, "uniqueid", type="num", default="true").text = movie.id
    
    # Genres
    for genre in movie.genres:
        ET.SubElement(root, "genre").text = genre
    
    # Tags
    for tag in movie.tags:
        ET.SubElement(root, "tag").text = tag
    
    # Country
    ET.SubElement(root, "country").text = "Japan"
    
    # Trailer
    if movie.trailer:
        ET.SubElement(root, "trailer").text = movie.trailer
    
    # Actors
    for actor in movie.actors:
        actor_elem = ET.SubElement(root, "actor")
        ET.SubElement(actor_elem, "name").text = actor.name
        if actor.role:
            ET.SubElement(actor_elem, "role").text = actor.role
        if actor.thumb:
            ET.SubElement(actor_elem, "thumb").text = actor.thumb
    
    # Fanart (as extra fanarts)
    for i, fanart_url in enumerate(movie.fanart_urls):
        fanart_elem = ET.SubElement(root, "fanart")
        ET.SubElement(fanart_elem, "thumb", preview=fanart_url).text = fanart_url
    
    # Write to file with proper XML declaration
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def download_cover(url: str, path: Path) -> bool:
    """Download cover image
    
    Args:
        url: URL of the cover image
        path: Local path to save the image
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if url:
            path.parent.mkdir(parents=True, exist_ok=True)
            urlretrieve(url, path)
            return True
    except Exception as e:
        print(f"Failed to download cover: {e}")
    return False


def test_nfo_generation():
    """Test NFO generation with mock data"""
    # Create mock movie
    movie = Movie(
        id="SSIS-001",
        title="一ヶ月間の禁欲の果てに彼女のルームメイト2人と浮気SEXだけに没頭した彼女不在の3日間。 葵つかさ 乙白さやか",
        original_title="",
        plot="After a month of abstinence, she spends three days cheating on her boyfriend with her two roommates while he's away.",
        tagline="",
        year="2021",
        release_date="2021-02-19",
        runtime="150",
        rating=8.5,
        votes=1250,
        mpaa="NC-17",
        studio="SSIS",
        director="",
        series="",
        actors=[
            Actor(name="葵つかさ", thumb="https://example.com/actress1.jpg", role="Actress"),
            Actor(name="乙白さやか", thumb="https://example.com/actress2.jpg", role="Actress"),
        ],
        genres=["巨乳", "中出", "単体作品", "、美乳"],
        tags=["中文字幕", "日产"],
        cover_url="https://pics.dmm.co.jp/digital/video/ssis00001/ssis00001pl.jpg",
        fanart_urls=[
            "https://pics.dmm.co.jp/digital/video/ssis00001/ssis00001jp-1.jpg",
            "https://pics.dmm.co.jp/digital/video/ssis00001/ssis00001jp-2.jpg",
        ],
        trailer="",
        source="fanza"
    )
    
    # Write to stdout for demo
    import io
    import sys
    
    # Create temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.nfo', delete=False, encoding='utf-8') as f:
        temp_path = f.name
    
    write_nfo(movie, Path(temp_path))
    
    # Read and print
    with open(temp_path, 'r', encoding='utf-8') as f:
        print(f.read())
    
    # Cleanup
    os.unlink(temp_path)
    
    print("\n" + "="*60)
    print("NFO generation test completed!")
    print("="*60)


if __name__ == "__main__":
    test_nfo_generation()