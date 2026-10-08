"""Browser checks for saved defaults, daily actions, and weight/waist progress."""
import datetime
from playwright.sync_api import sync_playwright
from test_ui import free_port, serve


def run():
    port = free_port()
    server = serve(port)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844}, service_workers="block")
            page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(status=200, content_type="text/css", body=""))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.clock.install(time=datetime.datetime(2026, 10, 14, 12, tzinfo=datetime.timezone.utc))
            page.goto(f"http://localhost:{port}/index.html")
            page.wait_for_selector("#foodAction")

            page.click("#editDefaults")
            page.select_option("#default-breakfast", "overnight-oats")
            page.select_option("#default-dinner", "turkey-chili")
            page.click("#saveDefaults")
            assert "Overnight Oats" in page.text_content("#focusToday")
            page.click("#defaultGroceries")
            assert "rolled oats" in page.text_content("#infoModalSheet")
            assert "turkey" in page.text_content("#infoModalSheet").lower()
            page.click("#modalCloseBtn")
            page.click("#todayMeals")
            assert "Overnight Oats" in page.text_content("#mealsContent")
            page.click("#tabToday")

            page.click('[data-energy="low"]')
            assert page.text_content("#todayWorkoutTitle") == "5-minute walk"
            page.click('[data-energy="medium"]')
            assert page.text_content("#todayWorkoutTitle") == "15-minute walk"
            page.click('[data-energy="high"]')
            assert page.text_content("#todayWorkoutTitle") == "Strength B"
            page.click('[data-energy="low"]')
            page.click("#foodAction")
            page.click("#movementAction")
            page.fill("#waistInput", "39")
            page.locator("#waistInput").press("Tab")
            page.reload()
            page.wait_for_selector("#foodAction")
            assert page.get_attribute("#foodAction", "aria-pressed") == "true"
            assert page.get_attribute("#movementAction", "aria-pressed") == "true"
            assert page.input_value("#waistInput") == "39"
            assert page.get_attribute('[data-energy="low"]', "aria-pressed") == "true"
            assert "Overnight Oats" in page.text_content("#focusToday")
            page.click("#movementAction")
            assert page.get_attribute("#movementAction", "aria-pressed") == "false"

            # Seed two calendar weeks, plus an ignored future entry and a corrupt log.
            page.evaluate("""() => {
                for (const [date, weight] of [['2026-10-05',201],['2026-10-06',200],['2026-10-07',199],['2026-10-12',199],['2026-10-13',198],['2026-10-14',197]]) {
                    const key='almanac:log:'+date;
                    const log=JSON.parse(localStorage.getItem(key)||'{}');
                    Object.assign(log,{weight,weightUnit:'lb'});
                    if(date==='2026-10-05')log.waist=40;
                    localStorage.setItem(key,JSON.stringify(log));
                }
                localStorage.setItem('almanac:log:2026-10-20',JSON.stringify({weight:100,waist:20}));
                localStorage.setItem('almanac:log:2026-09-20','broken');
            }""")
            page.reload()
            page.click("#viewProgress")
            content = page.text_content("#trendsContent")
            assert "198.0 lb" in content, content
            assert "-2.0 lb" in content, content
            assert "-1.0 in" in content, content
            assert "Meals as planned: 1 / 3 days" in content, content
            assert "Movement completed: 0 / 3 days" in content, content
            assert page.get_attribute('[role="progressbar"]', "aria-valuenow") == "10"
            page.fill("#dailyGoalInput", "10")
            page.locator("#dailyGoalInput").press("Tab")
            assert page.get_attribute('[role="progressbar"]', "aria-valuenow") == "20"
            page.click("#tabToday")
            page.click("#unitKg")
            assert abs(float(page.input_value("#weightInput")) - 89.4) < 0.1
            page.click("#tabTrends")
            assert "89.8 kg" in page.text_content("#trendsContent")
            assert page.get_attribute('[role="progressbar"]', "aria-valuenow") == "20"
            page.click("#tabToday")
            page.click("#prevDay")
            assert page.get_attribute("#foodAction", "aria-pressed") == "false"
            page.reload()
            assert "Wed, Oct 14" in page.text_content("#dateLabel")

            # Missing readings remain unknown, never zero or a fabricated average.
            page.evaluate("() => { for(const key of Object.keys(localStorage))if(key.startsWith('almanac:log:'))localStorage.removeItem(key); }")
            page.reload()
            page.click("#tabTrends")
            assert "No weight measurements yet" in page.text_content("#trendsContent")
            assert page.get_attribute('[role="progressbar"]', "aria-valuenow") == "0"
            assert errors == [], errors
            browser.close()
    finally:
        server.shutdown()
    print("Focus flow, persistence, weekly averages, waist, goal, and unit checks passed.")


if __name__ == "__main__":
    run()
