"""Desktop/mobile behavioral timing regression (Playwright + Chromium)."""

import base64
from io import BytesIO
import json
import os
from pathlib import Path
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from feed_metrics import feed_metrics_rows


def run():
    buffer = BytesIO()
    Image.new("RGB", (40, 40), "#8396ad").save(buffer, "PNG")
    image = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    posts = [{"id": f"P{i}", "image_url": image, "username": f"profilo.{i}", "comments": []} for i in range(1, 5)]
    data = {"session_id": "timing-test", "participant_id": "test", "phase": "feed", "posts": posts,
            "history": [], "phase1_ready": True, "missing_post_ids": []}
    css = (BASE / "styles.css").read_text().replace(":host {", "body {", 1)
    js = (BASE / "feed_tracking.js").read_text() + "\n" + (BASE / "feed.js").read_text().replace(
        "export default function (component)", "function initFeed(component)", 1)
    html = ('<style>html,body{margin:0}' + css + '</style><div id="instalab-root"></div><script>' + js +
            '\nwindow.events=[];window.hostData=' + json.dumps(data) + ';' +
            'window.mount=()=>{window.cleanup?.();window.cleanup=initFeed({parentElement:document,data:window.hostData,' +
            'setStateValue:(_name,events)=>{window.events=events;}});};window.mount();</script>')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"), args=["--no-sandbox"])
        for width, height in ((1280, 850), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(html)
            page.bring_to_front()
            page.wait_for_function('[...document.querySelectorAll(".post-photo")].every(i=>i.dataset.decoded==="true")')
            tracker = 'window.__instalabFeedTrackers.get("timing-test")'

            def views(post):
                return page.evaluate('(id)=>window.events.filter(e=>e.event_type==="feed_view" && e.post_id===id)', post)

            def exposure_total(post):
                durations = {}
                for e in views(post):
                    d = e["details"]
                    durations[d["exposure_id"]] = max(durations.get(d["exposure_id"], 0), d["duration_ms"])
                return sum(durations.values())

            def show(post, position="center"):
                page.locator(f'article[data-post="{post}"] .post-photo').evaluate('(e,position)=>e.scrollIntoView({block:position})', position)
                page.evaluate(tracker + '.update()')
                page.wait_for_timeout(70)

            show("P1")
            page.wait_for_timeout(220)
            page.evaluate('window.mount();window.mount()')
            page.wait_for_timeout(200)
            starts = [e for e in views("P1") if e["details"]["reason"] == "start"]
            assert len(starts) == 1, starts
            # With a compact feed, centering P2 can leave part of P1 visible.
            # Align P2 to the top to test an actually offscreen P1.
            show("P2", position="start")
            assert page.locator('article[data-post="P1"] .post-photo').evaluate('(e)=>feedVisibleRatio(e)') == 0
            offscreen_duration = exposure_total("P1")
            assert offscreen_duration >= 350, offscreen_duration
            page.wait_for_timeout(250)
            page.evaluate(tracker + '.update()')
            assert exposure_total("P1") == offscreen_duration
            # Exactly half the image is visible; the strict 75% clock must stop.
            page.locator('article[data-post="P2"] .post-photo').evaluate('(e)=>window.scrollTo(0,scrollY+e.getBoundingClientRect().top+e.height/2)')
            page.evaluate(tracker + '.update()')
            ratio = page.locator('article[data-post="P2"] .post-photo').evaluate('(e)=>feedVisibleRatio(e)')
            assert 0.45 <= ratio <= 0.55, ratio
            half_duration = exposure_total("P2")
            page.wait_for_timeout(200)
            page.evaluate(tracker + '.update()')
            assert exposure_total("P2") == half_duration
            show("P1")
            assert len([e for e in views("P1") if e["details"]["reason"] == "start"]) == 2
            page.wait_for_timeout(120)
            page.evaluate('document.hasFocus=()=>false;window.dispatchEvent(new Event("blur"))')
            blur_duration = exposure_total("P1")
            page.wait_for_timeout(200)
            page.evaluate(tracker + '.update()')
            assert exposure_total("P1") == blur_duration
            page.evaluate('document.hasFocus=()=>true;window.dispatchEvent(new Event("focus"))')
            page.wait_for_timeout(120)
            page.evaluate('window.testHidden=true;Object.defineProperty(document,"hidden",{get:()=>window.testHidden,configurable:true});document.dispatchEvent(new Event("visibilitychange"))')
            hidden_duration = exposure_total("P1")
            page.wait_for_timeout(200)
            page.evaluate(tracker + '.update()')
            assert exposure_total("P1") == hidden_duration
            page.evaluate('window.testHidden=false;document.dispatchEvent(new Event("visibilitychange"))')
            page.wait_for_timeout(120)
            # Exercise real UI actions, including opposite-reaction auto removal.
            like = page.locator('article[data-post="P1"] [data-action="like"]')
            for _ in range(3):
                like.click()
            page.locator('article[data-post="P1"] [data-action="dislike"]').click()
            page.locator('article[data-post="P1"] [data-action="save"]').click()
            page.locator('article[data-post="P1"] [data-action="open_comments"]').click()
            form = page.locator('form[data-comment-post="P1"]')
            form.locator('input').fill('Commento inviato')
            form.locator('button').click()
            page.evaluate(tracker + '.finalize();' + tracker + '.finalize()')
            events = page.evaluate('window.events')
            assert sum(e["event_type"] == "feed_tracking_finalized" for e in events) == 1
            assert not views("P4"), views("P4")
            start = {"event_id":"assignment", "event_type":"session_started", "participant_id":"test", "session_id":"timing-test",
                     "details":{"post_order":[p["id"] for p in posts], "stimuli":[{"id":p["id"],"stimulus_id":p["id"],"source_type":"real","gender":"F"} for p in posts]}}
            rows = feed_metrics_rows([start] + [{**e, "session_id":"timing-test", "participant_id":"test"} for e in events])
            first, unseen = rows[0], rows[-1]
            assert first["view_count"] >= 4, first
            assert first["first_view_duration_ms"] == offscreen_duration
            assert first["total_view_duration_ms"] >= hidden_duration
            assert (first["liked"], first["disliked"], first["like_count"], first["unlike_count"], first["dislike_count"]) == (0, 1, 2, 2, 1)
            assert (first["saved"], first["comment_open_count"], first["comment_count"], first["shared_count"], first["interaction_count"]) == (1, 1, 1, 0, 7), first
            assert unseen["view_count"] == 0 and unseen["metrics_missing"] == 0
            assert not errors, errors
            print(f'{width}x{height}: 75% timing, offscreen=0, revisits, blur/hidden pause, reruns, social counts and finalized export PASS', flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    run()
