# EduPointX

EduPointX now includes two app paths:

- `main.py`: the original Streamlit prototype
- `mobile_app/`: a new mobile-first Progressive Web App

## Mobile App

The new mobile app is designed to be published online and used from a phone like an installable app.

### What changed

- Added a `FastAPI` backend for login, signup, student dashboards, teacher actions, rewards, and admin overview.
- Added a mobile-first PWA frontend with responsive UI, manifest, and service worker.
- Replaced the old private MySQL dependency for this path with a free default SQLite database.
- Seeded the database with demo data so the app works immediately after startup.

### Run locally

```bash
pip install -r requirements.txt
uvicorn mobile_app.main:app --reload
```

Open `http://127.0.0.1:8000`.

### Demo accounts

- Student: `ali` / `password123`
- Teacher: `hassan` / `password123`
- Admin: `aishah` / `password123`

### Free and accessible database

The mobile app uses SQLite by default and stores its data in:

`mobile_app/data/edupointx_mobile.db`

This makes the project:

- free to run locally
- easy to deploy without private DB secrets
- immediately usable with seeded demo data

If you want free hosted persistence later, set `DATABASE_URL` to a free hosted Postgres database such as Supabase or Neon.

### Publish online

You can publish this app on a free Python-friendly host like Render or Railway.

Build/install command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn mobile_app.main:app --host 0.0.0.0 --port $PORT
```

After deployment, users can open the URL on a phone and choose `Add to Home Screen` to install it like a mobile app.

### Scope note

This is now a publishable mobile web app (PWA). If you want true Google Play / Apple App Store packaging next, the clean follow-up step is wrapping this PWA with Capacitor.
