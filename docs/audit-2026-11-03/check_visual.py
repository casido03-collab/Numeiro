"""Check the local proposal visualization in an isolated headless browser."""
from pathlib import Path
from playwright.sync_api import sync_playwright

folder = Path(r"C:\Users\Евгений\.codex\visualizations\2026\11\03\01a1a057-8c2b-7b43-a298-685ecab587f6")
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 850, "height": 1100}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((folder / "aisha-openai-preview.html").as_uri())
    frame = page.frame_locator("iframe")
    frame.locator("#aisha-count").wait_for()
    assert frame.locator("#aisha-new-cost").inner_text() == "$1,24"
    frame.locator("#aisha-count").fill("10000")
    frame.locator("#aisha-count").dispatch_event("input")
    assert frame.locator("#aisha-new-cost").inner_text() == "$12,35"
    frame.locator("#aisha-count").fill("1000")
    frame.locator("#aisha-count").dispatch_event("input")
    for width in (850, 390, 320):
        page.set_viewport_size({"width": width, "height": 1100})
        for tab, panel in (("models", "models"), ("services", "services"), ("dialog", "dialog")):
            frame.locator(f"#aisha-{tab}-tab").click()
            assert frame.locator(f"#aisha-{panel}").is_visible()
            overflow = frame.locator("#aisha-audit").evaluate("e => ({scroll:e.scrollWidth, width:e.clientWidth})")
            assert overflow["scroll"] <= overflow["width"] + 1, (width, tab, overflow)
        frame.locator("#aisha-services-tab").click()
        frame.locator("#aisha-product").select_option("vip")
        assert "30 вопросов" in frame.locator("#aisha-result-content").inner_text()
    page.set_viewport_size({"width": 850, "height": 1100})
    frame.locator("#aisha-models-tab").click()
    page.screenshot(path=str(folder / "aisha-openai-preview.png"), full_page=True)
    assert not errors, errors
    print("PASS: cost calculation, tabs, product details, widths 850/390/320; no JavaScript errors")
    browser.close()
