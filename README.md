# ✈️ TripBot — Group Trip Expense Tracker

A production-ready Telegram bot for splitting expenses on group trips.  
Think Splitwise, but living inside your Telegram chat.

---

## Features

| Feature | Details |
|---|---|
| 👤 Auto-registration | `/start` creates your account instantly |
| ✈️ Trip management | Create trips, share invite codes, list active trips |
| 💰 Expense tracking | Add expenses with description, amount, currency, category |
| 👥 Flexible splitting | Equal split or custom percentages |
| ⚖️ Balance calculation | Debt-simplification algorithm minimises transfers |
| 📅 Daily view | `/today` — today's expenses + category breakdown |
| 📊 Trip summary | `/summary` — totals per person + final balances |
| 📸 Receipt OCR | Upload a photo → amount + merchant auto-filled |
| 💱 Multi-currency | Stores original currency, converts to trip base currency |
| 🔔 Notifications | Optional daily reminder at 21:00 local time |
| 📤 CSV export | One-click export of all trip expenses |
| 👑 Admin panel | Owner can remove members or close trip |

---

## Quick Start (Local)

### Step 1 — Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. `My Trip Bot`)
4. Choose a username ending in `bot` (e.g. `mytripexpenses_bot`)
5. BotFather replies with a token like:  
   `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`  
   **Copy it — you'll need it in the next step.**

### Step 2 — Clone and run setup

```bash
git clone https://github.com/yourname/tripbot.git
cd tripbot
bash setup.sh
```

The script will:
- Check Python version
- Copy `.env.example` → `.env`
- Pause and ask you to paste your BOT_TOKEN
- Create a virtual environment
- Install all dependencies
- Create the `data/` directory

### Step 3 — Start the bot

```bash
source .venv/bin/activate
python main.py
```

Open Telegram, find your bot, send `/start`. That's it! ✅

---

## Running with Docker

```bash
# 1. Copy and edit env
cp .env.example .env
# Paste your BOT_TOKEN into .env

# 2. Build and start
docker compose up --build -d

# 3. View logs
docker compose logs -f
```

---

## Deploy on Railway (under 5 minutes)

Railway is the easiest way to host this bot for free (500 hours/month on free tier).

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/tripbot.git
git push -u origin main
```

### Step 2 — Create Railway project

1. Go to **[railway.app](https://railway.app)** and sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `tripbot` repository
4. Railway auto-detects the `Dockerfile` and starts building

### Step 3 — Add environment variables

1. Click your service → **"Variables"** tab
2. Click **"Raw Editor"** and paste:

```
BOT_TOKEN=your_token_here
DATABASE_URL=sqlite+aiosqlite:///./data/tripbot.db
DEBUG=false
```

3. Optionally add:
```
EXCHANGE_RATE_API_KEY=your_key
OCR_SPACE_API_KEY=your_key
```

4. Click **"Update Variables"** — Railway redeploys automatically

### Step 4 — Add persistent storage (important!)

Without a volume, the SQLite database resets on every deploy.

1. In your Railway project, click **"New"** → **"Volume"**
2. Set mount path: `/app/data`
3. Attach it to your bot service
4. Redeploy

### Step 5 — Done!

Your bot is now live 24/7. Check the **"Logs"** tab to confirm it started:
```
[INFO] Database ready.
[INFO] Starting bot polling...
```

---

## Optional: Better APIs

### Exchange Rates (free tier: 1,500 req/month)
1. Sign up at https://www.exchangerate-api.com/
2. Copy your API key
3. Add to `.env`: `EXCHANGE_RATE_API_KEY=your_key`

> Without a key the bot uses the free open API (no key required, slightly rate-limited).

### OCR for Receipts (free tier: 25,000 req/month)
1. Sign up at https://ocr.space/
2. Copy your API key
3. Add to `.env`: `OCR_SPACE_API_KEY=your_key`

> Without a key the bot falls back to local `pytesseract` (requires `tesseract` installed on your system — included in the Docker image).

---

## Project Structure

```
tripbot/
├── main.py                 # Bot entrypoint
├── config.py               # Environment variables
├── database.py             # SQLAlchemy engine + session
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── setup.sh                # One-click local setup
│
├── models/                 # SQLAlchemy ORM models
│   ├── user.py
│   ├── trip.py
│   ├── expense.py
│   └── notification.py
│
├── services/               # Business logic (pure functions)
│   ├── user_service.py
│   ├── trip_service.py
│   ├── expense_service.py  # Balance calc + debt simplification
│   ├── currency_service.py # Exchange rates with caching
│   ├── ocr_service.py      # Receipt OCR
│   ├── export_service.py   # CSV export
│   └── notification_service.py
│
├── handlers/               # Telegram message/callback handlers
│   ├── start.py
│   ├── trips.py
│   ├── expenses.py
│   ├── balances.py
│   ├── receipts.py
│   └── settings.py
│
├── keyboards/              # Inline + reply keyboards
│   ├── main.py
│   ├── trips.py
│   └── expenses.py
│
├── middlewares/            # aiogram middlewares
│   ├── db.py               # Injects DB session
│   └── user.py             # Auto-registers user
│
└── utils/
    ├── states.py           # FSM states
    └── formatting.py       # Text formatting helpers
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Main menu + auto-registration |
| `/newtrip` | Create a new trip |
| `/join` | Join trip by invite code |
| `/trips` | List your active trips |
| `/today` | Today's expenses for your first active trip |
| `/summary` | Full trip summary + final balances |
| `/settings` | Notification preferences |
| `/timezone` | Set your timezone for reminders |
| `/help` | Command reference |

---

## How Debt Simplification Works

The balance algorithm runs in two steps:

1. **Net balance per user**: for each expense, the payer gains `+amount`, each participant loses their share
2. **Greedy simplification**: creditors (positive balance) are matched against debtors (negative balance), largest first — minimising the number of transfers

Example with 3 people:
```
Anna paid 90€ (split equally → everyone owes 30€)
Max paid 30€ (split equally → everyone owes 10€)

Net balances:
  Anna: +90 - 30 - 10 = +50  (is owed 50€)
  Max:  +30 - 30 - 10 = -10  (owes 10€)
  Lisa: 0   - 30 - 10 = -40  (owes 40€)

Simplified:
  Lisa owes Anna 40.00 EUR
  Max  owes Anna 10.00 EUR
```
