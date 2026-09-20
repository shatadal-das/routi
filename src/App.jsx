import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useJsApiLoader } from '@react-google-maps/api';
import SearchForm from './components/SearchForm';
import Map from './components/Map';
import Timeline from './components/Timeline';
import AgentChat from './components/AgentChat';

const GOOGLE_MAPS_LIBRARIES = [];
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const LOADING_MESSAGES = [
  {
    title: 'Scanning nearby spots...',
    subtitle: 'Discovering top-rated attractions, parks, and dining spots nearby',
  },
  {
    title: 'AI is curating your vibe...',
    subtitle: 'Gemma 3 27B matching venues with your custom trip atmosphere',
  },
  {
    title: 'Estimating realistic dwell times...',
    subtitle: 'Calculating dynamic time allocations for each stop',
  },
  {
    title: 'Optimizing the driving route...',
    subtitle: 'Sequencing waypoints to minimize travel time and traffic',
  },
];

function LoadingCard() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 2200);
    return () => clearInterval(interval);
  }, []);

  const msg = LOADING_MESSAGES[index];

  return (
    <div className="p-4 sm:p-5 rounded-3xl bg-white border border-brand-teal/30 flex items-center space-x-3.5 shadow-xl transition-all duration-300">
      <div className="w-5 h-5 border-2 border-brand-teal border-t-transparent rounded-full animate-spin shrink-0"></div>
      <div className="text-xs min-w-0">
        <p className="font-bold text-brand-navy text-sm transition-all duration-300">
          {msg.title}
        </p>
        <p className="text-brand-navy/70 mt-0.5 font-medium transition-all duration-300">
          {msg.subtitle}
        </p>
      </div>
    </div>
  );
}

function App() {
  const [backendHealth, setBackendHealth] = useState({ status: 'loading', message: 'Checking API...' });
  const [startLocation, setStartLocation] = useState({
    lat: 37.7749,
    lng: -122.4194,
    address: 'San Francisco, CA',
  });
  const [routeResult, setRouteResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Single shared Google Maps API loader for the application
  const { isLoaded, loadError } = useJsApiLoader({
    id: 'routi-google-map-script',
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '',
    libraries: GOOGLE_MAPS_LIBRARIES,
  });

  useEffect(() => {
    axios.get(`${API_BASE_URL}/api/health`)
      .then((res) => {
        setBackendHealth({ status: 'connected', message: res.data.message });
      })
      .catch(() => {
        setBackendHealth({ status: 'error', message: 'Backend unreachable' });
      });
  }, []);

  const handleLocationChange = useCallback((loc) => {
    if (loc) {
      setStartLocation(loc);
    }
    // Clear any previous error and reset previous route when location updates
    setErrorMessage(null);
    setRouteResult(null);
  }, []);

  const handleGenerateRoute = useCallback(async (formData) => {
    setIsLoading(true);
    setErrorMessage(null);
    setRouteResult(null);

    const {
      start_location,
      lat,
      lng,
      hours,
      available_time_minutes,
      address,
      transport_mode,
      interests,
      vibe,
      vibe_preference,
      price_level,
      start_time,
    } = formData;

    setStartLocation({ lat, lng, address });

    try {
      const response = await axios.post(`${API_BASE_URL}/api/plan-trip`, {
        start_location: start_location || { lat, lng, address },
        start_lat: lat,
        start_lng: lng,
        address: address,
        start_time: start_time || '09:30 AM',
        start_time_clock: start_time || '09:30 AM',
        available_time_minutes: available_time_minutes || Math.round(Number(hours) * 60),
        time_hours: hours,
        transport_mode: transport_mode || 'DRIVE',
        interests: interests || (vibe ? [vibe] : []),
        vibe: vibe || vibe_preference,
        vibe_preference: vibe || vibe_preference,
        price_level: price_level,
      });

      console.log('Real Route Response:', response.data);
      if (response.data?.start_location) {
        setStartLocation(response.data.start_location);
      }
      setRouteResult(response.data);
    } catch (err) {
      console.error('Failed to generate route:', err);
      const detail = err.response?.data?.detail;
      const message = typeof detail === 'string'
        ? detail
        : (err.message || 'Failed to communicate with backend server.');
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const places = routeResult?.optimized_places || routeResult?.trip?.stops || [];
  const legs = routeResult?.legs || [];
  const polyline = routeResult?.polyline || '';
  const totalTripTime = routeResult?.total_trip_time || '';

  return (
    <div className="min-h-screen bg-brand-cream text-brand-navy flex flex-col font-sans selection:bg-brand-teal selection:text-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-brand-navy/10 bg-white/95 backdrop-blur-md sticky top-0 z-30 shadow-sm py-3 sm:py-3.5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <img
              src="/logo.png"
              alt="Routi Logo"
              className="h-9 w-9 sm:h-10 sm:w-10 object-contain shrink-0"
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = '/routi-logo.png';
              }}
            />
            <div className="flex items-center">
              <span className="text-xl sm:text-2xl font-black text-brand-navy tracking-tight leading-none">Routi</span>
              <span className="hidden sm:inline-block ml-2.5 text-xs px-2.5 py-0.5 rounded-full bg-brand-navy/10 text-brand-navy border border-brand-navy/20 font-bold">
                Day Trip Studio
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 bg-brand-cream/80 border border-brand-navy/15 py-1.5 px-3.5 rounded-full shadow-sm">
              <div
                className={`h-2 w-2 rounded-full ${
                  backendHealth.status === 'connected' ? 'bg-brand-teal animate-pulse' : 'bg-brand-yellow'
                }`}
              ></div>
              <span className="text-xs font-bold text-brand-navy">
                {backendHealth.status === 'connected' ? 'Live Routing Active' : 'Connecting Engine...'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5 sm:py-6">
        {/* Error Banner at Top if Request Fails */}
        {errorMessage && (
          <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs sm:text-sm flex items-start justify-between space-x-3 shadow-lg animate-fadeIn">
            <div className="flex items-start space-x-3">
              <svg className="w-5 h-5 shrink-0 text-rose-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="font-semibold text-rose-200">Unable to Generate Route</p>
                <p className="text-rose-300/90 mt-0.5 text-xs">{errorMessage}</p>
              </div>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-400 hover:text-rose-200 text-xs font-semibold px-2 py-1 rounded-lg hover:bg-rose-500/20 transition cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Responsive Grid: Stacks on mobile (form/timeline top, map bottom), two-column on desktop */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column (Desktop) / Top Section (Mobile): SearchForm and Timeline */}
          <div className="lg:col-span-5 w-full space-y-6 order-1">
            <SearchForm
              onSubmit={handleGenerateRoute}
              onLocationChange={handleLocationChange}
              isLoading={isLoading}
            />

            {/* Loading Indicator Card */}
            {isLoading && <LoadingCard />}

            {/* Timeline: Rendered below form once route is generated */}
            {routeResult && !isLoading && (
              <Timeline
                startLocation={startLocation}
                places={places}
                legs={legs}
                totalTripTime={totalTripTime}
                totalDurationMins={routeResult?.total_duration_minutes ?? routeResult?.total_trip_mins ?? 0}
                googleMapsUrl={routeResult?.google_maps_url}
                totalTravelMins={routeResult?.travel_time_minutes ?? routeResult?.total_travel_mins ?? 0}
                totalDwellMins={routeResult?.visit_time_minutes ?? routeResult?.total_dwell_mins ?? 0}
                slackRemainingMins={routeResult?.slack_remaining_mins}
                safetyBufferMins={routeResult?.safety_buffer_minutes ?? routeResult?.safety_buffer_mins ?? routeResult?.safety_buffer ?? 0}
                startClock={routeResult?.start_time || routeResult?.start_clock}
                endClock={routeResult?.actual_return_time || routeResult?.end_clock}
                bufferedEndClock={routeResult?.buffered_end_clock || routeResult?.trip?.buffered_end_clock}
                timeAccounting={routeResult?.time_accounting || routeResult?.trip?.time_accounting}
                rejectedDestinations={routeResult?.rejected_destinations}
                narrative={routeResult?.narrative}
                routeScore={routeResult?.route_score ?? routeResult?.score ?? routeResult?.trip?.score}
              />
            )}
          </div>

          {/* Right Column (Desktop) / Bottom Section (Mobile): Google Map */}
          <div className="lg:col-span-7 w-full lg:sticky lg:top-20 order-2">
            <div className="h-[380px] sm:h-[460px] lg:h-[calc(100vh-130px)] min-h-[380px] max-h-[780px] flex flex-col">
              <Map
                startLocation={startLocation}
                places={places}
                polyline={polyline}
                isLoaded={isLoaded}
                loadError={loadError}
              />
            </div>
          </div>
        </div>
      </main>

      {/* Interactive AI Concierge Assistant Drawer & Action Buttons */}
      <AgentChat
        currentItinerary={routeResult}
        startLocation={startLocation}
        onUpdateRoute={(updatedRoute) => {
          console.log('Active route updated by AI Concierge:', updatedRoute);
          setRouteResult(updatedRoute);
          if (updatedRoute?.start_location?.lat && updatedRoute?.start_location?.lng) {
            setStartLocation(updatedRoute.start_location);
          }
        }}
      />
    </div>
  );
}

export default App;
