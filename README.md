# Internship Bot 🤖📋

## Overview

Internship Bot is a powerful Discord bot designed to help students and job seekers discover the latest internship opportunities directly in their Discord server. By leveraging multiple job APIs, the bot provides real-time updates, search functionality, and easy browsing of internship postings.

## 🌟 Features

### Automatic Updates
- Periodically checks multiple job APIs for the latest internship opportunities
- Automatically posts new internships to a designated Discord channel
- Supports rate-limited API calls to prevent overwhelming the server

### Manual Commands
- `!internships`: Fetch the latest internship opportunities
- `!search`: Search internships by keywords (company, title, location)
- `!recent`: Show the most recently posted internships
- `!linkedin`: Advanced LinkedIn job search with flexible filtering

## 🛠 Prerequisites

Before running the bot, you'll need:
- Python 3.8+
- Discord Developer Account
- RapidAPI Account
- Environment variables configured

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/internship-bot.git
cd internship-bot
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## 🔐 Configuration

Create a `.env` file in the project root with the following variables:
```
DISCORD_TOKEN=your_discord_bot_token
CHANNEL_ID=your_discord_channel_id
RAPIDAPI_KEY=your_rapidapi_key
```

### Obtaining Credentials
- **Discord Token**: [Discord Developer Portal](https://discord.com/developers/applications)
- **Channel ID**: Right-click on a Discord channel and select "Copy ID" (Developer Mode must be enabled)
- **RapidAPI Key**: [RapidAPI](https://rapidapi.com/)

## 🚀 Running the Bot

```bash
python internship_bot.py
```

## 💡 Usage Examples

- `!internships`: Show 25 latest internships
- `!internships 50`: Show 50 latest internships
- `!search google`: Find internships at Google
- `!search software engineer`: Find software engineering internships
- `!recent 30`: Show 30 most recent internships
- `!linkedin`: Show LinkedIn job postings
- `!linkedin "data science" boston`: Find data science jobs in Boston

## 🔍 Advanced Search Tips

The bot supports complex search queries:
- Company names
- Job titles
- Locations
- Keywords
- Filtering by time range

## 📊 Data Sources

- Internships API (multiple endpoints)
- LinkedIn Job Search API

## 🛡️ Rate Limiting

The bot implements intelligent rate limiting to:
- Prevent API abuse
- Ensure smooth operation
- Comply with API usage guidelines

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📜 License

[Specify your license, e.g., MIT License]

## 🐛 Troubleshooting

- Ensure all environment variables are correctly set
- Check API quota and subscription status
- Verify Discord bot permissions

## 📞 Support

For issues or questions, please [open an issue](https://github.com/yourusername/internship-bot/issues) on GitHub.

---

**Happy Internship Hunting! 🎓🚀**
