# Presidency University Campus Guide

Streamlit campus navigation prototype with Gemini-powered natural-language intent parsing and photo-based location identification.

## Deploy on Streamlit Community Cloud
1. Upload the contents of this folder to a GitHub repository.
2. In Streamlit Community Cloud, create an app from that repository and select `app.py` as the main file.
3. In the app's Settings → Secrets, add:

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_VISION_MODEL = "gemini-3.8-flash"
```

4. Save and redeploy. Never commit your API key to GitHub.

The `campus_reference_pages` folder must remain beside `app.py`.
