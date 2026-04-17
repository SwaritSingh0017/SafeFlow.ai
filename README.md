<div align="center">

<img src="https://img.shields.io/badge/SafeFlow.ai-AI%20Parametric%20Insurance-F57C00?style=for-the-badge&logo=shield&logoColor=white" />

# 🛡️ SafeFlow.ai

### *AI-Powered Parametric Insurance for India's Gig Workers*

> **When rain stops deliveries, SafeFlow starts paying. Automatically. Instantly. Zero claims.**

[![Live Demo](https://img.shields.io/badge/🚀%20Live%20Demo-safeflow--ai--ev3w.onrender.com-F57C00?style=flat-square)](https://safeflow-ai-ev3w.onrender.com/)
[![GitHub](https://img.shields.io/badge/GitHub-SwaritSingh0017%2FSafeFlow.ai-181717?style=flat-square&logo=github)](https://github.com/SwaritSingh0017/SafeFlow.ai)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Firebase](https://img.shields.io/badge/Firebase-Auth%20%2B%20DB-FFCA28?style=flat-square&logo=firebase&logoColor=black)](https://firebase.google.com)
[![Pitch Deck](https://img.shields.io/badge/📊%20Pitch%20Deck-View%20Now-blue?style=flat-square)](https://drive.google.com/file/d/1vJPjlD-qaFZ4XF2GCkOd7eH5jp9SVYBc/view?usp=sharing)
---

</div>

## 📌 Table of Contents

- [Problem Statement](#-problem-statement)
- [Our Solution](#-our-solution)
- [Key Features](#-key-features)
- [System Architecture](#️-system-architecture)
- [Tech Stack](#-tech-stack)
- [How It Works](#-how-it-works)
- [Product Screens](#-product-screens)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [Project Structure](#-project-structure)
- [API Reference](#-api-reference)
- [Business Model](#-business-model)
- [Roadmap](#️-roadmap)
- [Contributing](#-contributing)

---

## 🔴 Problem Statement

India has **15 million+ active gig workers** — delivery riders for Swiggy & Zomato, auto drivers, and daily-wage laborers. They face a silent financial crisis:

| The Reality | The Impact |
|-------------|------------|
| 🌧 Heavy rain reduces deliveries by **60–80%** | Zero income on the worst days |
| 🌡 Heatwaves (>42°C) make outdoor work dangerous | Workers ride anyway — or starve |
| 📋 Traditional insurance requires paperwork + claims | Takes weeks; workers can't wait |
| 🚫 Gig workers aren't classified as employees | Fall through every safety net |
| ⚡ When crisis hits, money is needed **today** | No mechanism exists for instant relief |

> **Less than 2% of India's gig workers have any form of income protection.** The market is structurally broken.

---

## ✅ Our Solution

SafeFlow.ai is a **parametric insurance platform** — we pay on *trigger*, not on *claims*.

```
Traditional Insurance:  Event → File Claim → Adjuster Review → Approval → Payout (weeks)
SafeFlow Insurance:     Event → Trigger Fires → Auto-Payout (< 1 second)
```

When a weather event meets our parametric threshold (heavy rain, heatwave, AQI spike), **the payout is instant and automatic** — no paperwork, no calls, no waiting.

---

## ✨ Key Features

### 👷 For Workers
- **One-tap enrollment** — Phone OTP login, GPS-verified, active in 60 seconds
- **Real-time risk dashboard** — Live risk score (1–10), weather conditions, AQI
- **Instant wallet** — Auto-credited on trigger, withdraw via UPI anytime
- **Settlement history** — Full transparency on every payout and trigger
- **Community feed** — Connect with other riders in your city
- **Trust Score** — Builds over time; unlocks faster payouts and higher tiers

### 🏢 For Operations (Admin Portal)
- **Active Investigation Queue** — AI-flagged workers for review
- **Fraud Detection Engine** — Velocity checks, device fingerprinting, location integrity
- **Actuarial Pool Health** — Real-time reserve ratios by city
- **Withdrawal Management** — Approve/reject payout requests with one click
- **Override Commands** — Manual intervention tools for edge cases

### ⚡ Disruption Simulator
- **Test parametric payloads** in any city without real weather events
- **Simulate Heavy Rain, Heatwave, AQI spikes** — validate the full pipeline
- **Intensity calibration** — Test "Moderate" to "Maximum (Immediate Coverage Trig)"
- **Live risk heatmap** — Visual confirmation across India

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SafeFlow.ai Platform                      │
├──────────────┬──────────────────────────┬───────────────────────┤
│  Worker App  │    Operations Portal     │  Disruption Simulator │
│  (React PWA) │    (Admin Dashboard)     │  (Testing Console)    │
└──────┬───────┴────────────┬─────────────┴──────────┬────────────┘
       │                    │                         │
       ▼                    ▼                         ▼
┌──────────────────────────────────────────────────────────────┐
│                     Backend API Layer                         │
│  ┌──────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Firebase    │  │  Parametric     │  │   AI Fraud      │ │
│  │  Auth + DB   │  │  Engine         │  │   Detection     │ │
│  └──────────────┘  └────────┬────────┘  └────────┬────────┘ │
└───────────────────────────────┼──────────────────────────────┘
                                │
       ┌────────────────────────┼─────────────────────────┐
       ▼                        ▼                          ▼
┌─────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Weather    │      │   UPI / Payout   │      │  Actuarial Pool  │
│  APIs       │      │   Automation     │      │  Management      │
│  (IMD/OWM)  │      │   (Instant)      │      │  (City-level)    │
└─────────────┘      └──────────────────┘      └──────────────────┘
```

### Data Flow

```
1. Worker Registers
        │
        ▼
2. GPS Location Verified → Assigned to City Pool
        │
        ▼
3. Real-time Weather Monitor (polling every 5 min)
        │
        ▼
4. Parametric Trigger Evaluation
   ├── Rain > 35mm/hr    → TRIGGER
   ├── Temp > 42°C       → TRIGGER
   ├── AQI > 200         → TRIGGER
   └── Wind > 70 km/h    → TRIGGER
        │
        ▼
5. Fraud Check (AI) → Pass / Flag for Review
        │
        ▼
6. Auto-Credit to Worker Wallet (< 1 sec)
        │
        ▼
7. Settlement logged → Worker notified
```

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML, CSS, JS | Worker dashboard, admin portal |
| **Authentication** | Firebase Auth (Phone OTP) | Zero-friction mobile login |
| **Database** | Firebase Realtime DB / Firestore | Live data sync |
| **Hosting** | Render | Full-stack deployment |
| **Maps** | Leaflet.js + OpenStreetMap | Live risk heatmap |
| **Weather** | OpenWeatherMap API + IMD | Parametric data source |
| **Payments** | UPI Direct Integration | Instant wallet payouts |
| **AI/ML** | Custom fraud scoring engine | Threat detection |
| **Location** | Browser Geolocation API | GPS verification |
| **Charts** | Recharts / D3.js | Actuarial pool visualization |

---

## ⚙️ How It Works

### Parametric Trigger Logic

```javascript
// Simplified trigger evaluation
const evaluateTrigger = (weatherData, policy) => {
  const triggers = {
    heavyRain:  weatherData.rainfall_mm_hr > policy.rain_threshold,     // > 35mm/hr
    heatwave:   weatherData.temperature_c  > policy.heat_threshold,     // > 42°C
    highAQI:    weatherData.aqi            > policy.aqi_threshold,      // > 200
    highWind:   weatherData.wind_kmh       > policy.wind_threshold,     // > 70 km/h
  };

  if (Object.values(triggers).some(Boolean)) {
    return {
      triggered: true,
      payout: calculatePayout(policy.tier, triggers),
      reason: Object.keys(triggers).filter(k => triggers[k])
    };
  }
  return { triggered: false };
};
```

### Trust Score System

```
Trust Score (0–100)
├── 85–100 → Elite Tier: Instant payouts, highest coverage, GPS verified
├── 70–84  → Plus Tier: 30-sec payouts, enhanced coverage
└── 0–69   → Basic Tier: Standard payout, manual review queue
```

### Fraud Detection

The AI engine monitors:
- **Velocity Checks** — Suspicious claim frequency patterns
- **Location Integrity Sync** — GPS spoof detection
- **Device Fingerprinting** — Unique device binding
- **Behavioral Anomalies** — Pattern deviation scoring

---

## 📱 Product Screens

| Screen | Description |
|--------|-------------|
| **Landing Page** | Hero with live simulation demo, Swiggy/Zomato trust badges |
| **Worker Login** | Firebase Phone OTP — no passwords, no friction |
| **Worker Dashboard** | Live risk score, weather config, wallet, settlement history |
| **Admin Operations** | Investigation queue, fraud alerts, pool health, withdrawal approvals |
| **Radar / Simulator** | Risk heatmap, disruption console, payload testing |

---

## 🚀 Getting Started

### Prerequisites

```bash
node >= 18.0.0
npm >= 9.0.0
Firebase project with Phone Auth enabled
```

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/SwaritSingh0017/SafeFlow.ai.git
cd SafeFlow.ai

# 2. Install dependencies
npm install

# 3. Set up environment variables
cp .env.example .env.local
# Edit .env.local with your Firebase and API keys (see below)

# 4. Start the development server
npm run dev
```

### Running in Production

```bash
# Build for production
npm run build

# Start production server
npm start

# Or deploy to Render (recommended)
# Connect your GitHub repo at render.com → New Web Service
```

---

## 🔐 Environment Variables

Create a `.env.local` file in the root directory:

```env
# Firebase Configuration
REACT_APP_FIREBASE_API_KEY=your_firebase_api_key
REACT_APP_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your_project_id
REACT_APP_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
REACT_APP_FIREBASE_APP_ID=your_app_id
REACT_APP_FIREBASE_DATABASE_URL=https://your_project.firebaseio.com

# Weather API
REACT_APP_OPENWEATHER_API_KEY=your_openweather_api_key

# Google Maps / Leaflet (optional, OSM is default)
REACT_APP_MAPS_API_KEY=your_maps_api_key

# Admin Configuration
REACT_APP_ADMIN_SECRET=your_admin_secret_key
```

### Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project
3. Enable **Authentication → Phone** provider
4. Enable **Realtime Database** (set rules for dev)
5. Copy config to `.env.local`

```json
// Firestore Rules (development)
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /workers/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    match /admin/{document=**} {
      allow read, write: if request.auth.token.admin == true;
    }
  }
}
```

---

## 📁 Project Structure

```
SafeFlow.ai/
│
├── backend/                  # FastAPI Server
│   ├── main.py               # Application entry point
│   ├── database.py           # DB connection & models mapping
│   ├── models.py             # SQLAlchemy models
│   ├── security.py           # JWT & Hash logic
│   ├── auth_routes.py        # Login, Reg, OTP endpoints
│   ├── worker_routes.py      # Escrow, Claims, Community APIs
│   ├── payment_routes.py     # Razorpay webhooks & verification
│   ├── admin_routes.py       # Admin controls & dashboards
│   └── safeflow.db           # SQLite DB (local)
│
├── frontend/                 # Vanilla JS / HTML Client
│   ├── assets/               # Video and screenshot mockups
│   ├── css/                  # Styling & Glassmorphism
│   ├── js/                   # UI logic & API fetch layer
│   ├── index.html            # Landing page
│   ├── login.html            # Firebase-auth / OTP login
│   ├── dashboard.html        # Worker escrow dashboard
│   ├── admin.html            # Admin & withdrawal portal
│   └── (other views)
│
├── README.md                 # Project Overview
├── RUN_LOCAL.md              # Local setup guide
├── requirement.txt           # Python dependencies
└── render.yaml               # Deployment configuration
```

---

## 📡 API Reference

### Weather Trigger Endpoint
```
POST /api/trigger/evaluate
Body: { city, workerId, weatherData }
Response: { triggered, payoutAmount, reason, trustScoreImpact }
```

### Wallet Operations
```
GET  /api/wallet/:workerId          → Get balance & history
POST /api/wallet/withdraw           → Request withdrawal
POST /api/wallet/credit             → Admin: credit payout
```

### Admin Operations
```
GET  /api/admin/queue               → Investigation queue
PUT  /api/admin/override/:workerId  → Override fraud flag
GET  /api/admin/pool/:city          → Actuarial pool health
```

### Simulation (Admin Only)
```
POST /api/simulate/disrupt
Body: { city, eventType, intensity }
Response: { workersTriggered, totalPayout, poolImpact }
```

---

## 💰 Business Model

| Revenue Stream | Mechanism | Target |
|---------------|-----------|--------|
| **Worker Premiums** | ₹99–299/month subscription | ₹15L MRR at 10K workers |
| **Platform Licensing** | White-label to Swiggy/Zomato | ₹50L+ enterprise deals |
| **Reinsurance Float** | Pool surplus investments | ~8% annual return |
| **Risk Data** | Anonymized city-level insights | ₹5–20L per data contract |

**Unit Economics:**  
- CAC: < ₹150 | LTV: > ₹3,600 | LTV/CAC: **24x** | Gross Margin: ~68%

---

## 🗺️ Roadmap

```
Q2 2025 ✅  MVP Live — Firebase auth, parametric engine, admin portal
Q3 2025 🔄  IRDAI Sandbox Application — regulatory approval process
Q4 2025 📋  Swiggy/Zomato Pilot — 500 workers, Mumbai + Bhubaneswar
Q1 2026 📋  Series A / Scale — 5 cities, 10,000 workers
Q3 2026 📋  Pan-India Launch — 50 cities, 500,000 workers
2027    📋  Southeast Asia Expansion — Indonesia, Philippines
```

---

## 🤝 Contributing

We welcome contributions! Here's how:

```bash
# Fork the repo, then:
git checkout -b feature/your-feature-name
git commit -m "feat: add your feature"
git push origin feature/your-feature-name
# Open a Pull Request
```

**Areas we'd love help with:**
- New parametric trigger types (flood, cyclone, lightning)
- Multi-language support (Hindi, Odia, Tamil)
- Mobile app (React Native)
- Actuarial model improvements
- IRDAI regulatory compliance tooling

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ for India's gig workers**

*SafeFlow.ai — Protecting the people who keep India moving*

[![Pitch Deck](https://img.shields.io/badge/📊%20Pitch%20Deck-View%20Now-blue?style=for-the-badge)](https://drive.google.com/file/d/1vJPjlD-qaFZ4XF2GCkOd7eH5jp9SVYBc/view?usp=sharing)
[![Live Demo](https://img.shields.io/badge/Try%20Live%20Demo-F57C00?style=for-the-badge)](https://safeflow-ai-ev3w.onrender.com/)

</div>
