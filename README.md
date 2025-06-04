# LinkedIn Profile Scraper

A powerful LinkedIn profile scraper that uses Playwright for web automation and OpenAI's GPT-4 for intelligent data extraction. This tool can extract and format professional profiles into structured data and readable summaries.

## Features

- 🔐 Secure LinkedIn authentication with cookie management
- 🌐 Automated profile navigation and content expansion
- 🤖 Intelligent data extraction using OpenAI's GPT-4
- 📊 Structured JSON output
- 📝 Formatted text summaries
- 🔄 Handles dynamic content loading
- 🛡️ Respects LinkedIn's rate limits

## Prerequisites

- Python 3.9 or higher
- OpenAI API key
- LinkedIn account credentials

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd linkedin-scraper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

4. Create a `.env` file in the project root with your credentials:
```
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
OPENAI_API_KEY=your_openai_api_key
```

## Usage

1. First, authenticate with LinkedIn:
```bash
python main.py --login
```

2. Scrape a profile:
```bash
python main.py "https://www.linkedin.com/in/profile-url/"
```

## Output

The script generates two files:
- `profile_extracted.json`: Raw structured data in JSON format
- `bio.txt`: Formatted human-readable summary of the profile

## How It Works

1. **Authentication**: Uses Playwright to log into LinkedIn and save session cookies
2. **Profile Navigation**: 
   - Navigates to the target profile
   - Scrolls through the page
   - Expands "See more" sections
3. **Data Extraction**:
   - Extracts HTML from different profile sections
   - Uses GPT-4 to intelligently parse the HTML
   - Structures the data into JSON format
4. **Output Generation**:
   - Saves raw data as JSON
   - Creates a formatted text summary

## Project Structure

```
├── main.py              # Main script
├── requirements.txt     # Python dependencies
├── .env                # Environment variables (not in repo)
├── cookies.pkl         # LinkedIn session cookies
├── profile_extracted.json  # Raw profile data
└── bio.txt             # Formatted profile summary
```

## Dependencies

- `playwright`: Web automation
- `openai`: GPT-4 integration
- `python-dotenv`: Environment variable management
- `asyncio`: Asynchronous operations

## Security Notes

- Never commit your `.env` file
- Keep your LinkedIn credentials secure
- Don't share your OpenAI API key
- Use responsibly and respect LinkedIn's terms of service

## Limitations

- Requires valid LinkedIn account
- Needs OpenAI API key
- May be affected by LinkedIn's anti-scraping measures
- Rate limited by OpenAI API usage

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with LinkedIn's terms of service and rate limits.
