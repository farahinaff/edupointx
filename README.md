# EduPointX

EduPointX now runs as a publishable FastAPI web app with `EDUPOINTX/main.py` as the deployment source.

## Source Of Truth

- Main app entrypoint: `EDUPOINTX/main.py`
- Web UI assets: `EDUPOINTX/static/`
- Shared data/backend modules: `EDUPOINTX/`
- Legacy design assets still used by the web app: `EDUPOINTX/assets/`

## Local Run

Install with `pip`:

```bash
pip install -r requirements.txt
uvicorn EDUPOINTX.main:app --reload
```

Install with Poetry:

```bash
poetry install
poetry run uvicorn EDUPOINTX.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Demo Accounts

- Student: `ali` / `password123`
- Teacher: `hassan` / `password123`
- Admin: `aishah` / `password123`

## Database

The app uses SQLite by default.

- Local default DB: `EDUPOINTX/data/edupointx.db`
- Render persistent DB path: `/var/data/edupointx.db`

The app automatically uses `/var/data` when that disk exists, which makes Render setup simple.

## Render Deployment

This repo includes `render.yaml` and uses:

- Build command:
  `pip install -r requirements.txt`
- Start command:
  `uvicorn EDUPOINTX.main:app --host 0.0.0.0 --port $PORT`
- Persistent disk mount:
  `/var/data`

### Render Steps

1. Push this repo to GitHub.
2. In Render, create a new Web Service from the repo.
3. Let Render detect `render.yaml`.
4. Deploy.
5. Render will mount a persistent disk at `/var/data`.
6. The app will automatically create and use `/var/data/edupointx.db`.
7. Open the Render public URL from any device.

## QR Flow

The app supports both:

- QR-style direct links such as `?action=addpoints&sid=1` and `?action=redeem&sid=1`
- Teacher QR image upload for add-points flow

## Notes

- The old Streamlit app is no longer the deployment path.
- `EDUPOINTX/main.py` is now the active online app source.
