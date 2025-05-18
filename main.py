import os
import sys
import time
import random
import pickle
import json
import openai
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)
from bs4 import BeautifulSoup
import logging

# --- Configuration ---
COOKIE_FILE = "cookies.pkl"
LOG_FILE = "scraper.log"
SCROLL_PAUSE_TIME = 2
MAX_SCROLLS = 20
PAGE_LOAD_TIMEOUT = 90
ELEMENT_TIMEOUT = 15

PROXIES = [] # Add your proxies here if needed

# Configure logging
logging.basicConfig(
    level=logging.INFO, # Default to INFO for less verbose console output
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Helper Functions ---
def random_delay(a=1.0, b=4.0):
    time.sleep(random.uniform(a, b))
    logging.debug(f"Waited for {time.uniform(a, b):.2f} seconds.")

def get_random_proxy():
    if PROXIES:
        proxy = random.choice(PROXIES)
        logging.debug(f"Using proxy: {proxy}")
        return proxy
    logging.debug("No proxies configured.")
    return None

def init_driver(load_cookies=True, use_proxy=True):
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")

    proxy = get_random_proxy() if use_proxy and PROXIES else None
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')

    driver = None
    try:
        logging.info("Initializing undetected-chromedriver...")
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

        if load_cookies and os.path.exists(COOKIE_FILE):
            driver.get("https://www.linkedin.com")
            random_delay(1, 2)
            try:
                with open(COOKIE_FILE, "rb") as f:
                    cookies = pickle.load(f)
                    for c in cookies:
                         if '.linkedin.com' in c.get('domain', ''):
                             try:
                                cookie_dict = {k: v for k, v in c.items() if k != 'sameSite'}
                                driver.add_cookie(cookie_dict)
                             except Exception as add_cookie_e:
                                logging.debug(f"Could not add cookie {c.get('name')}: {add_cookie_e}")
                logging.debug("Attempted to load cookies.")
                random_delay(1, 2)
                driver.get("https://www.linkedin.com/feed") # Try navigating to logged-in page
                random_delay(3, 5)
            except Exception as e:
                logging.warning(f"Failed to load or apply cookies from {COOKIE_FILE}: {e}")

        logging.info("WebDriver initialized successfully.")
        return driver

    except Exception as e:
        logging.error(f"Error initializing WebDriver: {e}", exc_info=True)
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
        logging.debug(f"Element not found/visible within {timeout}s by {by}: {value}. Trying presence.")
        try:
             element = WebDriverWait(driver, timeout).until(
                 EC.presence_of_element_located((by, value))
             )
             logging.debug(f"Found element by {by}: {value} via presence.")
             return element
        except (TimeoutException, NoSuchElementException):
             logging.debug(f"Element not found/present within {timeout}s by {by}: {value}")
             return None
    except Exception as e:
        logging.error(f"Error finding element by {by}: {value} - {e}", exc_info=True)
        return None

def check_for_captcha_or_block(driver):
    try:
        source = driver.page_source.lower()
        url = driver.current_url.lower()
        captcha_keywords = ["verify you are human", "captcha", "i'm not a robot"]
        block_keywords = ["access to this page has been denied", "something went wrong", "too many requests", "page not found", "unavailable"]

        if any(k in source for k in captcha_keywords + block_keywords) or \
           "linkedin.com/checkpoint/challenge/" in url or \
           "linkedin.com/error/" in url:
             logging.warning(f"Potential CAPTCHA, challenge, or block detected. URL: {url}")
             return True

        if safe_find_element(driver, By.ID, "login-submit") or \
           safe_find_element(driver, By.XPATH, "//*[contains(text(), 'Please verify you are not a robot') or contains(text(), 'security check')]"):
             logging.warning("Potential CAPTCHA or challenge element detected.")
             return True

    except WebDriverException as e:
         logging.debug(f"Error during captcha/block check: {e}")
         pass
    return False

# --- Core Scraper Functions ---

def login():
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        logging.error("Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables.")
        return False

    driver = None
    try:
        driver = init_driver(load_cookies=False, use_proxy=True)
        if not driver: return False

        logging.info("Navigating to login page.")
        driver.get("https://www.linkedin.com/login")
        random_delay(3, 5)

        if check_for_captcha_or_block(driver):
             logging.error("Login page blocked or CAPTCHA.")
             return False

        logging.info("Attempting login...")
        user_f = safe_find_element(driver, By.ID, "username")
        pass_f = safe_find_element(driver, By.ID, "password")
        submit_b = safe_find_element(driver, By.CSS_SELECTOR, "button[type=submit]") or \
                   safe_find_element(driver, By.XPATH, "//button[contains(., 'Sign in')]")

        if not all([user_f, pass_f, submit_b]):
            logging.error("Login form elements not found.")
            return False

        # Simulate typing
        [user_f.send_keys(char) or time.sleep(random.uniform(0.05, 0.15)) for char in email]
        random_delay(0.8, 1.5)
        [pass_f.send_keys(char) or time.sleep(random.uniform(0.05, 0.15)) for char in password]
        random_delay(0.8, 1.5)

        submit_b.click()
        logging.info("Login form submitted.")
        random_delay(6, 10)

        current_url = driver.current_url
        success_indicator = safe_find_element(driver, By.ID, "global-nav-search", timeout=20)

        if success_indicator and ("feed" in current_url or "mynetwork" in current_url or "linkedin.com/in/" not in current_url):
             logging.info("Login successful.")
             try:
                with open(COOKIE_FILE, "wb") as f:
                    pickle.dump(driver.get_cookies(), f)
                logging.info(f"Cookies saved to {COOKIE_FILE}.")
             except Exception as e:
                 logging.warning(f"Failed to save cookies: {e}")
             return True
        else:
             logging.warning(f"Login failed. URL: {current_url}. Indicator not found.")
             if check_for_captcha_or_block(driver):
                 logging.error("CAPTCHA/block after login submission.")
             return False

    except Exception as e:
        logging.error(f"Login error: {e}", exc_info=True)
        return False
    finally:
        if driver: driver.quit()
        logging.info("WebDriver quit after login.")

def fetch_html(url):
    driver = None
    try:
        driver = init_driver(load_cookies=True, use_proxy=True)
        if not driver:
            logging.error("Failed to init driver for fetch.")
            return None

        logging.info(f"Navigating to {url}")
        driver.get(url)
        random_delay(6, 10)

        if check_for_captcha_or_block(driver):
             logging.error(f"Blocked or CAPTCHA on {url}.")
             return None

        logging.info("Starting dynamic scrolling...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        scroll_attempts_without_growth = 0

        while scroll_count < MAX_SCROLLS:
            scroll_count += 1
            logging.debug(f"Scrolling attempt {scroll_count}")
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            random_delay(SCROLL_PAUSE_TIME - 0.5, SCROLL_PAUSE_TIME + 0.5)

            new_height = driver.execute_script("return document.body.scrollHeight")
            logging.debug(f"Old Height: {last_height}, New Height: {new_height}")

            if new_height == last_height:
                scroll_attempts_without_growth += 1
                if scroll_attempts_without_growth >= 3:
                     logging.info("Page height stopped growing.")
                     break
            else:
                 scroll_attempts_without_growth = 0

            if check_for_captcha_or_block(driver):
                logging.warning("CAPTCHA/block detected during scrolling.")
                break

            last_height = new_height

        logging.info(f"Finished scrolling after {scroll_count} attempts.")
        random_delay(2, 3)

        html = driver.page_source
        logging.info("HTML fetched successfully.")
        return html

    except TimeoutException:
        logging.error(f"Page load timeout fetching {url}.", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Fetch error for {url}: {e}", exc_info=True)
        return None
    finally:
        if driver: driver.quit()
        logging.info("WebDriver quit after fetch.")


def parse_profile(html):
    if not html:
        logging.warning("No HTML to parse.")
        return None

    soup = BeautifulSoup(html, "html.parser")
    data = {
        "name": None, "headline": None, "about": None,
        "experience": [], "education": [], "skills": []
    }

    # NAME
    name_el = soup.select_one("h1.text-heading-xlarge, h1.pv-top-card__list li, .text-color-text.page-common h1")
    if name_el: data["name"] = name_el.get_text(strip=True)
    else: logging.debug("Name not found.")

    # HEADLINE
    headline_el = soup.select_one(".text-body-medium, .pv-text-details__current-company-occupation, .text-color-text.page-common .text-body-small")
    if headline_el: data["headline"] = headline_el.get_text(strip=True)
    else: logging.debug("Headline not found.")

    # ABOUT
    about_section = soup.find("section", {"id": "about"}) or soup.find("div", {"id": "about"}) or soup.select_one(".artdeco-card.pv-about-module")
    if about_section:
        about_text_el = about_section.select_one("span.lt-line-clamp__line, div.pv-about__summary-text, .pv-shared-text-area")
        if about_text_el: data["about"] = about_text_el.get_text(strip=True)
        else: logging.debug("About text not found.")
    else: logging.debug("About section not found.")

    # EXPERIENCE
    exp_sec = soup.find("section", {"id": "experience-section"}) or soup.find("div", {"id": "experience"})
    if exp_sec:
        logging.info("Parsing Experience...")
        items = exp_sec.select(".pv-profile-section__card-item, .artdeco-list__item, .pv-position-entity, .pvs-list__paged-list-item")
        for item in items:
            role_el = item.select_one("h3, .pv-entity__summary-info h3, .t-bold span[aria-hidden='true'], .t-bold .visually-hidden + span")
            comp_el = item.select_one(".pv-entity__secondary-title, .t-black--light span[aria-hidden='true']")
            role = role_el.get_text(strip=True) if role_el else "N/A"
            company = comp_el.get_text(strip=True) if comp_el else "N/A"
            if role != "N/A" or company != "N/A":
                data["experience"].append({"role": role, "company": company})
        logging.info(f"Parsed {len(data['experience'])} experience entries.")
    else: logging.debug("Experience section not found.")

    # EDUCATION
    edu_sec = soup.find("section", {"id": "education-section"}) or soup.find("div", {"id": "education"})
    if edu_sec:
        logging.info("Parsing Education...")
        items = edu_sec.select(".pv-profile-section__card-item, .artdeco-list__item, .pv-education-entity, .pvs-list__paged-list-item")
        for item in items:
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

    # SKILLS
    skills_sec = soup.find("div", {"id": "skills"}) or soup.find("section", {"id": "skills-section"})
    if skills_sec:
        logging.info("Parsing Skills...")
        skill_elements = skills_sec.select(".pv-skill-category-entity__name-text, .t-14.t-black.t-normal.lt-line-clamp__line, .pvs-list__outer-container .t-14.t-black.t-normal")
        if skill_elements:
            data["skills"] = [s.get_text(strip=True) for s in skill_elements if s.get_text(strip=True)]
            logging.info(f"Parsed {len(data['skills'])} skills.")
        else: logging.debug("No skills found.")
    else: logging.debug("Skills section not found.")

    return data


def format_bio(profile_data):
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
         logging.error("OPENAI_API_KEY env var not set.")
         return "Error: OpenAI API key missing."

    try: client = openai.OpenAI(api_key=openai_api_key)
    except Exception as e:
        logging.error(f"Error init OpenAI client: {e}")
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

    logging.info("Sending data to OpenAI for bio...")
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
        logging.info("Bio formatting successful.")
        return bio_text

    except Exception as e:
        logging.error(f"OpenAI API error: {e}", exc_info=True)
        return f"Error: OpenAI API Error - {e}"


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python scrape.py [--login] [profile_url]")
        logging.info("No args.")
        sys.exit(0)

    if args[0] == "--login":
        logging.info("Running login.")
        print("Attempting login...")
        if login():
            print(f"✅ Login successful and cookies saved to {COOKIE_FILE}.")
        else:
            print("❌ Login failed. Check scraper.log.")
        sys.exit(0)

    url = args[0]
    if not url.startswith("https://www.linkedin.com/in/"):
        print("Invalid LinkedIn profile URL.")
        logging.error(f"Invalid URL: {url}")
        sys.exit(1)

    if not os.path.exists(COOKIE_FILE):
        print(f"No cookie file ({COOKIE_FILE}) found. Run with --login first.")
        logging.error("Cookie file not found. Cannot scrape.")
        sys.exit(1)

    logging.info(f"--- Starting scrape for {url} ---")
    print(f"🔍 Fetching {url}")
    html = fetch_html(url)

    if not html:
        logging.error(f"Failed to fetch HTML for {url}.")
        print(f"❌ Failed to fetch profile HTML for {url}. See scraper.log.")
        sys.exit(1)

    logging.info("🧩 Parsing profile data...")
    print("🧩 Parsing profile data...")
    profile = parse_profile(html)

    if not profile or (not profile.get('name') and not profile.get('headline')):
         logging.warning("Parsing resulted in minimal data.")
         print("⚠️  Parsed minimal data. LinkedIn structure may have changed or profile is private.")
         # Optionally save HTML for debugging if you see this warning often
         # with open("debug_page.html", "w", encoding="utf-8") as f: f.write(html)
         # logging.info("HTML saved to debug_page.html.")


    logging.info("✍️  Formatting bio with OpenAI...")
    print("✍️  Formatting bio with OpenAI...")
    bio = format_bio(profile)

    output_filename = "bio.txt"
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(bio)
        logging.info(f"✅ Done! Bio saved to {output_filename}")
        print(f"✅ Done! Bio saved to {output_filename}")

        json_filename = "profile_data.json"
        with open(json_filename, "w", encoding="utf-8") as f:
             json.dump(profile, f, indent=4)
        logging.info(f"Structured data saved to {json_filename}")

    except Exception as e:
         logging.error(f"Error saving output files: {e}", exc_info=True)
         print(f"❌ Error saving files: {e}")


if __name__ == "__main__":
    main()

