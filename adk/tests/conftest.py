import os

# Tests never call a real model. Clear keys so an accidental live call fails fast.
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)
