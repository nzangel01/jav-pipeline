import gradio as gr
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrapers.jav321 import Jav321Scraper
from models import Movie

MOCK_DATA = {
    "SSIS-001": {
        "title": "After a month of abstinence, she was consumed by extramarital sex with her two roommates during the three days she was away.",
        "original_title": "一ヶ月間の禁怠の果てに彼女のルームメイト2人と浮きSEXブログに表示した彼女不在の3日間。",
        "actresses": ["葵つかさ", "乙白さやか"],
        "genres": ["AV opener", "Cosplay", "Facial", "Three-person", "Creampie"],
        "studio": "S1",
        "release_date": "2021-02-19",
        "duration": 147,
        "cover_url": "https://pics.d3.dmm.com/digital/video/ssis00001/ssis00001jp-1.jpg",
        "plot": "S1 brand's beautiful slim actress's luxurious co-star emotional drama! My girlfriend and two friends live together...",
        "cid": "ssis00001",
    }
}

OUTPUT_DIR = "/mnt/takao_data/JAV/scraped"


def mock_scrape(jav_id: str, source: str):
    jav_id = jav_id.strip().upper()
    if jav_id in MOCK_DATA:
        return MOCK_DATA[jav_id].copy()
    return {
        "title": f"Mock title for {jav_id}",
        "original_title": "",
        "actresses": ["Unknown"],
        "genres": [],
        "studio": "Unknown",
        "release_date": "",
        "duration": 0,
        "cover_url": "",
        "plot": f"No data for {jav_id}",
        "cid": jav_id.lower().replace("-", ""),
    }


def save_nfo(data):
    if not data or "title" not in data:
        return "No data"
    
    cid = data.get("cid", "unknown")
    title = data.get("title", "")[:50]
    studio = data.get("studio", "Unknown")
    
    folder = os.path.join(OUTPUT_DIR, studio, f"[{cid}] {title}")
    os.makedirs(folder, exist_ok=True)
    
    nfo = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<movie>
  <title>{cid} {data.get("title", "")}</title>
  <originaltitle>{data.get("original_title", "")}</originaltitle>
  <plot>{data.get("plot", "")}</plot>
  <runtime>{data.get("duration", 0)}</runtime>
  <uniqueid type="num" default="true">{cid}</uniqueid>
  <uniqueid type="cid">{data.get("cid", "")}</uniqueid>
  <genre>{", ".join(data.get("genres", []))}</genre>
  <country>Japan</country>
  <premiered>{data.get("release_date", "")}</premiered>
  <studio>{data.get("studio", "")}</studio>
</movie>'''
    
    with open(os.path.join(folder, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write(nfo)
    return f"Saved: {folder}/movie.nfo"


def scrape(jav_id: str, source: str):
    if not jav_id:
        return {k: "" for k in ["title","original_title","actresses","genres","studio","release_date","duration","cover_url","plot","cid","_data"]}
    
    scraper = Jav321Scraper()
    movie = scraper.scrape(jav_id)
    
    return {
        "title": movie.title,
        "original_title": movie.original_title,
        "actresses": ", ".join([a.name for a in movie.actors]),
        "genres": ", ".join(movie.genres),
        "studio": movie.studio,
        "release_date": movie.release_date,
        "duration": movie.runtime,
        "cover_url": movie.cover_url,
        "plot": movie.plot,
        "cid": movie.id,
        "_data": {
            "title": movie.title,
            "original_title": movie.original_title,
            "actresses": [a.name for a in movie.actors],
            "genres": movie.genres,
            "studio": movie.studio,
            "release_date": movie.release_date,
            "duration": movie.runtime,
            "cover_url": movie.cover_url,
            "plot": movie.plot,
            "cid": movie.id,
        },
    }


with gr.Blocks(title="JAV Scraper") as demo:
    gr.Markdown("## JAV Scraper GUI")
    
    with gr.Row():
        with gr.Column(scale=1):
            jav_id = gr.Textbox(label="JAV ID", placeholder="SSIS-001")
            source = gr.Dropdown(["Auto","JavLibrary","R18","DMM","Fanza"], label="Source", value="Auto")
            scrape_btn = gr.Button("Scrape", variant="primary")
        
        with gr.Column(scale=2):
            cover = gr.Image(label="Cover")
    
    with gr.Row():
        with gr.Column():
            title = gr.Textbox(label="Title")
            original_title = gr.Textbox(label="Original Title")
            actresses = gr.Textbox(label="Actresses")
            genres = gr.Textbox(label="Genres")
    
    with gr.Row():
        with gr.Column():
            studio = gr.Textbox(label="Studio")
            release_date = gr.Textbox(label="Release Date")
            duration = gr.Textbox(label="Duration")
            plot = gr.Textbox(label="Plot", lines=3)
    
    data_state = gr.State()
    save_status = gr.Textbox(label="Save Status", interactive=False)
    
    def on_scrape(jid, src):
        result = scrape(jid, src)
        return (
            result.get("title", ""),
            result.get("original_title", ""),
            result.get("actresses", ""),
            result.get("genres", ""),
            result.get("studio", ""),
            result.get("release_date", ""),
            result.get("duration", ""),
            result.get("plot", ""),
            result.get("cover_url", ""),
            result.get("_data", {}),
            "",
        )
    
    scrape_btn.click(
        on_scrape,
        inputs=[jav_id, source],
        outputs=[title, original_title, actresses, genres, studio, release_date, duration, plot, cover, data_state, save_status]
    )
    
    jav_id.submit(
        on_scrape,
        inputs=[jav_id, source],
        outputs=[title, original_title, actresses, genres, studio, release_date, duration, plot, cover, data_state, save_status]
    )
    
    gr.Markdown("---")
    gr.Markdown("### Save NFO")
    with gr.Row():
        save_btn = gr.Button("Save NFO")
    
    def on_save(data):
        if data:
            return save_nfo(data)
        return "No data"
    
    save_btn.click(on_save, inputs=[data_state], outputs=[save_status])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)