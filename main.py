import os
import sys
import time
import pickle
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

COOKIE_FILE = "cookies.pkl"

def init_driver(load_cookies=True, proxy=None, headless=True, incognito=True):
    opts = Options()
    if headless:
        opts.headless = True
    if incognito:
        opts.add_argument("--incognito")

    # Disable cache
    opts.add_argument("--disable-application-cache")
    opts.add_argument("--disk-cache-size=0")
    opts.add_argument("--disable-cache")

    if proxy:
        opts.add_argument(f'--proxy-server={proxy}')
        print(f"🚀 Using proxy: {proxy}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    # Clear cookies and cache
    driver.delete_all_cookies()
    driver.execute_cdp_cmd('Network.clearBrowserCache', {})
    driver.execute_cdp_cmd('Network.clearBrowserCookies', {})

    if load_cookies and os.path.exists(COOKIE_FILE):
        driver.get("https://www.linkedin.com")
        cookies = pickle.load(open(COOKIE_FILE, "rb"))
        for c in cookies:
            try:
                driver.add_cookie(c)
            except Exception as e:
                print(f"Warning: could not add cookie {c}: {e}")
        print("🔑 Loaded cookies from file.")

    return driver

def login():
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        print("Error: Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables.")
        sys.exit(1)

    driver = init_driver(load_cookies=False, headless=False, incognito=False)
    driver.get("https://www.linkedin.com/login")

    wait = WebDriverWait(driver, 20)

    wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(email)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type=submit]"))).click()

    try:
        wait.until(EC.presence_of_element_located((By.ID, "global-nav-search")))
        print("✅ Login successful!")
        pickle.dump(driver.get_cookies(), open(COOKIE_FILE, "wb"))
        print(f"🔑 Cookies saved to {COOKIE_FILE}")
    except TimeoutException:
        print("❌ Login failed or took too long; you may need to solve CAPTCHA or 2FA manually.")
        print("Please check the browser window that opened and complete login if required.")
        input("Press Enter here once you have manually logged in...")
        pickle.dump(driver.get_cookies(), open(COOKIE_FILE, "wb"))
        print(f"🔑 Cookies saved to {COOKIE_FILE} after manual login.")

    driver.quit()

def fetch_html(url, proxy=None):
    driver = init_driver(proxy=proxy)
    driver.get(url)
    time.sleep(5)  # Adjust if needed
    html = driver.page_source
    driver.quit()
    return html

def parse_profile(html):
    soup = BeautifulSoup(html, "html.parser")
    data = {
        "name": soup.select_one("h1") and soup.select_one("h1").get_text(strip=True),
        "headline": soup.select_one(".text-body-medium") and soup.select_one(".text-body-medium").get_text(strip=True),
        "about": soup.select_one("section.pv-about-section .pv-about__summary-text") and soup.select_one("section.pv-about-section .pv-about__summary-text").get_text(strip=True),
        "location": soup.select_one(".text-body-small.inline.t-black--light.break-words") and soup.select_one(".text-body-small.inline.t-black--light.break-words").get_text(strip=True),
        "experience": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "projects": [],
        "recommendations_received": [],
        "volunteer_experience": [],
        "accomplishments": [],
    }

    # Experience section
    for li in soup.select("#experience-section li"):
        role_el = li.select_one("h3")
        comp_el = li.select_one(".pv-entity__secondary-title")
        date_range_el = li.select_one(".pv-entity__date-range span:nth-of-type(2)")
        location_el = li.select_one(".pv-entity__location span:nth-of-type(2)")
        desc_el = li.select_one(".pv-entity__description")
        if role_el and comp_el:
            data["experience"].append({
                "role": role_el.get_text(strip=True),
                "company": comp_el.get_text(strip=True),
                "date_range": date_range_el.get_text(strip=True) if date_range_el else None,
                "location": location_el.get_text(strip=True) if location_el else None,
                "description": desc_el.get_text(strip=True) if desc_el else None
            })

    # Education section
    for edu in soup.select("#education-section li"):
        school_el = edu.select_one("h3")
        degree_el = edu.select_one(".pv-entity__degree-name .pv-entity__comma-item")
        field_el = edu.select_one(".pv-entity__fos .pv-entity__comma-item")
        date_range_el = edu.select_one(".pv-entity__dates time")
        if school_el:
            data["education"].append({
                "school": school_el.get_text(strip=True),
                "degree": degree_el.get_text(strip=True) if degree_el else None,
                "field_of_study": field_el.get_text(strip=True) if field_el else None,
                "date_range": date_range_el.get_text(strip=True) if date_range_el else None
            })

    # Skills section
    for skill in soup.select(".pv-skill-category-entity__name-text"):
        data["skills"].append(skill.get_text(strip=True))

    # Certifications section
    for cert in soup.select("#certifications-section li"):
        name_el = cert.select_one("h3")
        org_el = cert.select_one(".pv-entity__issuer")
        date_el = cert.select_one(".pv-entity__date")
        if name_el:
            data["certifications"].append({
                "name": name_el.get_text(strip=True),
                "issuer": org_el.get_text(strip=True) if org_el else None,
                "date": date_el.get_text(strip=True) if date_el else None
            })

    # Projects section
    for proj in soup.select("#projects-section li"):
        title_el = proj.select_one("h3")
        desc_el = proj.select_one(".pv-entity__description")
        date_el = proj.select_one(".pv-entity__date")
        if title_el:
            data["projects"].append({
                "title": title_el.get_text(strip=True),
                "description": desc_el.get_text(strip=True) if desc_el else None,
                "date": date_el.get_text(strip=True) if date_el else None
            })

    # Recommendations received
    for rec in soup.select("#recommendations-section .pv-recommendation-entity"):
        recommender_el = rec.select_one("h3")
        text_el = rec.select_one(".pv-recommendation-entity__text")
        if recommender_el and text_el:
            data["recommendations_received"].append({
                "recommender": recommender_el.get_text(strip=True),
                "text": text_el.get_text(strip=True)
            })

    # Volunteer Experience
    for vol in soup.select("#volunteering-section li"):
        role_el = vol.select_one("h3")
        org_el = vol.select_one(".pv-entity__secondary-title")
        date_el = vol.select_one(".pv-entity__date-range span:nth-of-type(2)")
        if role_el and org_el:
            data["volunteer_experience"].append({
                "role": role_el.get_text(strip=True),
                "organization": org_el.get_text(strip=True),
                "date_range": date_el.get_text(strip=True) if date_el else None
            })

    # Accomplishments (Awards, Publications, Languages etc.)
    # This is usually multiple sections; we'll grab Awards as example
    for award in soup.select("#honors-awards-section li"):
        title_el = award.select_one("h3")
        issuer_el = award.select_one(".pv-entity__issuer")
        date_el = award.select_one(".pv-entity__date")
        if title_el:
            data["accomplishments"].append({
                "title": title_el.get_text(strip=True),
                "issuer": issuer_el.get_text(strip=True) if issuer_el else None,
                "date": date_el.get_text(strip=True) if date_el else None
            })

    return data

def format_bio(profile_data):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = (
        "You are an expert profile summarizer. Given the following detailed LinkedIn profile JSON data, "
        "write a structured and readable profile summary covering their career, education, skills, certifications, projects, and achievements.\n\n"
        "Profile JSON:\n"
        f"{json.dumps(profile_data, indent=2)}\n\n"
        "Write the summary in plain text, suitable for a professional report."
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You summarize LinkedIn profiles into professional reports."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800,
    )
    return response.choices[0].message.content

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python main.py [--login] [profile_url] [optional_proxy_url]")
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
    with open("bio.txt", "w", encoding="utf-8") as f:
        f.write(bio)
    print("✅ Done! Bio saved to bio.txt")

if __name__ == "__main__":
    main()
