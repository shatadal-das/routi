# Routi 🗺️✨

> **Personalized Day Trip Planner & Algorithmic Route Optimization Engine**  
> Combines Google Places API (New), Google Routes API (TSP optimization), and Google Gemini to deliver personalized, perfectly-timed round-trip day itineraries based on time budget, travel mode, budget tiers, and custom vibes.

---

## 🌟 Overview

Planning a day trip usually requires juggling maps, opening hours, travel distances, meal timing, and venue quality. **Routi** solves this by unifying **deterministic combinatorial optimization** with **conversational AI intelligence**:

1. **Deterministic Route Optimizer**: Formulates and solves the Orienteering Problem with Time Windows (OPTW) using Seeded Greedy Insertion, Marginal Value candidate evaluation, and a 2-Opt Local Search TSP solver. It strictly honors hard constraints (time budgets, round-trip loop closure, category quotas, dynamic safety buffers, realistic dwell times, and deterministic meal windows).
2. **Dynamic Duration Scaling**: Seamlessly adapts itineraries across short and long trip horizons (2h, 4h, 6h, 8h, 12h) by evaluating candidates based on marginal value rather than simple greedy packing.
3. **Deterministic Meal Windows**: Enforces strict meal windows based on actual arrival times: Breakfast (`07:00–10:30`), Lunch (`11:30–15:00`), and Dinner (`18:00–21:30`). A stop at 16:00 is never mislabeled as lunch.
4. **Explicit Destination Locking**: When users request a specific place by name (e.g. *"I want to go to India Gate"*), the venue is resolved, locked (`is_locked = True`), and prioritized without displacement.
5. **Dual Category Modes**: Explicit category selections restrict recommendations to chosen interests; an empty selection represents "no preference", enabling broad discovery across top attractions, monuments, parks, and meal-window dining.
6. **Interactive Trip Concierge**: Floating concierge drawer (`/api/agent/chat`) allowing users to iteratively modify itineraries via natural language (e.g. *"add a scenic cafe stop"*, *"remove the restaurant"*, *"make the trip more relaxed"*).
7. **Google Maps Navigation Export**: Generates a one-click native Google Maps URL with sequential waypoints for turn-by-turn mobile navigation.

---

## 🚀 Key Features

- **⏱️ Hard Time Budget & Round-Trip Loop Guarantees**: Guaranteed return to your starting point within your specified time limit, with return transit time strictly reserved during every step.
- **🍽️ Deterministic Meal Scheduling**: Hard constraints for Breakfast (`07:00–10:30`), Lunch (`11:30–15:00`), and Dinner (`18:00–21:30`). Meal types are calculated strictly from arrival clock time. Out-of-window food stops are skipped or scheduled as refreshments without invalid meal labels.
- **🔒 Direct Destination Constraints**: Named destination requests are locked and seeded with priority in the optimizer.
- **🎯 Dynamic Marginal Value Optimization**: Evaluates candidates by marginal value ($Q + P + L + D - \Delta\text{Travel} - \Delta\text{Time}$) to prevent premature stopping or low-value padding on 8–12 hour trips.
- **🛡️ Dynamic Safety Buffering**: Automatically calculates transit and dwell safety buffers based on stop count and travel mode (Drive, Walk, Bicycle) to prevent tight schedules.
- **🧠 Bayesian-Smoothed Quality Scoring**: Filters out low-confidence places and balances Google ratings, review counts, user interest matching, and category diversity.
- **💬 Interactive Trip Concierge**: Floating chat assistant with quick-action shortcuts and natural language re-planning.
- **🗺️ Interactive Dark Mode Map**: Custom Google Maps styling, numbered route pins, arrival/departure markers, interactive InfoWindows, and polyline route visualization.
- **📱 Clean Production UI**: Focused, distraction-free interface with product-centered copy and streamlined timeline schedules.

---

## 🏗️ System Architecture

```
                                  ┌────────────────────────┐
                                  │   React 19 Frontend    │
                                  │ (Vite + Tailwind CSS)  │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                 ┌──────────────────────────┐
                                 │   FastAPI Backend API    │
                                 └──────┬────────────┬──────┘
                                        │            │
             ┌──────────────────────────┘            └─────────────────────────┐
             ▼                                                                 ▼
┌─────────────────────────┐                                       ┌─────────────────────────┐
│  Optimization Engine    │                                       │   Gemini AI Concierge   │
├─────────────────────────┤                                       ├─────────────────────────┤
│ • Candidate Scoring     │                                       │ • RoamAroundAgent       │
│ • Category Diversity    │                                       │ • Natural Language Chat │
│ • Orienteering Heuristic│                                       │ • Contextual Narratives │
│ • 2-Opt TSP Optimizer   │                                       │ • Interactive Re-plan   │
│ • Meal Window Scheduler │                                       └────────────┬────────────┘
│ • Safety Buffer Logic   │                                                    │
└────────────┬────────────┘                                                    │
             │                                                                 │
             └──────────────────────────┬──────────────────────────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │      External Services      │
                         ├─────────────────────────────┤
                         │ • Google Places API (New)   │
                         │ • Google Routes API (TSP)   │
                         │ • Google Geocoding API      │
                         │ • Google Maps JavaScript API│
                         │ • Google Gemini AI Studio   │
                         └─────────────────────────────┘
```

---

## 📁 Project Structure

```
Routi/
├── backend/
│   ├── main.py                  # FastAPI entry point & API route handlers
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Template for backend environment variables
│   └── services/
│       ├── agent.py             # Gemini conversational concierge & re-planning agent
│       ├── ai_curator.py        # Gemini itinerary narrative and fallback curator
│       ├── geocoding.py         # Google Geocoding & place suggestions
│       ├── itinerary_generator.py # User-facing timetable & itinerary builder
│       ├── optimizer.py         # Deterministic Orienteering & 2-Opt TSP engine
│       ├── places.py            # Google Places API (New) integration & candidate search
│       ├── routing.py           # Google Routes API (computeRoutes, polylines, directions URL)
│       ├── scorer.py            # Multi-factor place scoring & diversity penalties
│       ├── taxonomy.py          # Category classifications, iconic landmarks, dwell rules
│       ├── time_manager.py      # Timetable slots, travel leg pacing, activity budgets
│       └── tools.py             # Agent tools for place search, routing, and optimization
│
├── frontend/
│   ├── index.html               # Web entry point
│   ├── package.json             # Frontend dependencies & scripts
│   ├── vite.config.js           # Vite build configuration
│   ├── tailwind.config.js       # Tailwind CSS configuration
│   ├── .env.example             # Template for frontend environment variables
│   └── src/
│       ├── App.jsx              # Main layout and application state coordinator
│       ├── main.jsx             # React DOM entry
│       ├── index.css            # Tailwind directives & global styling
│       ├── components/
│       │   ├── AgentChat.jsx    # Floating AI Concierge conversational chat drawer
│       │   ├── Map.jsx          # Google Map component (dark theme, markers, polylines)
│       │   ├── SearchForm.jsx   # Trip configuration form (time, vibe, transport, location)
│       │   └── Timeline.jsx     # Chronological itinerary view with explainability badges
│       └── utils/
│           └── polyline.js      # Encoded polyline decoder for route visualization
│
└── README.md                    # Project documentation
```

---

## 🛠️ Prerequisites

Before running Routi locally, ensure you have:

- **Python 3.10+**
- **Node.js 18+** & **npm**
- **Google Cloud API Key** with the following APIs enabled:
  - Places API (New)
  - Routes API
  - Geocoding API
  - Maps JavaScript API
- **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/))

---

## ⚙️ Environment Configuration

### 1. Backend (`backend/.env`)

Create a `.env` file in the `backend/` directory (you can copy `backend/.env.example`):

```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
OPENAI_API_KEY=your_aws_bedrock_api_key_here
OPENAI_BASE_URL=https://bedrock-runtime.../v1
```

| Variable | Description |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Maps API key with Places, Routes, and Geocoding enabled. |
| `OPENAI_API_KEY` | API key for AWS Bedrock OpenAI-compatible endpoint. |
| `OPENAI_BASE_URL` | AWS Bedrock endpoint URL (for `google.gemma-3-27b-it` model). |


### 2. Frontend (`frontend/.env`)

Create a `.env` file in the `frontend/` directory (you can copy `frontend/.env.example`):

```env
VITE_GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
VITE_API_BASE_URL=http://localhost:8000
```

| Variable | Description |
|---|---|
| `VITE_GOOGLE_MAPS_API_KEY` | Google Maps API key for the interactive Maps JavaScript API. |
| `VITE_API_BASE_URL` | Base URL of the running FastAPI backend (defaults to `http://localhost:8000`). |

---

## 🏃 Getting Started

### 1. Start the Backend

Open a terminal and navigate to `backend/`:

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Launch FastAPI development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **Backend API**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/health`

---

### 2. Start the Frontend

Open a second terminal and navigate to `frontend/`:

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

- **Application URL**: `http://localhost:5173`

---

## 📡 API Reference

### 1. `POST /api/plan-trip` (or `/api/generate-route`)

Generates a fully optimized, round-trip day itinerary.

**Request Body (`application/json`):**

```json
{
  "start_location": {
    "lat": 28.6139,
    "lng": 77.2090,
    "address": "Connaught Place, New Delhi"
  },
  "available_time_minutes": 300,
  "start_time": "09:30 AM",
  "transport_mode": "DRIVE",
  "interests": ["Historic Landmarks", "Local Cuisine", "Photography"],
  "price_level": "$$"
}
```

**Key Response Fields:**

- `trip`: Contract object containing `stops`, `timetable`, `distance_km`, `total_duration_mins`.
- `optimized_places`: Ordered list of stops with:
  - `arrival_time`, `departure_time`, `duration_mins`
  - `selection_reasons`: Array of tags explaining why the venue was picked.
  - `ai_reasoning`: Contextual rationale for the stop.
  - `time_estimate_reason`: Explanation of the allotted dwell time.
- `polyline`: Encoded overview polyline for map drawing.
- `google_maps_url`: One-click native navigation URL.
- `rejected_destinations`: List of evaluated candidate places with reasons for exclusion.
- `safety_buffer_minutes`: Allotted travel/buffer slack.

---

### 2. `POST /api/agent/chat`

Conversational endpoint for the AI concierge. Allows iterative adjustments to the generated itinerary.

**Request Body (`application/json`):**

```json
{
  "message": "Can you swap the restaurant for a casual cafe and make the day a bit more relaxed?",
  "conversation_history": [],
  "current_itinerary": { ... },
  "start_location": { "lat": 28.6139, "lng": 77.2090 }
}
```

**Response:** Returns an updated itinerary with recomputed schedules, polylines, and a conversational explanation of applied modifications.

---

### 3. `GET /api/places/autocomplete`

Provides debounced autocomplete suggestions for place names, landmarks, and addresses.

**Query Parameters:**
- `query` (string, required, min length 2): Search string.

---

### 4. `GET /api/health`

Verifies backend status and API key configuration health.

```json
{
  "status": "ok",
  "message": "Backend is running",
  "google_maps_configured": true,
  "gemini_configured": true
}
```

---

## 🔬 How the Optimization Engine Works

```
[User Preferences & Origin]
           │
           ▼
[Google Places Search] ──► 50+ Candidate Places
           │
           ▼
[Bayesian & Diversity Scoring] ──► Quality + Category Penalty + Proximity
           │
           ▼
[Greedy Insertion with Loop Reservation] ──► Enforces Hard Time Budget & Loop Closure
           │
           ▼
[2-Opt TSP Local Search] ──► Untangles Route Crossings & Minimizes Transit
           │
           ▼
[Meal Scheduler & Dwell Estimation] ──► Slots Lunch/Dinner & Computes Accurate Times
           │
           ▼
[Safety Buffer & Timetable Generation] ──► Final Itinerary + Polylines + Explainability
```

1. **Candidate Discovery**: Fetches diverse candidate venues across sightseeing, culture, nature, viewpoints, and dining within a realistic geographic radius using Google Places API (New).
2. **Bayesian-Smoothed Ranking**: Evaluates candidates using a multi-objective scoring formula:
   $$\text{Score} = w_r \cdot \text{BayesianRating} + w_v \cdot \text{VibeMatch} + w_p \cdot \text{Proximity} - \text{CategoryPenalty}$$
3. **Marginal Value Greedy Insertion**: Iteratively adds candidate stops that maximize marginal value:
   $$\text{MarginalValue} = \text{Quality} + \text{VibeMatch} + \text{LandmarkScore} + \text{Diversity} + \text{ItineraryValue} - \Delta\text{Travel} - \Delta\text{Time}$$
   Ensures return transit to the starting point remains strictly within the time limit.
4. **2-Opt TSP Sequence Optimization**: Re-sequences stops to eliminate self-intersecting route legs, minimizing total driving/walking time while respecting locked destination constraints.
5. **Deterministic Meal Window Constraints**:
   - **Breakfast**: `07:00 – 10:30` (ideal: `08:00 – 09:30`)
   - **Lunch**: `11:30 – 15:00` (ideal: `12:15 – 01:30`)
   - **Dinner**: `18:00 – 21:30` (ideal: `19:00 – 08:30`)
   - Meal types are derived deterministically from the venue's actual arrival clock time. Food stops reached outside these windows (e.g. 16:00) receive `meal_type = None` and are never mislabeled. Dedicated restaurants that cannot fit a valid meal window are skipped rather than scheduled at invalid times.
6. **Safety Buffer**: Adds dynamic transit and dwell buffers (10–45 mins) based on route complexity and transport mode to safeguard against real-world delays.

---

## 🤝 Contributing & Development

1. Ensure code style is consistent.
2. Verify frontend builds cleanly:
   ```bash
   cd frontend
   npm run build
   ```
3. Test backend changes with FastAPI's auto-reload:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

---