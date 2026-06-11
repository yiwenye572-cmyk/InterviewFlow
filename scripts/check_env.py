import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import dotenv_values

from app.config import get_settings

s = get_settings()
k = s.dashscope_api_key
raw = (dotenv_values(".env").get("DASHSCOPE_API_KEY") or "")

print("len", len(k))
print("prefix_ok", k.startswith("sk-"))
print("has_outer_whitespace", k != k.strip())
print("dotenv_len", len(raw))
print("settings_match_dotenv", raw.strip() == k)
print("is_placeholder", k == "sk-xxx")
