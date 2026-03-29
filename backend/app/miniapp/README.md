# M-Okoa Agent — M-Pesa Mini App

The Mini App runs **inside the M-Pesa Super App** on a user's phone.
No separate download required. Access to 40+ million M-Pesa users from day one.

## What it is

A lightweight sub-application built with the official **M-Pesa Mini Program SDK**
from Safaricom. It uses `.axml` templates (like HTML), `.acss` styles (like CSS),
and `.js` logic files.

## Three screens

| Screen | What it does |
|---|---|
| **Home** | Balance aggregator across all tills |
| **Agent** | Full AI chat — Swahili, Sheng, English |
| **Pay** | STK Push bill payment with live feedback |

## How to develop and test

1. Download **Mini Program Studio** from the Safaricom developer portal
2. Open this `miniapp/` folder as a project in Mini Program Studio
3. The simulator shows exactly what the M-Pesa Super App user sees
4. Point `app.js` `config.API_BASE` to your local backend URL
5. Submit for Safaricom review via the Mini Program Platform

## How it connects to the backend

The Mini App calls the **same FastAPI backend** as the React dashboard:
```
Mini App → POST https://your-app.railway.app/api/v1/auth/miniapp-login
         → GET  https://your-app.railway.app/api/v1/tills/balances/all
         → POST https://your-app.railway.app/api/v1/agent/message
```

## Privacy — Daraja 3.0 Security API

When a user opens the Mini App, M-Pesa issues a one-time `auth_code`.
The backend exchanges this code with the Daraja 3.0 Security API
for a **masked phone** (e.g. `2547****5678`) and an opaque identity token.

**The raw MSISDN (phone number) is never stored.**
This is a 2026 Safaricom compliance requirement under the Kenya Data Protection Act.

## Documentation

- Mini App SDK docs: https://mpesaminiapps.safaricom.co.ke/docs
- Daraja 3.0 Security API: https://developer.safaricom.co.ke/APIs