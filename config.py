import os
import logging
from dotenv import load_dotenv

# ---------------------- Setup and Configuration ----------------------

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename='bot.log',
    format='%(asctime)s:%(levelname)s:%(message)s'
)

# Access environment variables
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN2')  # Updated variable name
COMFYUI_API_URL = os.getenv('COMFYUI_API_URL', "http://127.0.0.1:8188/api/v1/generate")
COMFYUI_API_TOKEN = os.getenv('COMFYUI_API_TOKEN')
COMFYUI_SERVER_ADDRESS = os.getenv('COMFYUI_SERVER_ADDRESS', '127.0.0.1')
COMFYUI_SERVER_PORT = os.getenv('COMFYUI_SERVER_PORT', '8188')

# Verify that the tokens are loaded
if not DISCORD_TOKEN:
    logging.critical("DISCORD_BOT_TOKEN2 is not set.")
    exit(1)

# Constants for file paths and settings
BANNED_WORDS = ['badword1', 'badword2']  # Replace with actual banned words
CONFIG_FILE = 'configurations.json'
HISTORY_FILE = 'chat_history.txt'
WHATSNEW_FILE = 'whatsnew.txt'
USER_PROFILES_FILE = 'user_profiles.json'
MAX_HISTORY_SIZE = 10 * 1024 * 1024  # 10 Megabytes

# Emoji Pools
STANDARD_EMOJIS = [
    "�", "�", "❤️", "✨", "�", "�", "�", "�", "�", "�"
]
CUSTOM_EMOJIS = {}  # Will be populated per guild

# ---------------------- Helper Functions ----------------------

def get_absolute_path(filename):
    """
    Get the absolute path of a file relative to the script.
    This function helps to ensure that file paths are resolved correctly regardless of the current working directory.
    """
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

# ---------------------- Other Configuration-Related Functions ----------------------

# Add other configuration-related functions here if needed

