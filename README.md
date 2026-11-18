# DYPCOE Smart Campus Navigator — Quick Start

## Prerequisites
- PostgreSQL running with `dypcoe_campus` database (already seeded ✅)
- Python 3.11+ with venv set up (already done ✅)
- Node.js 18+

---

## Run the App

### 1. Start Backend (Terminal 1)
```powershell
cd C:\Users\VAIBHAV\.gemini\antigravity\scratch\dypcoe-campus-navigator\backend
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```
Backend runs at: http://localhost:8000  
API Docs: http://localhost:8000/api/docs

### 2. Start Frontend (Terminal 2)
```powershell
cd C:\Users\VAIBHAV\.gemini\antigravity\scratch\dypcoe-campus-navigator\frontend
npm run dev
```
App runs at: **http://localhost:5173**

---

## Admin Dashboard
- URL: http://localhost:5173/admin/login
- Email: `admin@dypcoe.ac.in`
- Password: `dypcoe@2024`

---

## Add a Google Maps API Key (optional but recommended)
1. Get a key at https://console.cloud.google.com/
2. Enable: **Maps JavaScript API** + **Routes API** + **Places API**
3. Edit `frontend/.env`:
   ```
   VITE_GOOGLE_MAPS_API_KEY=YOUR_KEY_HERE
   VITE_GOOGLE_MAPS_MAP_ID=YOUR_MAP_ID
   ```
4. Restart the frontend dev server.

> **Without a key:** The app shows a beautiful schematic SVG campus map (fallback mode). Full Google Maps satellite/street view loads only with a key.

---

## API Endpoints (v1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/locations` | List all campus locations |
| GET | `/api/v1/locations/categories` | List categories |
| GET | `/api/v1/locations/{id}` | Get one location |
| POST | `/api/v1/directions` | Get route between two locations |
| POST | `/api/v1/chat` | AI campus assistant |
| POST | `/api/v1/auth/login` | Admin login → JWT token |
| GET | `/api/v1/admin/stats/overview` | Dashboard stats (admin) |
| POST | `/api/v1/locations` | Create location (admin) |
| PATCH | `/api/v1/locations/{id}` | Update location (admin) |
| DELETE | `/api/v1/locations/{id}` | Delete location (admin) |

---

## Tech Stack
- **Frontend:** React 18 (JSX), Vite 5, Tailwind CSS 3, Framer Motion, Google Maps JS API
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, psycopg2
- **Campus:** DYPCOE – Dr. D.Y. Patil College of Engineering, Akurdi, Pune
- **Coordinates:** 18.6448°N, 73.7582°E
