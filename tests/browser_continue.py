"""Optional browser regression checks: python tests/browser_continue.py.

Uses Playwright and an existing Chromium executable (CHROMIUM_PATH overrides it).
The fake host captures events without a backend rerun so local DOM replacement
cannot hide a disconnected impression observer.
"""

import base64
import json
import os
from io import BytesIO
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from PIL import Image

BASE = Path(__file__).resolve().parents[1]


def run():
    fixture = BytesIO()
    Image.new("RGB", (32, 32), "#8a9bad").save(fixture, "PNG")
    image = "data:image/png;base64," + base64.b64encode(fixture.getvalue()).decode()
    posts = [{"id":f"P{i:03}", "image_url": image, "username":f"profilo.{i}", "comments":[]} for i in range(1,4)]
    data = {"posts": posts, "phase": "feed", "history": [], "phase1_ready": False,
            "missing_post_ids": [p["id"] for p in posts]}
    css = (BASE / "styles.css").read_text().replace(":host {", "body {", 1)
    js = (BASE / "feed_tracking.js").read_text() + "\n" + (BASE / "feed.js").read_text().replace("export default function (component)", "function initFeed(component)", 1)
    html = ('<style>html,body{margin:0}' + css + '</style><div id="instalab-root"></div><script>' + js +
            '\nwindow.events=[];window.hostData=' + json.dumps(data) + ';' +
            'window.mount=()=>{window.cleanup?.();window.cleanup=initFeed({parentElement:document,data:window.hostData,' +
            'setStateValue:(_name,events)=>{window.events=events;}});};window.mount();</script>')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"), args=["--no-sandbox"])
        for width, height in [(1280, 300), (390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            for index, post in enumerate(posts):
                page.locator(f'.post[data-post="{post["id"]}"] .photo-wrap').evaluate('(e)=>e.scrollIntoView({block:"center"})')
                page.wait_for_function('(id)=>window.events.some(e=>e.event_type==="post_impression" && e.post_id===id)', arg=post["id"])
                if index == 0:
                    page.locator('[data-action="like"]').first.click()
                if index == 1:
                    form = page.locator('form[data-comment-post]').nth(1)
                    form.locator('input').fill('Commento di prova')
                    form.locator('button').click()
            impressions = page.evaluate('window.events.filter(e=>e.event_type==="post_impression").map(e=>e.post_id)')
            assert set(impressions) == {p["id"] for p in posts}, impressions
            expect(page.locator('.phase-next')).to_be_disabled()
            # Simulate a host that still needs one exposure, then acknowledge it.
            page.evaluate('window.hostData.missing_post_ids=["P002"];window.mount()')
            page.locator('.review-unseen').click()
            expect(page.locator('.post[data-post="P002"] .photo-wrap')).to_be_in_viewport()
            page.evaluate('window.hostData.phase1_ready=true;window.hostData.missing_post_ids=[];window.mount()')
            expect(page.locator('.phase-next')).to_be_enabled()
            page.locator('.phase-next').click()
            assert page.evaluate('window.events.some(e=>e.event_type==="begin_recognition")')
            expect(page.locator('.feed-transition-status')).to_be_visible()
            expect(page.locator('.phase-next')).to_be_disabled()
            page.evaluate('window.mount();window.mount()')
            expect(page.locator('.feed-transition-status')).to_be_visible()
            page.locator('.phase-next').evaluate('(button)=>button.dispatchEvent(new MouseEvent("click",{bubbles:true}))')
            assert page.evaluate('window.events.filter(e=>e.event_type==="begin_recognition").length===1')
            kinds = page.evaluate('window.events.map(e=>e.event_type)')
            assert kinds.index('feed_tracking_finalized') < kinds.index('begin_recognition')
            print(f'{width}x{height}: exposures, Continue, immediate loading status, reruns and single finalized transition PASS', flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    run()
