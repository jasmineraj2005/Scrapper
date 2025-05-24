import os
import sys
import time
import pickle
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from openai import OpenAI

COOKIE_FILE = "cookies.pkl"

def init_driver(load_cookies=True, proxy=None):
    """
    Initialize a headless Chrome browser with optional proxy and cache disabled.
    Load cookies if available.
    """
    opts = Options()
    opts.headless = True  # run browser in background

    # Disable cache to avoid stale content
    opts.add_argument("--disable-application-cache")
    opts.add_argument("--disk-cache-size=0")
    opts.add_argument("--disable-cache")
    opts.add_argument("--incognito")

    if proxy:
        opts.add_argument(f'--proxy-server={proxy}')
        print(f"🚀 Using proxy: {proxy}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    # Clear cookies and cache for fresh session (good cache avoidance)
    driver.delete_all_cookies()
    driver.execute_cdp_cmd('Network.clearBrowserCache', {})
    driver.execute_cdp_cmd('Network.clearBrowserCookies', {})

    if load_cookies and os.path.exists(COOKIE_FILE):
        driver.get("https://www.linkedin.com")
        cookies = pickle.load(open(COOKIE_FILE, "rb"))
        for c in cookies:
            driver.add_cookie(c)
        print("🔑 Loaded cookies from file.")

    return driver

def login():
    """
    Automate LinkedIn login using environment credentials.
    Save cookies for reuse.
    """
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        print("Error: Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables.")
        sys.exit(1)

    driver = init_driver(load_cookies=False)
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)

    driver.find_element(By.ID, "username").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    time.sleep(5)  # wait for login/authentication

    pickle.dump(driver.get_cookies(), open(COOKIE_FILE, "wb"))
    driver.quit()
    print("✅ Logged in and cookies saved.")

def fetch_html(url, proxy=None):
    """
    Fetch rendered HTML of LinkedIn profile page using optional proxy.
    """
    driver = init_driver(proxy=proxy)
    driver.get(url)
    time.sleep(5)
    html = driver.page_source
    driver.quit()
    return html

def parse_profile(html):
    """
    Extract profile data from LinkedIn HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    data = {
        "name":     soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else None,
        "headline": soup.select_one(".text-body-medium").get_text(strip=True) if soup.select_one(".text-body-medium") else None,
        "about":    soup.select_one("section.pv-about-section .pv-about__summary-text").get_text(strip=True) if soup.select_one("section.pv-about-section .pv-about__summary-text") else None,
        "experience": [],
        "skills":   []
    }

    for li in soup.select("#experience-section li"):
        role_el = li.select_one("h3")
        comp_el = li.select_one(".pv-entity__secondary-title")
        if role_el and comp_el:
            data["experience"].append({
                "role":    role_el.get_text(strip=True),
                "company": comp_el.get_text(strip=True)
            })

    for s in soup.select(".pv-skill-category-entity__name-text"):
        data["skills"].append(s.get_text(strip=True))

    return data

def format_bio(profile_data):
    """
    Generate LinkedIn-style bio using OpenAI.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = client.responses.create(
        model="gpt-4o",
        instructions=(
            "You’re a friendly user‐profile writer. Given this JSON of someone’s LinkedIn data, "
            "write one casual paragraph (2–3 sentences, ~50 words) that: "
            "1) names their current role and organization, "
            "2) highlights a standout project or experience, "
            "3) calls out their top technical skills, "
            "and 4) sounds natural and upbeat—just like this example:\n\n"
            "Ethan Lee is a Bachelor of Commerce student at the University of Melbourne blending his love of AI and voice tech to build real-time conversational agents, including an AI phone-screening system using Next.js, FastAPI, Twilio and 11Labs. He’s led hackathon teams like Urbanteria, fine-tuned image-generation models for property apps and helped SaaS founders with marketing, sharpening his skills in Python, React, Supabase and prompt engineering.\n\n"
            "Now write a matching paragraph for the JSON below:"
        ),
        input=json.dumps(profile_data),
    )

    return response.output_text

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python linkedin_scraper.py [--login] [profile_url] [optional_proxy_url]")
        sys.exit(0)

    if args[0] == "--login":
        login()
        sys.exit(0)

    url = args[0]
    proxy = args[1] if len(args) > 1 else None

    print(f"🔍 Fetching {url} with proxy: {proxy if proxy else 'None'}")

    html = fetch_html(url, proxy=proxy)
    print("🧩 Parsing profile data...")

    profile = parse_profile(html)
    print("✍️  Formatting bio with ChatGPT...")

    bio = format_bio(profile)
    with open("bio.txt", "w") as f:
        f.write(bio)
    print("✅ Done! Bio saved to bio.txt")

if __name__ == "__main__":
    main()
