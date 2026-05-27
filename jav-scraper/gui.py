import gradio as gr
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrapers.jav321 import Jav321Scraper

QUEUE_FILE = os.path.expanduser("~/jav-pipeline/jav-scraper/queue.json")
OUTPUT_DIR = "/mnt/takao_data/JAV/scraped"
JAV_PATTERN = re.compile(r'([A-Z]{2,5}-\d{3,5})', re.IGNORECASE)


def load_queue():
    try:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE) as f:
                return json.load(f)
    except:
        pass
    return {"pending": [], "done": [], "failed": []}


def save_queue(q):
    with open(QUEUE_FILE, 'w') as f:
        json.dump(q, f, ensure_ascii=False, indent=2)


def add_to_queue(jid):
    q = load_queue()
    jid = jid.strip().upper()
    if jid and jid not in q["pending"]:
        q["pending"].append(jid)
        save_queue(q)
    return f"Added {jid}"


def scan_folder(path):
    if not path or not os.path.isdir(path):
        return [], "Invalid path"
    exts = (".mp4", ".mkv", ".avi", ".mov", ".m4v", ".wmv", ".ts")
    files = []
    for f in sorted(os.listdir(path)):
        if f.lower().endswith(exts):
            m = JAV_PATTERN.search(os.path.splitext(f)[0])
            jav_id = m.group(1).upper() if m else ""
            status = "pending" if jav_id else "no ID"
            files.append([f, jav_id, status])
    return files, f"Found {len(files)} files"


def add_batch(files_data):
    if files_data is None:
        return "No data"
    q = load_queue()
    added = 0
    for row in files_data:
        jav_id = row[1] if len(row) > 1 else ""
        if jav_id and jav_id not in q["pending"]:
            q["pending"].append(jav_id)
            added += 1
    save_queue(q)
    return f"Added {added} IDs to queue"


def process_one():
    q = load_queue()
    if not q["pending"]:
        pending_list = []
        return "Queue empty", len(q["pending"]), len(q["done"]), len(q["failed"]), pending_list
    sc = Jav321Scraper()
    jid = q["pending"].pop(0)
    try:
        movie = sc.scrape(jid)
        if movie.title:
            q["done"].append(jid)
            save_nfo({"title": movie.title, "orig": movie.original_title, "plot": movie.plot,
                      "dur": movie.runtime, "cid": movie.id, "gn": movie.genres,
                      "rd": movie.release_date, "st": movie.studio})
            res = f"OK: {jid}"
        else:
            q["failed"].append(jid)
            res = f"Not found: {jid}"
    except Exception as e:
        q["failed"].append(jid)
        res = f"Error: {jid} — {e}"
    save_queue(q)
    pending_list = [[i] for i in q["pending"]]
    return res, len(q["pending"]), len(q["done"]), len(q["failed"]), pending_list


def process_all():
    q = load_queue()
    if not q["pending"]:
        pending_list = []
        return "Queue empty", len(q["pending"]), len(q["done"]), len(q["failed"]), pending_list
    res = []
    sc = Jav321Scraper()
    while q["pending"]:
        jid = q["pending"].pop(0)
        try:
            m = sc.scrape(jid)
            if m.title:
                q["done"].append(jid)
                save_nfo({"title": m.title, "orig": m.original_title, "plot": m.plot,
                          "dur": m.runtime, "cid": m.id, "gn": m.genres,
                          "rd": m.release_date, "st": m.studio})
                res.append(f"OK: {jid}")
            else:
                q["failed"].append(jid)
                res.append(f"NF: {jid}")
        except Exception as e:
            q["failed"].append(jid)
            res.append(f"ERR: {jid}")
    save_queue(q)
    pending_list = [[i] for i in q["pending"]]
    return "\n".join(res), len(q["pending"]), len(q["done"]), len(q["failed"]), pending_list


def clear_done():
    q = load_queue()
    q["done"] = []
    save_queue(q)
    pending_list = [[i] for i in q["pending"]]
    return "Done list cleared", len(q["pending"]), len(q["done"]), len(q["failed"]), pending_list


def save_nfo(d):
    if not d:
        return
    cid = d.get("cid", "x")
    title = d.get("title", "")[:50]
    st = d.get("st", "Unknown")
    fold = os.path.join(OUTPUT_DIR, st, f"[{cid}] {title}")
    os.makedirs(fold, exist_ok=True)
    nfo = f'''<?xml version="1.0"?>
<movie><title>{cid} {d.get("title","")}</title>
<originaltitle>{d.get("orig","")}</originaltitle>
<plot>{d.get("plot","")}</plot>
<runtime>{d.get("dur",0)}</runtime>
<uniqueid type="num">{cid}</uniqueid>
<genre>{", ".join(d.get("gn",[]))}</genre>
<country>Japan</country>
<premiered>{d.get("rd","")}</premiered>
<studio>{d.get("st","")}</studio>
</movie>'''
    with open(os.path.join(fold, "movie.nfo"), "w") as f:
        f.write(nfo)


def scrape_one(jid, src):
    if not jid:
        return "", "", "", "", "", "", "", None, "", {}
    sc = Jav321Scraper()
    try:
        m = sc.scrape(jid)
        _d = {"title": m.title, "orig": m.original_title, "actors": [a.name for a in m.actors],
              "gn": m.genres, "st": m.studio, "rd": m.release_date, "dr": m.runtime,
              "cv": m.cover_url, "pl": m.plot, "cid": m.id}
        return (m.title, m.original_title, ", ".join([a.name for a in m.actors]),
                ", ".join(m.genres), m.studio, m.release_date, str(m.runtime),
                m.cover_url, m.plot, _d)
    except Exception as e:
        return "", "", "", "", "", "", "", None, f"Error: {e}", {}


demo = gr.Blocks(title="JAV Scraper")

with demo:
    with gr.Tab("Single Scrape"):
        gr.Markdown("### Single Scrape")
        jid = gr.Textbox(label="JAV ID")
        src = gr.Dropdown(["Auto", "Jav321", "R18"], label="Source", value="Jav321")
        scrape_btn = gr.Button("Scrape", variant="primary")
        add_btn = gr.Button("Add to Queue")

        title = gr.Textbox(label="Title")
        orig = gr.Textbox(label="Original")
        acts = gr.Textbox(label="Actors")
        genres = gr.Textbox(label="Genres")
        studio = gr.Textbox(label="Studio")
        date = gr.Textbox(label="Date")
        dur = gr.Textbox(label="Duration")
        cover = gr.Image(label="Cover")
        plot = gr.Textbox(label="Plot", lines=3)

        state = gr.State()
        status = gr.Textbox(label="Status")

        scrape_btn.click(scrape_one, inputs=[jid, src],
                         outputs=[title, orig, acts, genres, studio, date, dur, cover, plot, state])

        add_btn.click(add_to_queue, inputs=[jid], outputs=[status])

        gr.Button("Save NFO").click(lambda d: save_nfo(d) or "Saved", inputs=[state], outputs=[status])

    with gr.Tab("Batch Scan"):
        gr.Markdown("### Batch Scan — สแกน JAV ID จากชื่อไฟล์ในโฟลเดอร์")
        folder = gr.Textbox(label="Folder Path", placeholder="/path/to/folder")
        with gr.Row():
            scan_btn = gr.Button("Scan", variant="primary")
            addb_btn = gr.Button("Add to Queue")
        s_status = gr.Textbox(label="Status")
        files_df = gr.Dataframe(
            headers=["file", "id", "status"],
            column_count=3,
            interactive=False,
            label="Scan Results"
        )

        scan_btn.click(scan_folder, inputs=[folder], outputs=[files_df, s_status])
        addb_btn.click(add_batch, inputs=[files_df], outputs=[s_status])

    with gr.Tab("Queue"):
        gr.Markdown("### Queue Manager")
        with gr.Row():
            cnt_p = gr.Number(label="Pending", interactive=False)
            cnt_d = gr.Number(label="Done", interactive=False)
            cnt_f = gr.Number(label="Failed", interactive=False)

        q_status = gr.Textbox(label="Status", lines=3)
        q_list = gr.Dataframe(label="Pending IDs", headers=["ID"], column_count=1, interactive=False)

        with gr.Row():
            btn_one = gr.Button("Process One", variant="primary")
            btn_all = gr.Button("Process All", variant="primary")
            btn_clr = gr.Button("Clear Done")

        def load_q():
            q = load_queue()
            return len(q["pending"]), len(q["done"]), len(q["failed"]), [[i] for i in q["pending"]]

        demo.load(load_q, outputs=[cnt_p, cnt_d, cnt_f, q_list])
        btn_one.click(process_one, outputs=[q_status, cnt_p, cnt_d, cnt_f, q_list])
        btn_all.click(process_all, outputs=[q_status, cnt_p, cnt_d, cnt_f, q_list])
        btn_clr.click(clear_done, outputs=[q_status, cnt_p, cnt_d, cnt_f, q_list])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
