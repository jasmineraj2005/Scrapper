# 🤖 Agentic LinkedIn Scraper Framework

This framework uses **Playwright** (for browser automation) and **OpenAI** (for AI-powered extraction and summarization) to robustly scrape and summarize LinkedIn profiles.

---

## ✨ Features

- 🤖 **Agentic Extraction**: AI adaptively extracts all relevant profile sections (experience, education, volunteering, etc.)
- 🔄 **No Hardcoding**: No hardcoded selectors, API keys, or prompts. Everything is configurable.
- 📝 **Summary Only**: Outputs a detailed, professional summary for each profile in `profile_summary.md`.
- 🧩 **Modular & Extensible**: Easily adapt for other sites or data needs.

---

## ⚙️ Requirements

- Python 3.8+
- Playwright
- OpenAI Python SDK
- A valid OpenAI API key (set in `.env` as `OPENAI_API_KEY`)

---

## 🚀 Usage

### 🔗 Single Profile

```bash
python main.py "https://www.linkedin.com/in/sample-profile-1/"
```

This will save the summary to `profile_summary.md`.

### 📑 Multiple Profiles (Batch Mode)

You can run the script in a loop from the shell to process multiple profiles:

```bash
# profiles.txt contains one LinkedIn profile URL per line
# Example contents:
# https://www.linkedin.com/in/sample-profile-1/
# https://www.linkedin.com/in/sample-profile-2/
# https://www.linkedin.com/in/sample-profile-3/
while read url; do
  python main.py "$url"
done < profiles.txt
```

Each run will overwrite `profile_summary.md` with the latest summary. To save each summary separately, you can use:

```bash
while read url; do
  python main.py "$url"
  cp profile_summary.md "summary_$(basename $url).md"
done < profiles.txt
```

---

## 🗝️ .env Example

```
OPENAI_API_KEY=sk-...
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
```

---

## 📝 Notes

- For production, remove any hardcoded API keys from the script.
- The script currently outputs only the summary, not the raw JSON.
- You can customize the extraction and summary prompts by editing the script.

---

## 📁 Project Structure

- `main.py` — The main scraping and summarization script
- `README.md` — This documentation
- `requirements.txt` — Python dependencies
- `.env` — Your API keys and credentials (not included in version control)

---

## 💡 Tip

- You can easily adapt this framework for other sites or data needs by changing the prompts and selectors.

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
