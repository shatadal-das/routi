# Routi 🗺️⚡

> **AI-Powered Day Trip Planner & Algorithmic Route Optimization Engine**  
> Combines Google Places API (New), Google Routes API (TSP optimization), and Gemini AI to create realistic, perfectly-timed round-trip day itineraries with guaranteed return loop, hard time budget enforcement, dynamic dwell times, and meal window scheduling.

---

### Quick Links
- 🚀 [Live Demo](https://frontend.d1cq4yp88o5lol.amplifyapp.com)
- 🌐 [Frontend Branch](https://github.com/shatadal-das/routi/tree/frontend)
- ⚙️ [Backend Branch](https://github.com/shatadal-das/routi/tree/backend)

---

## ⚡ Core Features

- **⏱️ Hard Time Budget & Loop Closure**: Solves the Orienteering Problem (OP) with strict return-to-origin transit reservations. Never overshoots available time.
- **🔄 2-Opt Local Search TSP**: Untangles route crossings and minimizes driving/walking times.
- **🛡️ Dynamic Safety Buffering**: Calculates 10–30 min travel and dwell buffers to prevent schedule overruns.
- **🍽️ Smart Meal Scheduling**: Automatically slots lunch (12:00–2:30 PM) or dinner (6:30–9:30 PM) at top-rated dining spots, styled distinctly in timeline and map.
- **📊 Bayesian Quality & Diversity Scoring**: Filters low-confidence places; applies exponential diminishing returns to prevent duplicate categories.
- **🗺️ Interactive Map Canvas**: Custom brand-styled map, SVG marker pins with high-contrast white halo strokes, decoded polyline path, and instant reset on departure location updates.
- **📍 Real-Time Autocomplete**: Debounced place & address suggestions via Google Places API (New).
- **📲 One-Click Google Maps Export**: Launches multi-stop GPS turn-by-turn navigation in native Google Maps.

---

## 🏗️ Architecture

```
[ User Browser / Client ]
           │
           ▼
[ React 19 Frontend (Vite + Tailwind CSS) ]
  • SearchForm.jsx: Origin autocomplete, duration, vibe, transport mode
  • Timeline.jsx: Chronological timetable, dwell times, meal badges, AI rationale
  • Map.jsx: Custom Google Maps canvas, SVG pins, decoded route polylines
           │
           │ REST JSON
           ▼
[ FastAPI Backend (Python 3.12 + Uvicorn) ]
  • main.py: API gateway, validation, CORS
  • services/optimizer.py: Orienteering Problem solver, greedy insertion, 2-Opt TSP
  • services/scorer.py & taxonomy.py: Bayesian smoothing, category rules, iconic landmarks
  • services/places.py & geocoding.py: Google Places API (New) candidate search & text search
  • services/routing.py: Google Routes API (computeRoutes) & polyline generator
  • services/agent.py & ai_curator.py: Gemini AI narrative & conversational concierge
```

---

## 📁 Repository Structure

```
Routi/
├── backend/
│   ├── main.py                  # FastAPI app & endpoint handlers
│   ├── requirements.txt         # Python dependencies
│   ├── Dockerfile               # Production container definition
│   └── services/
│       ├── optimizer.py         # Deterministic OP solver & 2-Opt TSP engine
│       ├── scorer.py            # Bayesian rating & diversity penalty algorithms
│       ├── taxonomy.py          # Category classifications & dwell duration rules
│       ├── places.py            # Google Places API (New) candidate search
│       ├── routing.py           # Google Routes API TSP sequence & encoded polyline
│       ├── geocoding.py         # Address geocoding & autocomplete suggestions
│       ├── agent.py             # RoamAroundAgent conversational re-planning
│       ├── ai_curator.py        # Gemini itinerary narrative generator
│       ├── time_manager.py      # Timeline slot budgeting
│       └── tools.py             # Agent tools for search, routing & optimization
│
├── frontend/
│   ├── package.json             # React 19, @react-google-maps/api, lucide-react
│   ├── vite.config.js           # Vite build configuration
│   ├── tailwind.config.js       # Brand color palette tokens
│   └── src/
│       ├── App.jsx              # Main layout, script loader & state coordinator
│       ├── components/
│       │   ├── SearchForm.jsx   # Input form with live autocomplete & filters
│       │   ├── Timeline.jsx     # Chronological timetable with food indicators
│       │   └── Map.jsx          # Custom styled Google Map with SVG pins
│       └── utils/
│           └── polyline.js      # Polyline decoding helper
│
├── Dockerfile                   # Root container deployment file
├── WALKTHROUGH.md               # Detailed engineering documentation
└── README.md                    # Project documentation
```

---

## ⚙️ Environment Variables

### Backend (`backend/.env`)
```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
GEMINI_API_KEY=your_gemini_api_key
# Optional AWS Bedrock / OpenAI compatible endpoint:
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_endpoint_url
```

### Frontend (`frontend/.env`)
```env
VITE_GOOGLE_MAPS_API_KEY=your_google_maps_api_key
VITE_API_BASE_URL=http://localhost:8000
```

---

## 🚀 Getting Started

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```
- Web App: `http://localhost:5173`

### 3. Docker

```bash
docker build -t routi-backend ./backend
docker run -p 8000:80 --env-file backend/.env routi-backend
```

---

## 📡 API Contract

### `POST /api/plan-trip`

#### Request
```json
{
  "start_location": {
    "lat": 37.7749,
    "lng": -122.4194,
    "address": "San Francisco, CA"
  },
  "available_time_minutes": 270,
  "start_time": "09:30 AM",
  "transport_mode": "DRIVE",
  "interests": ["Scenic Viewpoints", "Art & Architecture"],
  "price_level": "$$"
}
```

#### Response
```json
{
  "success": true,
  "trip": {
    "total_duration_mins": 255,
    "total_travel_mins": 45,
    "total_dwell_mins": 190,
    "safety_buffer_mins": 20,
    "start_clock": "09:30 AM",
    "end_clock": "01:45 PM",
    "return_to_start": true
  },
  "optimized_places": [
    {
      "name": "Coit Tower",
      "lat": 37.8024,
      "lng": -122.4058,
      "arrival_time": "09:45 AM",
      "departure_time": "10:35 AM",
      "duration_mins": 50,
      "category": "viewpoint",
      "is_meal_stop": false,
      "selection_reasons": ["Top Rated (4.6★)", "Scenic View"],
      "ai_reasoning": "Iconic panoramic views over SF Bay."
    }
  ],
  "polyline": "encoded_polyline...",
  "google_maps_url": "https://www.google.com/maps/dir/?api=1...",
  "rejected_destinations": []
}
```

---

## 📄 License
MIT