import os
import sys
import time
import random
import pickle
import json
import openai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)
from bs4 import BeautifulSoup
import logging
from logging import StreamHandler
from dotenv import load_dotenv

# Load environment variables from .env file (requires python-dotenv)
load_dotenv()

# Configuration
COOKIE_FILE = "cookies.pkl"
LOG_FILE = "scraper.log"
SCROLL_PAUSE_TIME = 1.5
MAX_SCROLLS = 20
PAGE_LOAD_TIMEOUT = 60
ELEMENT_TIMEOUT = 10

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        StreamHandler(sys.stdout)
    ]
)

# Helper Functions
def random_delay(a=1.0, b=3.0):
    delay = random.uniform(a, b)
    time.sleep(delay)
    logging.debug(f"Waited for {delay:.2f} seconds.")

def init_driver(load_cookies=True):
    opts = Options()
    opts.headless = True

    # Minimum common options for headless stability (can remove if not needed locally)
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")

    service = None
    try:
        logging.info("Getting ChromeDriver using webdriver_manager...")
        service = Service(ChromeDriverManager().install())
        logging.info("ChromeDriver obtained.")
    except Exception as e:
        logging.error(f"Error getting ChromeDriver: {e}", exc_info=True)
        return None

    driver = None
    try:
        logging.info("Starting Chrome WebDriver...")
        driver = webdriver.Chrome(service=service, options=opts)

        if load_cookies and os.path.exists(COOKIE_FILE):
            logging.info(f"Attempting to load cookies from {COOKIE_FILE}...")
            try:
                driver.get("https://www.linkedin.com")
                random_delay(1, 2)
            except Exception as get_e:
                logging.warning(f"Error navigating to LinkedIn base URL before loading cookies: {get_e}")

            try:
                with open(COOKIE_FILE, "rb") as f:
                    cookies = pickle.load(f)
                    for c in cookies:
                         domain = c.get('domain', '')
                         if domain.endswith('.linkedin.com') or domain == 'linkedin.com':
                             try:
                                cookie_dict = {k: v for k, v in c.items() if k != 'sameSite'}
                                if cookie_dict.get('domain', '').startswith('.'):
                                     cookie_dict['domain'] = cookie_dict['domain'][1:]
                                if '.linkedin.com' in driver.current_url or 'linkedin.com' in driver.current_url:
                                     driver.add_cookie(cookie_dict)
                             except Exception as add_cookie_e:
                                logging.debug(f"Could not add cookie {c.get('name')}: {add_cookie_e}")
                logging.debug("Attempted to load cookies.")
                random_delay(1, 2)
                logging.info("Navigating to feed to test cookie login...")
                try:
                    driver.get("https://www.linkedin.com/feed")
                    random_delay(3, 5)
                    if "feed" in driver.current_url or "mynetwork" in driver.current_url:
                        logging.info("Cookies appear to have loaded successfully.")
                    elif "login" in driver.current_url.lower():
                        logging.warning("Cookies loaded, but redirected back to login page.")
                    else:
                         logging.warning(f"Cookies loaded, but redirected to unexpected URL: {driver.current_url}")
                except Exception as test_get_e:
                    logging.warning(f"Error navigating to LinkedIn feed after loading cookies: {test_get_e}")

            except FileNotFoundError:
                 logging.warning(f"Cookie file not found at {COOKIE_FILE}.")
            except Exception as e:
                logging.warning(f"Failed during cookie loading or testing: {e}", exc_info=True)

        logging.info("✅ WebDriver initialized.")
        return driver

    except Exception as e:
        logging.error(f"❌ Error initializing WebDriver: {e}", exc_info=True)
        if driver: driver.quit()
        return None

def safe_find_element(driver, by, value, timeout=ELEMENT_TIMEOUT):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, value))
        )
        logging.debug(f"Found element by {by}: {value}")
        return element
    except (TimeoutException, NoSuchElementException):
        logging.debug(f"Element not found or visible within {timeout}s located by {by}: {value}")
        return None
    except Exception as e:
        logging.error(f"Error finding element located by {by}: {value} - {e}", exc_info=True)
        return None

def check_for_block_page(driver):
    try:
        source = driver.page_source.lower()
        url = driver.current_url.lower()

        block_keywords = ["access to this page has been denied", "something went wrong", "too many requests", "page not found", "unavailable", "verify you are human", "captcha"]

        if any(keyword in source for keyword in block_keywords) or \
           "linkedin.com/in/unavailable/" in url or \
           "linkedin.com/error/" in url or \
           "linkedin.com/checkpoint/" in url:
             logging.warning(f"Potential block or challenge detected. URL: {url}")
             return True

    except WebDriverException as e:
         logging.debug(f"Error during block check: {e}")
         pass
    return False

# Core Scraper Functions
def login():
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        logging.error("Error: Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables.")
        sys.exit(1)

    driver = None
    try:
        logging.info("--- Attempting Login ---")
        driver = init_driver(load_cookies=False)
        if not driver:
            logging.error("Driver initialization failed during login.")
            return False

        logging.info("Navigating to LinkedIn login page.")
        login_url = "https://www.linkedin.com/login"
        try:
            driver.get(login_url)
            time.sleep(3)
        except Exception as get_e:
            logging.error(f"Error navigating to login page: {get_e}", exc_info=True)
            return False

        if check_for_block_page(driver):
             logging.error("Login page appears blocked or challenged. Automated login aborted.")
             return False

        logging.info("Finding login form elements...")
        user_f = safe_find_element(driver, By.ID, "username", timeout=ELEMENT_TIMEOUT)
        pass_f = safe_find_element(driver, By.ID, "password", timeout=ELEMENT_TIMEOUT)
        submit_b = safe_find_element(driver, By.CSS_SELECTOR, "button[type=submit]", timeout=ELEMENT_TIMEOUT) or \
                   safe_find_element(driver, By.XPATH, "//button[contains(., 'Sign in')]", timeout=ELEMENT_TIMEOUT)

        if not all([user_f, pass_f, submit_b]):
            logging.error("Login form elements not found. Page structure changed?")
            return False

        logging.info("Entering credentials...")
        try:
             user_f.send_keys(email)
             random_delay(0.5, 1.0)
             pass_f.send_keys(password)
             random_delay(0.5, 1.0)
        except Exception as type_e:
            logging.error(f"Error entering credentials: {type_e}", exc_info=True)
            return False

        logging.info("Clicking sign in button...")
        try:
            submit_b.click()
            random_delay(6, 10)
        except Exception as click_e:
            logging.error(f"Error clicking submit button: {click_e}", exc_info=True)
            return False

        current_url = driver.current_url
        logging.info(f"URL after login attempt: {current_url}")

        if check_for_block_page(driver):
             logging.error("Block or challenge page displayed after login submission.")
             return False

        success_indicator = safe_find_element(driver, By.ID, "global-nav-search", timeout=20)

        if success_indicator and ("feed" in current_url or "mynetwork" in current_url or (("login" not in current_url.lower()) and ("linkedin.com/in/" not in current_url.lower()) and ("sales.linkedin.com" not in current_url.lower()))):
             logging.info("✅ Login appears successful.")
             try:
                with open(COOKIE_FILE, "wb") as f:
                    pickle.dump(driver.get_cookies(), f)
                logging.info(f"Cookies saved to {COOKIE_FILE}.")
             except Exception as e:
                 logging.warning(f"Failed to save cookies: {e}")
             return True
        else:
             logging.warning(f"❌ Login failed. URL: {current_url}. Success indicator not found or URL is unexpected.")
             return False

    except Exception as e:
        logging.error(f"An unexpected error occurred during login: {e}", exc_info=True)
        return False
    finally:
        if driver:
            logging.info("Quitting WebDriver after login attempt.")
            driver.quit()
            logging.info("WebDriver quit.")


def fetch_html(url):
    driver = None
    try:
        logging.info("--- Attempting Fetch HTML ---")
        driver = init_driver(load_cookies=True)
        if not driver:
            logging.error("Failed to init driver for fetch.")
            return None

        logging.info(f"Navigating to profile URL: {url}")
        try:
            driver.get(url)
            random_delay(6, 10)
        except Exception as get_e:
             logging.error(f"Error navigating to profile URL {url}: {get_e}", exc_info=True)
             return None

        if check_for_block_page(driver):
             logging.error(f"Blocked or challenged on {url}.")
             return None

        # Dynamic Scrolling
        logging.info("Starting dynamic scrolling...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        scroll_attempts_without_growth = 0

        while scroll_count < MAX_SCROLLS:
            scroll_count += 1
            logging.debug(f"Scrolling attempt {scroll_count}/{MAX_SCROLLS}")
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            random_delay(SCROLL_PAUSE_TIME - 0.5, SCROLL_PAUSE_TIME + 0.5)

            new_height = driver.execute_script("return document.body.scrollHeight")
            logging.debug(f"Scroll {scroll_count}: Old Height: {last_height}, New Height: {new_height}")

            if new_height == last_height:
                scroll_attempts_without_growth += 1
                if scroll_attempts_without_growth >= 3:
                     logging.info("Page height stopped growing.")
                     break
            else:
                 scroll_attempts_without_growth = 0

            if check_for_block_page(driver):
                logging.warning("Block or challenge detected during scrolling. Stopping scroll.")
                return None

            last_height = new_height

        logging.info(f"Finished dynamic scrolling after {scroll_count} attempts.")
        random_delay(2, 3)

        logging.info("Grabbing page source...")
        html = driver.page_source
        logging.info("✅ HTML fetched.")
        return html

    except Exception as e:
        logging.error(f"An unexpected error occurred during fetching HTML for {url}: {e}", exc_info=True)
        return None

    finally:
        if driver:
            logging.info("Quitting WebDriver after fetch attempt.")
            driver.quit()
            logging.info("WebDriver quit.")


def parse_profile(html):
    if not html:
        logging.warning("No HTML provided to parse.")
        return None

    soup = BeautifulSoup(html, "html.parser")
    data = {
        "name": None, "headline": None, "about": None,
        "experience": [], "education": [], "skills": []
    }

    # Name
    name_el = soup.select_one("h1.text-heading-xlarge, h1.pv-top-card__list li, .text-color-text.page-common h1")
    if name_el: data["name"] = name_el.get_text(strip=True)
    else: logging.debug("Name not found.")

    # Headline
    headline_el = soup.select_one(".text-body-medium, .pv-text-details__current-company-occupation, .text-color-text.page-common .text-body-small")
    if headline_el: data["headline"] = headline_el.get_text(strip=True)
    else: logging.debug("Headline not found.")

    # About
    about_section = soup.find("section", {"id": "about"}) or soup.find("div", {"id": "about"}) or soup.select_one(".artdeco-card.pv-about-module")
    if about_section:
        about_text_el = about_section.select_one("span.lt-line-clamp__line, div.pv-about__summary-text, .pv-shared-text-area")
        if about_text_el: data["about"] = about_text_el.get_text(strip=True)
        else: logging.debug("About text not found.")
    else: logging.debug("About section not found.")

    # Experience
    experience_section = soup.find("section", {"id": "experience-section"}) or soup.find("div", {"id": "experience"})
    if experience_section:
        logging.info("Parsing Experience...")
        experience_items = experience_section.select(".pv-profile-section__card-item, .artdeco-list__item, .pv-position-entity, .pvs-list__paged-list-item")
        for item in experience_items:
             role_el = item.select_one("h3, .pv-entity__summary-info h3, .t-bold span[aria-hidden='true'], .t-bold .visually-hidden + span")
             comp_el = item.select_one(".pv-entity__secondary-title, .t-black--light span[aria-hidden='true'], .t-normal.t-black--light span[aria-hidden='true']")
             role = role_el.get_text(strip=True) if role_el else "N/A"
             company = comp_el.get_text(strip=True) if comp_el else "N/A"
             if role != "N/A" or company != "N/A":
                 data["experience"].append({"role": role, "company": company})
        logging.info(f"Parsed {len(data['experience'])} experience entries.")
    else: logging.debug("Experience section not found.")

    # Education
    education_section = soup.find("section", {"id": "education-section"}) or soup.find("div", {"id": "education"})
    if education_section:
        logging.info("Parsing Education...")
        education_items = education_section.select(".pv-profile-section__card-item, .artdeco-list__item, .pv-education-entity, .pvs-list__paged-list-item")
        for item in education_items:
             degree_el = item.select_one(".pv-entity__degree-name, .t-bold span[aria-hidden='true']")
             field_el = item.select_one(".pv-entity__fos, .t-normal span[aria-hidden='true']")
             school_el = item.select_one("h3.pv-entity__school-name, .t-institute")
             degree = degree_el.get_text(strip=True) if degree_el else "N/A"
             field = field_el.get_text(strip=True) if field_el else "N/A"
             school = school_el.get_text(strip=True) if school_el else "N/A"
             if degree != "N/A" or field != "N/A" or school != "N/A":
                 data["education"].append({"degree": degree, "field": field, "school": school})
        logging.info(f"Parsed {len(data['education'])} education entries.")
    else: logging.debug("Education section not found.")

    # Skills
    skills_section = soup.find("div", {"id": "skills"}) or soup.find("section", {"id": "skills-section"})
    if skills_section:
        logging.info("Parsing Skills...")
        skill_elements = skills_section.select(".pv-skill-category-entity__name-text, .t-14.t-black.t-normal.lt-line-clamp__line, .pvs-list__outer-container .t-14.t-black.t-normal")
        if skill_elements:
            data["skills"] = [s.get_text(strip=True) for s in skill_elements if s.get_text(strip=True)]
            logging.info(f"Parsed {len(data['skills'])} skills.")
        else: logging.debug("No skills found.")
    else: logging.debug("Skills section not found.")

    return data


def format_bio(profile_data):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
         logging.error("OPENAI_API_KEY env var not set.")
         return "Error: OpenAI API key missing."

    try:
        client = openai.OpenAI(api_key=openai_api_key)
    except Exception as e:
        logging.error(f"Error init OpenAI client: {e}", exc_info=True)
        return f"Error: Failed to init OpenAI client - {e}"

    if not profile_data or (not profile_data.get('name') and not profile_data.get('headline')):
         logging.warning("Insufficient profile data for bio.")
         return "Error: Insufficient profile data to generate bio."

    clean_data = {k: v for k, v in profile_data.items() if v is not None and (not isinstance(v, list) or v)}

    prompt_text = (
        "You’re a friendly user‐profile writer. Given this JSON of someone’s LinkedIn data, "
        "write one casual paragraph (2–3 sentences, ~60 words) that: "
        "1) names the person and mentions their current role and organization (if available), "
        "2) highlights a standout aspect from their About or Experience (if available), "
        "3) calls out some of their top technical skills (if available), "
        "and 4) sounds natural and upbeat—like the example:\n\n"
        "Ethan Lee is a Bachelor of Commerce student at the University of Melbourne blending his love of AI and voice tech to build real-time conversational agents, including an AI phone-screening system using Next.js, FastAPI, Twilio and 11Labs. He’s led hackathon teams like Urbanteria, fine-tuned image-generation models for property apps and helped SaaS founders with marketing, sharpening his skills in Python, React, Supabase and prompt engineering.\n\n"
        "Write a matching paragraph for the JSON below. Focus on prominent details, handle missing sections:\n"
        f"{json.dumps(clean_data, indent=2, ensure_ascii=False)}"
    )

    logging.info("✍️ Sending data to OpenAI for bio...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful and creative profile writer. Generate a concise LinkedIn-style bio based on JSON."},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=250,
            temperature=0.7,
        )
        bio_text = response.choices[0].message.content.strip()
        logging.info("✅ Bio formatting successful.")
        return bio_text

    except Exception as e:
        logging.error(f"❌ OpenAI API error: {e}", exc_info=True)
        return f"Error: OpenAI API Error - {e}"


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python scrape.py [--login] [profile_url]")
        logging.info("No args provided. Showing usage.")
        sys.exit(0)

    if args[0] == "--login":
        logging.info("--- Running login sequence ---")
        print("Attempting login...")
        if login():
            print(f"✅ Login successful and cookies saved to {COOKIE_FILE}. You can now scrape profiles.")
        else:
            print("❌ Login failed. Check scraper.log for details.")
        sys.exit(0)

    url = args[0]
    if not url.startswith("https://www.linkedin.com/in/"):
        print("Error: Invalid LinkedIn profile URL format.")
        logging.error(f"Invalid URL format provided: {url}")
        sys.exit(1)

    if not os.path.exists(COOKIE_FILE):
        print(f"❌ Error: No cookie file ({COOKIE_FILE}) found. Please run with --login first.")
        logging.error(f"Cookie file not found: {COOKIE_FILE}. Cannot proceed with scraping.")
        sys.exit(1)

    logging.info(f"--- Starting scrape process for {url} ---")
    print(f"🔍 Fetching profile data from {url}")

    html = fetch_html(url)

    if not html:
        logging.error(f"❌ Failed to fetch HTML for {url}.")
        print(f"❌ Failed to fetch profile HTML for {url}. See scraper.log for details.")
        sys.exit(1)

    logging.info("🧩 Parsing profile data from HTML...")
    print("🧩 Parsing profile data...")
    profile = parse_profile(html)

    if not profile or (not profile.get('name') and not profile.get('headline')):
         logging.warning("⚠️ Parsing resulted in minimal data (name/headline not found).")
         print("⚠️  Parsed minimal data. LinkedIn structure may have changed or profile is private.")
         if not profile:
             logging.error("Parsing returned no data at all. Exiting.")
             print("❌ Parsing failed entirely. Exiting.")
             sys.exit(1)

    logging.info("✍️ Formatting bio with OpenAI...")
    print("✍️  Formatting bio with ChatGPT...")
    bio = format_bio(profile)

    output_filename = "bio.txt"
    json_filename = "profile_data.json"

    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(bio)
        logging.info(f"✅ Done! Bio saved to {output_filename}")
        print(f"✅ Done! Bio saved to {output_filename}")

        if profile:
            with open(json_filename, "w", encoding="utf-8") as f:
                 json.dump(profile, f)
            logging.info(f"Structured data saved to {json_filename}")
            print(f"Structured data saved to {json_filename}")
        else:
            logging.warning("No profile data to save as JSON.")

    except Exception as e:
         logging.error(f"❌ Error saving output files: {e}", exc_info=True)
         print(f"❌ Error saving files: {e}. Check scraper.log.")

if __name__ == "__main__":
    main()
