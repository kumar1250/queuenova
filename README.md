# QueueNova — Queue Management System

## Deploy to Render.com (Recommended)

### Step 1 — Push to GitHub
```bash
git add .
git commit -m "Production ready"
git push origin main
```

### Step 2 — Deploy on Render
1. Go to [render.com](https://render.com) and sign up with GitHub
2. Click **New → Blueprint**
3. Connect your GitHub repo (`kumar1250/queuenova`)
4. Render reads `render.yaml` and auto-creates the web service + PostgreSQL database

### Step 3 — Set Environment Variables
In Render → your service → **Environment**, add:

| Variable | Value |
|---|---|
| `EMAIL_HOST_USER` | your Gmail address |
| `EMAIL_HOST_PASSWORD` | Gmail App Password (not your login password) |
| `RAZORPAY_KEY_ID` | From Razorpay Dashboard |
| `RAZORPAY_KEY_SECRET` | From Razorpay Dashboard |
| `RAZORPAY_WEBHOOK_SECRET` | From Razorpay Dashboard → Webhooks |

`SECRET_KEY` and `DATABASE_URL` are auto-set by the blueprint.

### Step 4 — Create Superuser
After deploy, open Render's **Shell** tab and run:
```bash
python manage.py createsuperuser
```

---

## Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file
cp .env.example .env
# Edit .env with your values

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Start server
python manage.py runserver
```

## Tech Stack
- Django 5.2 + Gunicorn
- PostgreSQL (Render) / SQLite (local)
- Whitenoise (static files)
- Razorpay (payments)
- django-allauth (Google OAuth)
