# 📞 IVR Simulator — FastAPI + HTML Frontend

> **Interactive Voice Response (IVR) System Simulator**  
> Built with **FastAPI**, **SQLAlchemy**, and a realistic **HTML frontend** that simulates DTMF keypresses, speech recognition, and text-to-speech for a lifelike airline call experience.

---

## 🧩 Project Overview

This project simulates an **Air India-style IVR system** with:
- A backend (`FastAPI`) handling call logic, state management, and database storage.
- A frontend (`HTML + JS`) emulating a smartphone UI to interact with the backend.
- Persistent call states stored in the database (`SQLite` or `PostgreSQL`).

It demonstrates **end-to-end integration** between speech, API processing, and database-backed menu flow.

---

## 📂 Files in this Repository

| File | Description |
|------|--------------|
| `ivr_simulator_backend.py` | FastAPI backend app with all IVR logic and database handling |
| `database.py` | SQLAlchemy models, database setup, and session dependency |
| `ivr_simulator.html` | Frontend simulator with keypad, microphone, and live call interface |
| `requirements.txt` | Python dependencies for backend deployment |

---

## ✨ Features

✅ Persistent call state saved in the database (multi-worker safe)  
✅ Realistic IVR menu navigation via DTMF and speech input  
✅ Automatic seeding of mock booking (PNR) and frequent flyer data  
✅ Fully functional Text-to-Speech (TTS) and Speech-to-Text (STT) via browser APIs  
✅ SQLite (local) and PostgreSQL (production) compatible  
✅ Deployed and accessible via Render.com  

---

## 🧠 Prerequisites

- Python **3.10+**
- Modern browser (Chrome recommended for best TTS/STT support)
- Optional: PostgreSQL database for production

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|-----------|--------------|----------|
| `DATABASE_URL` | SQLAlchemy connection string (`postgresql://` or `sqlite:///`) | `sqlite:///./ivr.db` |

> The backend automatically converts `postgres://` → `postgresql://` for compatibility with psycopg2.

---

## 📦 Installation

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate     # macOS/Linux
.venv\Scripts\activate        # Windows

# 2. Install dependencies
pip install -r requirements.txt
```

## 🗃️ Database & Data Seeding

When the server starts, it will:

- Automatically create the tables (`Booking`, `FrequentFlyer`, `CallHistory`)
- Preload mock booking and frequent flyer data

---

### 🧱 Database Schema Includes

- **Booking** → Passenger & flight details (PNR)
- **FrequentFlyer** → Frequent flyer numbers, PINs, and points
- **CallHistory** → Call state (menus, input buffers, timestamps, etc.)

---

## 🚀 Run Locally

### Start the backend

```bash
uvicorn ivr_simulator_backend:app --reload --host 0.0.0.0 --port 8000
```

By default, it uses: `sqlite:///./ivr.db`.

---

### 🖥️ Open the Frontend

1. Open `ivr_simulator.html` in your browser.  
2. Update the API base URL (optional) inside the script if you’re running locally:

   ```js
   const API_BASE_URL = 'http://localhost:8000';
   ```
3.Press the green button to start a simulated call 🎧

---
## 🧭 API Endpoints Overview

| Method | Endpoint             | Description                         |
|--------|----------------------|-------------------------------------|
| `GET`  | `/`                  | Health check + DB info              |
| `POST` | `/ivr/start`         | Start a new IVR session             |
| `POST` | `/ivr/dtmf`          | Handle keypad digit input           |
| `POST` | `/ivr/process_voice` | Handle voice (speech-to-text) input |
| `POST` | `/ivr/end`           | End or hang up a call               |

---

## 🖥️ Frontend (ivr_simulator.html)

A modern, smartphone-style simulator featuring:

- DTMF keypad with **0–9**, `*`, and `#`
- **Start** (green), **Speak** (blue), and **Hangup** (red) buttons
- IVR conversation bubbles with realistic **speech synthesis (TTS)**
- Integrated **browser microphone** support for speech commands

---

### 🎮 Quick Demo Actions

| Action | Command |
|--------|----------|
| Flight Status | Press `1` |
| Manage Booking | Press `2` |
| Book Flight | Say “Book Flight” |
| Connect to Agent | Say “Agent” |

---
## 🧪 Example (Using cURL)

```bash
# Start call
curl -X POST http://localhost:8000/ivr/start \
  -H "Content-Type: application/json" \
  -d '{"caller_number":"+911234567890"}'

# Send DTMF
curl -X POST http://localhost:8000/ivr/dtmf \
  -H "Content-Type: application/json" \
  -d '{"call_id":"CALL_123456","digit":"1","current_menu":"main"}'

# Send voice input
curl -X POST http://localhost:8000/ivr/process_voice \
  -H "Content-Type: application/json" \
  -d '{"call_id":"CALL_123456","text":"flight status","current_menu":"main"}'

# End call
curl -X POST http://localhost:8000/ivr/end \
  -H "Content-Type: application/json" \
  -d '{"call_id":"CALL_123456"}'
```
## 🌐 Live Deployment (Render)

This project is deployed on **Render.com** for live testing.

---

### 🔗 Live URLs

- **Backend (FastAPI)** → [https://ivr-fastapi-simulator.onrender.com](https://ivr-fastapi-simulator.onrender.com)  
- **Frontend (HTML)** → Open `ivr_simulator.html` locally  
  > It already connects to the live API above.

---

## 🧰 Render Setup

1. **Create a new Web Service** on [Render](https://render.com)  
2. **Connect this GitHub repository**  
3. **Set the Start Command:**

   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker ivr_simulator_backend:app
   ```
4.**Add environment variable**

   ```bash
   DATABASE_URL=sqlite:///./ivr.db
   ```
5.**Or use your PostgreSQL URL:**

   ```bash
   DATABASE_URL=postgresql://user:password@host:port/dbname
   ```
Render will automatically build, deploy, and expose your app at:

  ```bash
   https://<your-app-name>.onrender.com
   ```
---

## ⚠️ Troubleshooting

| Issue | Possible Cause | Solution |
|--------|----------------|-----------|
| **TTS/STT not working** | Browser doesn’t support speech APIs | Use Chrome or Edge and allow microphone access |
| **“Call not found” error** | Wrong `API_BASE_URL` or expired session | Make sure frontend `API_BASE_URL` matches backend host |
| **Postgres connection error** | Invalid or missing `DATABASE_URL` | Ensure `DATABASE_URL` is correctly set — note that Render uses `postgres://`, which is automatically fixed to `postgresql://` |

---

## 🧑‍💻 Contributing

Contributions are welcome!  
You can help improve the project by:

- Extending IVR flows in `MENU_STRUCTURE`
- Adding new menus or DB-backed features
- Updating documentation or improving frontend visuals

---

## 🪪 License

This project is provided for **educational and demonstration** purposes.  
You are free to **use**, **modify**, and **deploy** it for learning or non-commercial use.

---

## 💬 Author

**Developed by [Saranya Muthuraj](#)**  
> IVR Simulation using **FastAPI + SQLAlchemy + HTML Speech API**
