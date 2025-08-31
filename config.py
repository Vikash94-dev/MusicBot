import os

# Telegram Bot Configuration
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
STRING_SESSION = os.getenv("STRING_SESSION", "")

# Music API Configuration
API_KEY = os.getenv("API_KEY", "YOUR_OWN_API_KEY")
API_URL = os.getenv("API_URL", "https://deadlinetech.site")

# Application Configuration
DEBUG = True
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# YouTube API Configuration (if using official YouTube API)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", None)
