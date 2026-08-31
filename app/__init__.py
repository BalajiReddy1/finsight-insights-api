"""Load .env once, before anything reads os.environ."""

from dotenv import load_dotenv

load_dotenv()
