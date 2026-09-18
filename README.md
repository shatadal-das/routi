# Routi

AI-powered day trip planner. Combines Google Places API, Google Routes API (TSP route optimization), and Google Gemini (Gemini 3.8 Flash) to curate personalized loop itineraries based on available time, budget, and custom vibe.

---

## Architecture

- **`backend/`**: FastAPI service for place discovery, Gemini curation, duration estimation, and route sequencing.
- **`frontend/`**: React 19 + Vite + Tailwind CSS + Google Maps JavaScript API for interactive map and timeline.

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** & `npm`
- **Google Maps API Key** (Places API New, Routes API, Geocoding API, Maps JavaScript API enabled)
- **Gemini API Key** (Google AI Studio)

---

## Environment Configuration

> Note: `.env` and `venv` are ignored by Git per `.gitignore`. Configure local `.env` files before running.

### 1. Backend (`backend/.env`)
Create `backend/.env` (copy from `backend/.env.example`):
```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Frontend (`frontend/.env`)
Create `frontend/.env` (copy from `frontend/.env.example`):
```env
VITE_GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
# Optional (defaults to http://localhost:8000)
# VITE_API_BASE_URL=http://localhost:8000
```

---

## Getting Started

### 1. Run the Backend

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI dev server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

---

### 2. Run the Frontend

Open a separate terminal:

```bash
cd frontend

# Install packages
npm install

# Start Vite dev server
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## Key Features

- **Trip Vibe Curation**: Natural language vibe input (e.g., *"Relaxed waterfront walk and spicy food, no rushing"*).
- **AI Dwell Time Estimates**: Dynamic visit durations based on venue type and pace.
- **AI Decision Rationale**: Transparent rationale badge for every recommended stop.
- **Google Routes Optimization**: Round-trip loop TSP route with polyline overlay.
- **Native Navigation Export**: One-click export to Google Maps with waypoints for live turn-by-turn directions.
- **Mobile Responsive**: Dual-column desktop layout that stacks smoothly on mobile.
