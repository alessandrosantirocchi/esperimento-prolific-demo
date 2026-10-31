"""Optional regression: python tests/browser_images.py (Playwright + Chromium)."""

import json
import os
from pathlib import Path
import sys

from playwright.sync_api import expect, sync_playwright

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from image_assets import prepare_image


def run():
    study = json.loads((BASE / "posts.json").read_text())
    posts = []
    images = {}
    for index, original in enumerate(study["posts"]):
        post = {k: v for k, v in original.items() if k != "image_region"}
        post["image_key"] = f"asset-{index}"
        images[post["image_key"]] = prepare_image(BASE / original["image"], original.get("image_region")).url
        posts.append(post)
    data = {"posts": posts, "image_sources": images, "phase": "feed", "history": [],
            "phase1_ready": False, "missing_post_ids": [p["id"] for p in posts]}
    css = (BASE / "styles.css").read_text().replace(":host {", "body {", 1)
    js = (BASE / "feed.js").read_text().replace("export default function (component)", "function initFeed(component)", 1)
    html = ('<style>html,body{margin:0}' + css + '</style><div id="instalab-root"></div><script>' + js +
            '\nwindow.events=[];window.hostData=' + json.dumps(data) + ';' +
            'window.mount=()=>{window.cleanup?.();window.cleanup=initFeed({parentElement:document,data:window.hostData,' +
            'setStateValue:(_name,events)=>{window.events=events;}});};window.mount();</script>')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"), args=["--no-sandbox"])
        for width, height in [(1280, 800), (390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(html)
            page.wait_for_function('document.querySelectorAll(".post-photo").length===20 && [...document.querySelectorAll(".post-photo")].every(i=>i.dataset.decoded==="true" && i.naturalWidth>0)')
            page.evaluate('window.originalImages=[...document.querySelectorAll(".post-photo")]')
            for _ in range(2):
                for index in range(20):
                    page.locator('.post-photo').nth(index).evaluate('(image)=>image.scrollIntoView({block:"center"})')
                    page.wait_for_timeout(16)
            page.locator('[data-action="like"]').first.click()
            form = page.locator('form[data-comment-post]').first
            form.locator('input').fill('Verifica caricamento')
            form.locator('button').click()
            page.evaluate('window.mount();window.mount()')
            assert page.evaluate('window.originalImages.every((image,index)=>image===document.querySelectorAll(".post-photo")[index] && image.dataset.decoded==="true")')
            assert page.locator('.image-load-status:not([hidden])').count() == 0
            # A broken decode cannot accept a rating, and retry restores the same face.
            page.locator('.post-photo').first.evaluate('(image)=>{image.dataset.decoded="";image.__decodePromise=null;image.src="data:image/webp;base64,broken";}')
            expect(page.locator('[data-action="retry_image"]').first).to_be_visible()
            expect(page.locator('[data-action="like"]').first).to_be_disabled()
            page.locator('[data-action="retry_image"]').first.click()
            page.wait_for_function('document.querySelector(".post-photo").dataset.decoded==="true"')
            expect(page.locator('[data-action="like"]').first).to_be_enabled()
            assert page.locator('.post-photo').first.get_attribute('src') == images['asset-0']
            assert not errors, errors
            print(f'{width}x{height}: 20 decoded faces, fast scrolling, stable image nodes through reactions/reruns, retry PASS', flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    run()
