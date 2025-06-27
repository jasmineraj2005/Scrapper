import os
import sys
import json
import argparse
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from openai import OpenAI

# --- CONFIGURATION ---
DEFAULT_PROMPT = (
    "You are an expert LinkedIn profile data extractor. Given the HTML of a LinkedIn profile section, "
    "rephrase and organize the extracted data into a consistent, structured, and professional format. "
    "Output should be in a human-readable narrative style with clear sections like Experience, Education, etc. "
    "Ensure the output follows a standard format for each section, e.g. bullet points, paragraphs, etc. "
    "Do not simply summarize, but rephrase the raw HTML data into a professional format."
)

# --- ENVIRONMENT SETUP ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
API_KEY = "opneai-api-key"
if not API_KEY:
    print("❌ Please set OPENAI_API_KEY in your .env file or environment.")
    sys.exit(1)
client = OpenAI(api_key=API_KEY)

COOKIE_FILE = "linkedin_cookies.json"
DEBUG = True  # Set False to run headless without logs

# --- MODULAR FUNCTIONS ---
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
        await asyncio.sleep(2)
        buttons = await page.query_selector_all("button[aria-label='See more'], button:has-text('Show more')")
        for btn in buttons:
            if await btn.is_visible():
                try:
                    await btn.click()
                    await asyncio.sleep(1)
                except Exception:
                    pass
    print("✅ Finished scrolling and expanding.")

async def extract_sections_html(page):
    sections = {}
    selectors = {
        'header': "main > section:first-of-type",
        'about': "section.artdeco-card:has(div#about)",
        'experience': "section.artdeco-card:has(div#experience)",
        'education': "section.artdeco-card:has(div#education)",
        'skills': "section.artdeco-card:has(div#skills)",
        'licenses_and_certifications': "section.artdeco-card:has(div#licenses_and_certifications)",
        'volunteering': "section.artdeco-card:has(div#volunteering_experience)",
    }
    for name, selector in selectors.items():
        try:
            await page.wait_for_selector(selector, timeout=10000)
            el = await page.query_selector(selector)
            if el:
                sections[name] = await el.inner_html()
                print(f"✅ Extracted section '{name}'.")
            else:
                print(f"⚠️ Section '{name}' not found with selector '{selector}'.")
        except Exception:
            print(f"❌ Could not extract section '{name}'.")
    return sections

async def generate_phrased_output_from_raw_data(raw_html):
    prompt = f"{DEFAULT_PROMPT}\n\n{raw_html}"

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert LinkedIn profile data extractor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ AI error during data phrasing: {e}")
        return None

async def chunk_html_for_openai(raw_html, chunk_size=15000):
    """Split the raw HTML into chunks that fit within OpenAI's token limit."""
    chunks = []
    while len(raw_html) > chunk_size:
        chunk = raw_html[:chunk_size]
        raw_html = raw_html[chunk_size:]
        chunks.append(chunk)
    if raw_html:
        chunks.append(raw_html)
    return chunks

# --- MAIN ENTRYPOINT ---
async def main():
    parser = argparse.ArgumentParser(description="LinkedIn Profile Scraper with OpenAI Rephrasing")
    parser.add_argument("profile_url", nargs="?", help="LinkedIn profile URL to scrape")
    parser.add_argument("--login", action="store_true", help="Login and save cookies")
    parser.add_argument("--output", action="store_true", help="Output phrased data")
    args = parser.parse_args()

    if args.login:
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")
        if not email or not password:
            print("❌ Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file.")
            sys.exit(1)
        await login_and_save_cookies(email, password)
        return

    if not args.profile_url:
        print("❌ Please provide a LinkedIn profile URL.")
        sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEBUG)
        context = await browser.new_context()
        await load_cookies_to_context(context)
        page = await context.new_page()
        print(f"➡️ Navigating to profile: {args.profile_url}")
        await page.goto(args.profile_url)
        print("⌛ Waiting for page to load...")
        await asyncio.sleep(15)
        await page.wait_for_selector("h1", timeout=15000)
        await scroll_and_expand(page)

        # Extract the raw HTML of profile sections
        profile_html = await extract_sections_html(page)
        raw_html = "\n\n".join([f"{section.capitalize()} Section: \n{html}" for section, html in profile_html.items()])

        # Split the raw HTML into chunks for OpenAI
        chunks = await chunk_html_for_openai(raw_html)

        # Rephrase each chunk with OpenAI and print the output
        for chunk in chunks:
            phrased_output = await generate_phrased_output_from_raw_data(chunk)
            if phrased_output:
                print("✅ Phrased Data Output:")
                print(phrased_output)
            else:
                print("❌ Failed to generate phrased output.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
