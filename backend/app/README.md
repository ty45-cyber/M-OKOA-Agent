# M-Okoa Agent 🇰🇪

> **AI-powered M-Pesa financial co-pilot for Kenyan micro-entrepreneurs.**  
> Built on Daraja 3.0 for the M-Pesa Africa × GOMYCODE "Money in Motion" Hackathon.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-mokoa.vercel.app-00D664?style=for-the-badge&logo=vercel)](https://mokoa.vercel.app)
[![Backend](https://img.shields.io/badge/API-Railway-purple?style=for-the-badge)](https://mokoa-api.railway.app)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

---

## 🎯 The Problem — The "Nairobi Hustle"

Kamau runs a hardware shop with 3 M-Pesa Tills for his delivery business.  
Every night he:

- Spends **2 hours** manually matching M-Pesa SMS receipts to invoices
- Loses money to **transaction fee leakage** — sending in small chunks instead of optimised batches
- Has **no idea** if he can afford a business expense because "money is still in the Till"
- Accidentally **spends KRA tax money** because it's mixed with his float
- Pays school fees through an **intermediary** who sometimes pockets a cut

**This is the daily reality for 40+ million M-Pesa users in Kenya.**

---

## ✅ The Solution — M-Okoa Agent

An **AI-first financial co-pilot** that sits on top of the M-Pesa Daraja 3.0 API.  
It doesn't just *track* money — it **optimises the motion of money** using agentic workflows.
```
User: "Lipa KPLC bill, only if my balance is above 5k"

M-Okoa Agent:
  → Checks balance via Daraja Account Balance API
  → Balance is KES 12,340 ✓ (above 5k)
  → Triggers STK Push to user's phone
  → User taps PIN
  → Ledger updated, DST tax locked automatically
  → "Done! KPLC imelipwa. Umebaki na KES 11,340."
```

---

## 🏆 Money in Motion — All Four Challenge Areas

| Challenge Area | Daraja API Used | Impact |
|---|---|---|
| **Merchant Collections** | Transaction Status API | 2 hours of reconciliation → 0 minutes |
| **Farmer Payments** | B2C Disbursement API | 14 days to payout → 14 seconds |
| **Student Finance** | STK Push → Verified Paybill | Fee misdirection rate 12% → 0% |
| **Community (Chama)** | Account Balance API | Treasurer embezzlement disputes → eliminated |

---

## 🖥️ Screenshots

### Dashboard — Total Float & Cash Flow
![Dashboard](docs/screenshots/dashboard.png)

### Agent Chat — Swahili / Sheng / English
![Agent](docs/screenshots/agent.png)

### Mini App Demo — Inside M-Pesa Super App
![MiniApp](docs/screenshots/miniapp-demo.png)

### Tills — Smart Float Automation
![Tills](docs/screenshots/tills.png)

### Tax Vault — KRA Auto-compliance
![Tax](docs/screenshots/tax-vault.png)

### Challenge Areas — Money in Motion Personas
![Domain](docs/screenshots/challenge-areas.png)

---

## 🌐 Live Demo

| Interface | URL | Description |
|---|---|---|
| **Web Dashboard** | [mokoa.vercel.app](https://mokoa.vercel.app) | Full React PWA |
| **API Docs** | [mokoa-api.railway.app/docs](https://mokoa-api.railway.app/docs) | FastAPI Swagger (dev only) |
| **Telegram Bot** | [@MokoaAgentBot](https://t.me/MokoaAgentBot) | Low-data interface |
| **Mini App Demo** | [mokoa.vercel.app/miniapp](https://mokoa.vercel.app/miniapp) | Phone simulator in browser |

### 🔑 Test Account Credentials
```
Phone:    +254712000001
Password: Demo@1234

# Pre-loaded with:
# - 3 demo tills (Mama Mboga, Delivery, Hardware Shop)
# - 30 days transaction history
# - Smart Float rule configured
# - Chama wallet with 20 members
```

> **Note:** The demo account runs against the Daraja **sandbox** environment.
> STK Push callbacks are simulated. Real money is never moved in demo mode.

---

## ⚡ Key Features

### 🤖 AI Agent (LangGraph + Claude)
- Understands **Swahili, Sheng, and English** natively
- Executes **conditional payments**: "Lipa tu kama balance iko juu ya 5k"
- **13 tools** wired to real Daraja APIs
- **Resumable sessions** — if a Daraja callback is delayed, the agent picks up exactly where it stopped
- Domain-aware system prompts per challenge area (merchant / farmer / student / community)

### 💸 Smart Float Optimizer
- Monitors till balance continuously
- Auto-triggers B2C disbursement when threshold exceeded
- Moves excess to SACCO, bank account, or Chama paybill
- 5-minute cooldown prevents rapid-fire transfers
- Full audit trail on every automated action

### 🔒 Privacy-First (Daraja 3.0)
- Daraja 3.0 **Security API** for Mini App identity — raw MSISDN never stored
- Phone numbers hashed with SHA-256 + secret salt for audit logs
- All Daraja credentials encrypted with **AES-256 (Fernet)** before database storage
- Kenya Data Protection Act (2019) compliant

### 🧾 KRA Auto-compliance
- **DST (1.5%)** locked automatically on every M-Pesa inflow
- **VAT (16%)** for enterprise-tier (VAT-registered businesses)
- Virtual sub-wallet prevents accidental spending of tax money
- Monthly filing reminders with iTax deadlines

### 📱 M-Pesa Mini App (Daraja 3.0)
- Runs **inside the M-Pesa Super App** — no separate download
- Balance aggregator, AI agent chat, STK Push — three screens
- Built with the official **M-Pesa Mini Program SDK**
- Access to 40+ million M-Pesa users from day one

### 📊 SMS-to-Insight Engine
- Forward M-Pesa confirmation SMS → auto-parsed into ledger
- Two-pass parsing: regex patterns first, Claude fallback for edge cases
- Works via web dashboard or **Telegram** (forward directly in chat)

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT INTERFACES                        │
│  React PWA (Vercel)  │  Telegram Bot  │  M-Pesa Mini App    │
└──────────────────────┼────────────────┼─────────────────────┘
                       │                │
                       ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Railway)                       │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  LangGraph  │  │ Daraja 3.0   │  │   Tax Engine     │   │
│  │  Agent      │  │ Service      │  │   DST + VAT      │   │
│  │  (Claude)   │  │ STK/B2C/Bal  │  │   KRA compliance │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  MariaDB    │  │    Redis     │  │  Security API    │   │
│  │  Ledger     │  │  Cache +     │  │  Identity +      │   │
│  │  Tax Locks  │  │  Agent State │  │  Fraud Check     │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  M-PESA DARAJA 3.0 APIs                      │
│  STK Push  │  C2B  │  B2C  │  Account Balance  │  Tx Status │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Version | Role |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | 0.115 | API framework, async webhooks |
| LangGraph | 0.2.60 | Agentic workflow orchestration |
| Claude claude-sonnet-4-20250514 (Anthropic) | Latest | NLP, Swahili/Sheng understanding |
| SQLAlchemy | 2.0 | Async ORM |
| MariaDB | 10.11 | Financial ledger, audit trail |
| Redis | 7.0 | Agent state, STK correlation, rate limiting |
| python-telegram-bot | 21.9 | Telegram bot interface |
| Daraja 3.0 | v3 | M-Pesa STK Push, C2B, B2C, Balance, Security API |
| Africa's Talking | Latest | SMS inbox parsing |

### Frontend
| Technology | Version | Role |
|---|---|---|
| React | 18.3 | UI framework |
| Vite | 5.4 | Build tool |
| Zustand | 5.0 | Global state (auth, tills) |
| Recharts | 2.12 | Cash flow charts |
| Axios | 1.7 | API client with JWT refresh |
| date-fns | 4.1 | Date formatting |

### Infrastructure
| Service | Role |
|---|---|
| Railway | FastAPI backend + MariaDB + Redis |
| Vercel | React frontend, edge CDN |
| Safaricom Daraja Portal | M-Pesa API credentials |
| Anthropic API | Claude claude-sonnet-4-20250514 |

### Mini App
| Technology | Role |
|---|---|
| M-Pesa Mini Program SDK | Mini App runtime (.axml + .js) |
| Mini Program Studio | Development + testing IDE |
| Daraja 3.0 Security API | Privacy-first identity resolution |

### AI Tools Used in Development
- **Claude (Anthropic)** — agent brain, Swahili NLP, SMS parsing fallback
- **LangGraph** — stateful multi-step agent graph with checkpointing

---

## 📁 Repository Structure
```
m-okoa-agent/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/v1/             # REST endpoints
│   │   │   ├── auth.py
│   │   │   ├── tills.py
│   │   │   ├── transactions.py
│   │   │   ├── agent.py
│   │   │   ├── sms.py
│   │   │   ├── domain_modes.py
│   │   │   ├── miniapp_auth.py
│   │   │   └── daraja_webhooks.py
│   │   ├── core/               # Config, DB, Redis, Security
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   └── services/           # Business logic
│   │       ├── agent_service.py
│   │       ├── daraja_service.py
│   │       ├── merchant_service.py
│   │       ├── farmer_service.py
│   │       ├── student_service.py
│   │       ├── community_service.py
│   │       ├── tax_service.py
│   │       ├── sms_service.py
│   │       ├── till_service.py
│   │       ├── auth_service.py
│   │       ├── audit_service.py
│   │       ├── smart_float_executor.py
│   │       └── security_api_service.py
│   ├── database/
│   │   └── schema.sql
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                   # React PWA
│   ├── src/
│   │   ├── pages/
│   │   │   ├── auth/           # Login, Register
│   │   │   ├── dashboard/      # Main dashboard + components
│   │   │   ├── tills/          # Till management + drawers
│   │   │   ├── agent/          # AI chat interface
│   │   │   ├── ledger/         # Transaction history
│   │   │   ├── tax/            # Tax vault
│   │   │   ├── sms/            # SMS inbox
│   │   │   ├── domain/         # Challenge area switcher
│   │   │   ├── miniapp/        # Mini App demo simulator
│   │   │   └── settings/       # Profile, security, Telegram
│   │   ├── components/
│   │   │   ├── ui/             # Button, Card, Badge
│   │   │   └── layout/         # Sidebar, AppLayout, AuthLayout
│   │   ├── hooks/              # useDashboard, useTills
│   │   ├── store/              # Zustand auth + till stores
│   │   ├── lib/                # API client, formatters
│   │   └── styles/             # globals.css (Nairobi Noir)
│   ├── public/
│   │   ├── mokoa-icon.svg
│   │   └── manifest.json
│   ├── index.html
│   ├── vite.config.js
│   ├── vercel.json
│   └── .env.example
│
├── miniapp/                    # M-Pesa Mini App (Daraja 3.0)
│   ├── app.json
│   ├── app.js
│   ├── pages/
│   │   ├── home/               # Balance aggregator
│   │   ├── agent/              # AI chat interface
│   │   └── pay/                # STK Push
│   └── README.md
│
└── README.md                   # This file
```

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.12+
- Node.js 20+
- MariaDB 10.11+
- Redis 7+
- A Safaricom Daraja developer account
- An Anthropic API key

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/m-okoa-agent.git
cd m-okoa-agent
```

### 2. Backend setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Copy and fill environment variables
cp .env.example .env
# Edit .env with your credentials (see Environment Variables section)

# Create the database
mysql -u root -p -e "CREATE DATABASE mokoa CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p mokoa < database/schema.sql

# Run the development server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend setup
```bash
cd frontend

# Install dependencies
npm install

# Copy and fill environment variables
cp .env.example .env.local
# Set VITE_API_URL=http://localhost:8000

# Run development server
npm run dev
# Opens at http://localhost:5173

# Build for production
npm run build
```

### 4. Telegram Bot setup
```bash
# Create a bot via @BotFather on Telegram
# Set the token in backend/.env as TELEGRAM_BOT_TOKEN

# In development, use ngrok to expose localhost:8000
ngrok http 8000

# Set DARAJA_CALLBACK_BASE_URL to your ngrok URL
# The bot webhook registers automatically on server startup
```

### 5. Deploy to Railway (backend)
```bash
# Install Railway CLI
npm install -g @railway/cli

railway login
railway init
railway add --database mariadb
railway add --database redis
railway up

# Set environment variables in Railway dashboard
# Point DARAJA_CALLBACK_BASE_URL to your Railway URL
```

### 6. Deploy to Vercel (frontend)
```bash
cd frontend

# Install Vercel CLI
npm install -g vercel

vercel

# Set VITE_API_URL to your Railway backend URL in Vercel dashboard
# vercel.json handles SPA routing automatically
```

---

## 🔑 Environment Variables

### Backend (`backend/.env`)
```bash
# App
ENVIRONMENT=development
SECRET_KEY=                        # openssl rand -hex 32
FIELD_ENCRYPTION_KEY=              # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Database
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/mokoa

# Redis
REDIS_URL=redis://localhost:6379/0

# Daraja (M-Pesa)
DARAJA_BASE_URL=https://sandbox.safaricom.co.ke
DARAJA_CALLBACK_BASE_URL=https://your-app.railway.app
DARAJA_PLATFORM_CONSUMER_KEY=      # From Safaricom Developer Portal
DARAJA_PLATFORM_CONSUMER_SECRET=   # From Safaricom Developer Portal

# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-...

# Telegram
TELEGRAM_BOT_TOKEN=                # From @BotFather

# Africa's Talking
AFRICASTALKING_API_KEY=
AFRICASTALKING_USERNAME=sandbox
```

### Frontend (`frontend/.env.local`)
```bash
VITE_API_URL=http://localhost:8000
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Authenticate |
| POST | `/api/v1/auth/miniapp-login` | Mini App identity exchange |
| GET  | `/api/v1/tills/` | List user's tills |
| GET  | `/api/v1/tills/balances/all` | Aggregate all balances |
| POST | `/api/v1/tills/{id}/smart-float-rules` | Create automation rule |
| POST | `/api/v1/agent/message` | Send message to AI agent |
| GET  | `/api/v1/transactions/` | Paginated ledger |
| GET  | `/api/v1/transactions/summary/ledger` | Monthly summary |
| POST | `/api/v1/sms/forward` | Forward M-Pesa SMS for parsing |
| POST | `/api/v1/domain/set` | Switch challenge area persona |
| POST | `/api/v1/daraja/stk-callback` | Safaricom STK Push callback |
| POST | `/api/v1/daraja/c2b-confirmation` | Safaricom C2B callback |
| POST | `/api/v1/daraja/b2c-result` | Safaricom B2C callback |
| POST | `/api/v1/daraja/balance-result` | Safaricom Balance callback |

---

## 🧪 Testing the Demo

### Quick demo flow (5 minutes)

**1. Dashboard**
```
Login with test account → See 3 till balances aggregate live
```

**2. Agent Chat** — type any of these:
```
"Uko na pesa ngapi kwa till zote?"
"Lipa KPLC 1000 kama balance iko juu ya 5k"
"Nionyeshe transactions za wiki iliyopita"
"Kodi yangu ya KRA mwezi huu ni ngapi?"
```

**3. Challenge Areas**
```
Switch to Merchant → type "Nionyeshe malipo ya leo"
Switch to Farmer   → type "Lipa mkulima kwa mahindi"
Switch to Chama    → type "Taarifa ya Chama yetu"
```

**4. Mini App Demo**
```
Navigate to /miniapp → Interact with the phone simulator
Watch the live API activity log update in real time
```

**5. SMS Import**
```
Navigate to /sms
Paste this SMS:
"RBA67XXXXX Confirmed. KES1,234.00 received from JOHN DOE
0712345678 on 1/3/25 at 10:30 AM.
New M-PESA balance is KES12,340.00."
Click Parse & Import → See it appear in the ledger
```

---

## 🔐 Security

- **OWASP Top 10** compliance across all endpoints
- Daraja credentials encrypted with **AES-256 (Fernet)** before storage
- JWT access tokens (60 min) + refresh tokens (30 days)
- **bcrypt** password hashing
- STK Push callbacks use **idempotency keys** — no double-processing
- All Daraja callbacks always return HTTP 200 (prevents Safaricom retry storms)
- Raw MSISDNs never stored for Mini App users (Daraja 3.0 Security API)
- Immutable **audit log** for every sensitive action
- Rate limiting via Redis

---

## 👥 Team

Jessicah Mmbone  Frontend dev
Milka Muthoni Frontend dev
Sarah Atieno Otieno UI/UX
Branham Kola Fullstack software Engineer and Team Lead
Ian Ongeri Product Manager
Amos Owuor Backend Engineer

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- **Safaricom** — for the Daraja 3.0 API platform and Mini App SDK
- **M-Pesa Africa × GOMYCODE** — for the Money in Motion hackathon
- **Anthropic** — for Claude claude-sonnet-4-20250514 and the API powering the agent brain
- **LangGraph (LangChain)** — for the agentic workflow framework

---

*Built with ❤️ in Nairobi. Kwa wauzaji wadogo, wakulima, wanafunzi, na Chama za Kenya.*