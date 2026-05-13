<div align="center">

  <h1>🛡️ ConsentFlow</h1>

  ### AI-Powered Privacy & Automated Cookie Consent Management Platform

  <p align="center">
    Take complete control of your online privacy. ConsentFlow automatically detects, analyzes, and manages cookie consent banners across the web using browser extensions, AI policy summaries, and automated consent preferences.
  </p>

  <p align="center">
    <a href="#-key-features"><strong>Key Features »</strong></a>
    &nbsp;•&nbsp;
    <a href="#%EF%B8%8F-tech-stack--architecture"><strong>Tech Stack</strong></a>
    &nbsp;•&nbsp;
    <a href="#-architecture-overview"><strong>Architecture</strong></a>
    &nbsp;•&nbsp;
    <a href="#-quick-start-guide"><strong>Quick Start</strong></a>
  </p>

  <br />

  <!-- Badges -->
  <img src="https://img.shields.io/badge/Chrome_Extension-Manifest_V3-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Manifest V3" />
  <img src="https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/Node.js-Express-339933?style=for-the-badge&logo=nodedotjs&logoColor=white" alt="Node.js" />
  <img src="https://img.shields.io/badge/MongoDB-Database-47A248?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB" />
  <img src="https://img.shields.io/badge/Gemini-AI_Analysis-8E75B2?style=for-the-badge&logo=google&logoColor=white" alt="Gemini AI" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-v4-38BDF8?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS" />

</div>

---

## 🌟 Key Features

<div align="center">
<table>
  <tr>
    <td width="50%">
      <h3 align="center">🧩 Auto-Consent Extension</h3>
      <p>Manifest V3 browser extension automatically rejecting non-essential cookies and handling complex CMP banner overlays in real time.</p>
    </td>
    <td width="50%">
      <h3 align="center">🤖 AI Privacy Policy Analyzer</h3>
      <p>Google Gemini AI generates concise risk scores ($A$ through $F$) and flags hidden data-sharing clauses before you accept terms.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3 align="center">📊 Real-Time Tracker Dashboard</h3>
      <p>Interactive web dashboard tracking third-party scripts, ad trackers, and cookie preference history across visited web domains.</p>
    </td>
    <td width="50%">
      <h3 align="center">⚡ Custom Whitelist & Rules</h3>
      <p>Define custom domain rules, emergency whitelist controls, and automated GDPR/CCPA preference templates with one click.</p>
    </td>
  </tr>
</table>
</div>

---

## 🛠️ Tech Stack & Architecture

| Component | Technology | Description |
|---|---|---|
| **Browser Extension** | Chrome Extensions API (Manifest V3) | Content scripts, service workers, Shadow DOM overlays |
| **Web Dashboard** | [Next.js 15](https://nextjs.org/) + React 19 | Responsive admin & user privacy audit portal |
| **Backend API** | Node.js + Express.js | REST API services, rate-limiting, authentication |
| **AI Processing** | Google Gemini 2.5 API | Privacy policy NLP parser & risk rating generator |
| **Database** | MongoDB + Mongoose ORM | Tracker logs, user preferences, domain analytics |
| **Styling** | Tailwind CSS v4 + Radix UI Primitives | Modern dark mode interface with glassmorphism |

---

## 📂 Architecture Overview

```bash
ConsentFlow/
├── consentflow-extension/    # Manifest V3 Chrome Extension source
│   ├── manifest.json         # Extension permissions & entry points
│   ├── content-scripts/      # DOM banner detectors & CMP handlers
│   ├── background/           # Service worker & storage sync
│   └── popup/                # Extension popup UI component
├── consentflow-frontend/     # Next.js web dashboard
│   ├── src/app/              # Dashboard pages & route handlers
│   └── components/           # Analytics charts, domain tables
├── consentflow-backend/      # Express API server
│   ├── controllers/          # API route controllers
│   ├── models/               # MongoDB Mongoose data models
│   └── services/             # Gemini AI policy parser & scraper
└── docs/                     # API specs, setup guides, diagrams
```

---

## 🚀 Quick Start Guide

### 1. Extension Setup (Browser)
1. Open Chrome and navigate to `chrome://extensions`.
2. Enable **Developer Mode** in the top right.
3. Click **Load unpacked** and select the `consentflow-extension` folder.

### 2. Dashboard & Backend Setup
```bash
# Clone repository
git clone https://github.com/Rishu7011/ConsentFlow.git
cd ConsentFlow

# Start backend
cd consentflow-backend
npm install
npm run dev

# Start web dashboard (new terminal)
cd ../consentflow-frontend
npm install
npm run dev
```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.

<div align="center">
  <sub>Safeguarding digital privacy, one cookie banner at a time.</sub>
</div>
