import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from openai import OpenAI

load_dotenv()

COOKIE_FILE = "linkedin_cookies.json"
DEBUG = True  # Set False to run headless without logs

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def login_and_save_cookies(email, password):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEBUG)
        context = await browser.new_context()
        page = await context.new_page()

        print("➡️ Navigating to LinkedIn login page...")
        await page.goto("https://www.linkedin.com/login")
        await page.fill("input#username", email)
        await page.fill("input#password", password)
        await page.click("button[type=submit]")
        print("⌛ Waiting for login success...")
        await page.wait_for_selector("#global-nav-search", timeout=30000)

        cookies = await context.cookies()
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
        print(f"✅ Cookies saved to {COOKIE_FILE}")

        await browser.close()

async def load_cookies_to_context(context):
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print(f"🔑 Loaded cookies from {COOKIE_FILE}")
    else:
        print(f"❌ Cookies file not found. Please run with --login first.")
        sys.exit(1)

async def scroll_and_expand(page):
    print("⏳ Scrolling page and expanding 'See more' buttons...")
    for _ in range(5):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(2)  # Wait a little longer for content to load
        buttons = await page.query_selector_all("button[aria-label='See more'], button:has-text('Show more')")
        for btn in buttons:
            if await btn.is_visible():
                try:
                    await btn.click()
                    await asyncio.sleep(1)  # Pause to wait for content to load
                except Exception:
                    pass
    print("✅ Finished scrolling and expanding.")

async def extract_sections_html(page):
    await page.wait_for_selector("section.pv-about-section", timeout=30000)
    sections = {}

    # Extract each section based on selectors
    selectors = {
        'about': "section.pv-about-section",
        'experience': "section#experience-section",
        'education': "section#education-section",
        'skills': "section#skills-section",
        'header': "div.pv-top-card-section__information"
    }

    for name, selector in selectors.items():
        el = await page.query_selector(selector)
        if el:
            sections[name] = await el.inner_html()
            print(f"✅ Extracted section '{name}'.")
        else:
            print(f"⚠️ Section '{name}' not found.")

    return sections

async def ask_openai_to_parse(section_name, html_snippet):
    instructions_map = {
        'header': "Extract Full Name, Professional Headline, Current Company, Current Role, Location, Profile URL.",
        'about': "Extract the About Summary as plain text.",
        'experience': "Extract a list of job experiences including job title, company, dates, description.",
        'education': "Extract a list of education entries with degree, school, dates.",
        'skills': "Extract a list of skills as strings.",
    }
    instructions = instructions_map.get(section_name, f"Extract key information from '{section_name}'.")

    prompt = f"""
You are an expert LinkedIn profile data extractor.
Given this HTML snippet representing the '{section_name}' section, perform the following extraction:
{instructions}

Return your output as JSON.

HTML snippet:
```html
{html_snippet[:15000]}
"""  # Limiting snippet length for API compatibility

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Extract structured LinkedIn data from HTML."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=1500
    )

    return response.choices[0].message.content

async def scrape_and_parse_profile(page):
    sections_html = await extract_sections_html(page)
    profile_data = {}
    for section, html in sections_html.items():
        try:
            parsed_str = await ask_openai_to_parse(section, html)
            parsed = json.loads(parsed_str)
            profile_data.update(parsed)
        except Exception as e:
            print(f"❌ Failed parsing '{section}': {e}")
    return profile_data

async def main():
    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print(" python main.py --login")
        print(" python main.py <linkedin_profile_url>")
        sys.exit(0)

    if args[0] == "--login":
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")
        if not email or not password:
            print("❌ Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file.")
            sys.exit(1)
        await login_and_save_cookies(email, password)
        return

    profile_url = args[0]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEBUG)
        context = await browser.new_context()
        await load_cookies_to_context(context)
        page = await context.new_page()

        print(f"➡️ Navigating to profile: {profile_url}")
        await page.goto(profile_url)

        # Added a 15-second wait to ensure the page has fully loaded
        print("⌛ Waiting for 15 seconds for the page to load...")
        await asyncio.sleep(15)

        await page.wait_for_selector("h1", timeout=15000)

        await scroll_and_expand(page)

        print("🔍 Parsing profile sections with OpenAI...")
        profile_data = await scrape_and_parse_profile(page)

        with open("profile_extracted.json", "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2)

        print("✅ Data saved to profile_extracted.json")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
