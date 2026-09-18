import React, { useState, useEffect } from 'react';
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
    subtitle: 'Gemini 3.8 Flash matching venues with your custom trip atmosphere',
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

function App() {
  const [backendHealth, setBackendHealth] = useState({ status: 'loading', message: 'Checking API...' });
  const [startLocation, setStartLocation] = useState({
    lat: 37.7749,
    lng: -122.4194,
    address: 'San Francisco, CA',
  });
  const [routeResult, setRouteResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [errorMessage, setErrorMessage] = useState(null);

  // Single shared Google Maps API loader for the application
  const { isLoaded, loadError } = useJsApiLoader({
    id: 'routi-google-map-script',
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '',
    libraries: GOOGLE_MAPS_LIBRARIES,
  });

  // Cycle through intelligent loading messages while curating
  useEffect(() => {
    let interval = null;
    if (isLoading) {
      setLoadingMessageIndex(0);
      interval = setInterval(() => {
        setLoadingMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
      }, 2200);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading]);

  useEffect(() => {
    axios.get(`${API_BASE_URL}/api/health`)
      .then((res) => {
        setBackendHealth({ status: 'connected', message: res.data.message });
      })
      .catch(() => {
        setBackendHealth({ status: 'error', message: 'Backend unreachable' });
      });
  }, []);

  const handleLocationChange = (loc) => {
    setStartLocation(loc);
    // Clear any previous error when user picks new location
    setErrorMessage(null);
  };

  const handleGenerateRoute = async (formData) => {
    setIsLoading(true);
    setErrorMessage(null);

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
    } = formData;

    setStartLocation({ lat, lng, address });

    try {
      const response = await axios.post(`${API_BASE_URL}/api/plan-trip`, {
        start_location: start_location || { lat, lng, address },
        start_lat: lat,
        start_lng: lng,
        address: address,
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
  };

  const places = routeResult?.optimized_places || [];
  const legs = routeResult?.legs || [];
  const polyline = routeResult?.polyline || '';
  const totalTripTime = routeResult?.total_trip_time || '';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20 shrink-0">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <div>
              <span className="text-lg font-bold text-white tracking-tight">Routi</span>
              <span className="hidden sm:inline-block ml-2.5 text-xs px-2.5 py-0.5 rounded-full bg-indigo-950/60 text-indigo-300 border border-indigo-800/40 font-medium">
                Day Trip Studio
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 bg-slate-900/90 border border-slate-800/90 py-1.5 px-3.5 rounded-full shadow-sm">
              <div
                className={`h-2 w-2 rounded-full ${
                  backendHealth.status === 'connected' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                }`}
              ></div>
              <span className="text-xs font-medium text-slate-300">
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
              loadingMessage={LOADING_MESSAGES[loadingMessageIndex].title}
              isLoaded={isLoaded}
              loadError={loadError}
            />

            {/* Loading Indicator Card */}
            {isLoading && (
              <div className="p-4 sm:p-5 rounded-3xl bg-indigo-950/50 border border-indigo-500/40 flex items-center space-x-3.5 shadow-xl transition-all duration-300">
                <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin shrink-0"></div>
                <div className="text-xs min-w-0">
                  <p className="font-bold text-indigo-200 text-sm transition-all duration-300">
                    {LOADING_MESSAGES[loadingMessageIndex].title}
                  </p>
                  <p className="text-indigo-300/80 mt-0.5 font-medium transition-all duration-300">
                    {LOADING_MESSAGES[loadingMessageIndex].subtitle}
                  </p>
                </div>
              </div>
            )}

            {/* Timeline: Rendered below form once route is generated */}
            {routeResult && !isLoading && (
              <Timeline
                startLocation={startLocation}
                places={places}
                legs={legs}
                totalTripTime={totalTripTime}
                googleMapsUrl={routeResult?.google_maps_url}
                totalTravelMins={routeResult?.total_travel_mins}
                totalDwellMins={routeResult?.total_dwell_mins}
                slackRemainingMins={routeResult?.slack_remaining_mins}
                startClock={routeResult?.start_clock}
                endClock={routeResult?.end_clock}
                rejectedDestinations={routeResult?.rejected_destinations}
                narrative={routeResult?.narrative}
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
