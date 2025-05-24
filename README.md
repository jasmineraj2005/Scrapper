# Scrapper

# LinkedIn Profile Scraper & Summarizer

This project scrapes detailed LinkedIn profile data using Selenium and generates a professional summary using OpenAI's GPT-4o model.

---

## Features

- Logs into LinkedIn automatically and saves cookies for session reuse
- Scrapes profile sections including:
  - Basic info (name, headline, location, about)
  - Work experience (roles, companies, dates, descriptions)
  - Education (schools, degrees, fields, dates)
  - Skills
  - Certifications
  - Projects
  - Recommendations received
  - Volunteer experience
  - Accomplishments (awards, publications)
- Uses OpenAI to generate a polished professional profile summary saved as `bio.txt`
- Supports proxy usage and cache disabling for stealth scraping

---

## Setup

1. Clone the repository:

   ```bash
   git clone <repo-url>
   cd <repo-folder>

2. Create a .env file in the project root with your credentials
3. Install dependencies

