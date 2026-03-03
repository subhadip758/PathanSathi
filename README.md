Library Website PathanSathi — Upgraded
=============================

What's new in PathanSathi:
- Email-only usernames enforced at registration.
- Strong password validation (min length 8, upper, lower, digit, special).
- Dark mode toggle (client-side, saved to localStorage).
- Search & filter by title/author/genre + live search.
- Book metadata (author, genre) and QR-code generation per book.
- Leaderboard showing top readers (by total borrow count).
- Simple recommendation engine (suggests books from user's top genres).
- Manual "Send Due Reminders" admin action (sends emails if SMTP configured).
- Lightweight AI Chatbot helper (keyword-based) for book discovery.
- JSON persistence in data/; qrcodes stored in static/qrcodes/

Notes:
- Email sending requires SMTP config in data/config.json. If not set, reminders will be simulated (printed to console).
- Passwords are still stored plaintext here for simplicity; for production use hashing (werkzeug.security).
- To run: create venv, pip install -r requirements.txt, then python app.py

