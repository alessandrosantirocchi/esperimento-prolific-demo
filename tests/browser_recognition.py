"""Browser checks for OLD/NEW followed by a mandatory 1–5 confidence rating."""

import base64
import json
import os
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright

BASE = Path(__file__).resolve().parents[1]


def run():
    fixture = BytesIO()
    Image.new("RGB", (64, 64), "#a9b7cb").save(fixture, "PNG")
    source = "data:image/png;base64," + base64.b64encode(fixture.getvalue()).decode()
    data = {"posts": [{"id": "R001", "image_url": source}], "phase": "recognition",
            "confidence_required": True, "session_id": "confidence-test", "history": [],
            "trial_number": 11, "trial_total": 60}
    css = (BASE / "styles.css").read_text().replace(":host {", "body {", 1)
    js = (BASE / "feed_tracking.js").read_text() + "\n" + (BASE / "feed.js").read_text().replace(
        "export default function (component)", "function initFeed(component)", 1)
    html = ('<style>html,body{margin:0}' + css + '</style><div id="instalab-root"></div><script>' + js +
            '\nwindow.events=[];window.hostData=' + json.dumps(data) + ';' +
            'window.mount=()=>{window.cleanup?.();window.cleanup=initFeed({parentElement:document,data:window.hostData,' +
            'setStateValue:(_name,events)=>{window.events=events;}});};window.mount();</script>')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"),
                                             headless=True, args=["--no-sandbox"])
        for width, height in [(1280, 900), (390, 667), (390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(html)
            old = page.locator('[data-choice="OLD"]')
            expect(old).to_be_enabled()
            text = page.locator('#instalab-root').inner_text()
            for removed in ["Memoria di riconoscimento", "Scegli OLD se", "Volto 11 di 60"]:
                assert removed not in text
            ratings = page.locator('[data-confidence-value]')
            assert ratings.count() == 5
            assert [button.inner_text() for button in ratings.all()] == ["1", "2", "3", "4", "5"]
            assert page.locator('[data-confidence-value][aria-pressed="true"]').count() == 0
            for button in ratings.all():
                expect(button).to_be_disabled()
                assert button.bounding_box()["height"] >= 44
            old.click()
            assert page.evaluate('window.events.filter(e=>e.event_type==="recognition_response").length') == 0
            expect(old).to_have_attribute('aria-pressed', 'true')
            page.wait_for_timeout(180)
            page.evaluate('window.mount();window.mount()')
            expect(old).to_have_attribute('aria-pressed', 'true')
            for button in ratings.all():
                expect(button).to_be_enabled()
            page.locator('[data-choice="NEW"]').click()
            choice_rt = page.evaluate('document.querySelector("#instalab-root").__instalab_state.choiceRt')
            page.wait_for_timeout(300)
            page.locator('[data-confidence-value="4"]').click()
            response = page.evaluate('window.events.filter(e=>e.event_type==="recognition_response")')
            assert len(response) == 1
            assert response[0]['details']['response'] == 'NEW'
            assert response[0]['details']['confidence'] == 4
            assert response[0]['details']['response_time_ms'] == choice_rt
            assert response[0]['details']['confidence_response_time_ms'] >= 250
            assert response[0]['details']['confidence_scale_version'] == 1
            for button in page.locator('.recognition-actions button,[data-confidence-value]').all():
                expect(button).to_be_disabled()
            page.evaluate('window.mount();window.mount()')
            page.locator('[data-confidence-value="4"]').evaluate(
                '(button)=>button.dispatchEvent(new MouseEvent("click",{bubbles:true}))')
            assert page.evaluate('window.events.filter(e=>e.event_type==="recognition_response").length') == 1

            # All five values are reachable, reset for the next trial, and work
            # with native button keyboard activation as well as pointer/touch.
            for number in range(1, 6):
                page.evaluate('''(number)=>{window.hostData.history=window.events.slice();
                  window.hostData.posts[0].id=`R00${number+1}`;window.mount();}''', number)
                expect(page.locator('.recognition-heading')).to_be_in_viewport()
                expect(old).to_be_enabled()
                assert page.locator('[data-confidence-value][aria-pressed="true"]').count() == 0
                old.focus()
                old.press('Enter')
                rating = page.locator(f'[data-confidence-value="{number}"]')
                expect(rating).to_be_enabled()
                rating.focus()
                rating.press('Enter')
                assert page.evaluate('window.events.at(-1).details.confidence') == number

            # A failed decode blocks both judgments. Retrying restores the image
            # and does not create a response or choose a default confidence.
            page.evaluate('window.hostData.history=window.events.slice();window.hostData.posts[0].id="R007";window.mount()')
            expect(old).to_be_enabled()
            page.locator('.post-photo').evaluate('''image=>{image.dataset.decoded="";
              image.__decodePromise=null;image.src="data:image/png;base64,broken";}''')
            expect(page.locator('[data-action="retry_image"]')).to_be_visible()
            expect(old).to_be_disabled()
            for button in ratings.all():
                expect(button).to_be_disabled()
            page.locator('[data-action="retry_image"]').click()
            expect(old).to_be_enabled()
            assert page.locator('[data-confidence-value][aria-pressed="true"]').count() == 0

            # Recognition sessions already started on the previous format keep
            # their original one-click response until they finish.
            page.evaluate('window.hostData.history=window.events.slice();window.hostData.posts[0].id="R008";window.hostData.confidence_required=false;window.mount()')
            expect(old).to_be_enabled()
            assert page.locator('.recognition-confidence').count() == 0
            old.click()
            assert 'confidence' not in page.evaluate('window.events.at(-1).details')
            assert not errors, errors
            print(f'{width}x{height}: clean recognition screen, all confidence values, separate clocks, reruns, deduplication, keyboard, decode retry and legacy format PASS', flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    run()
