import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function SearchForm({
  onSubmit,
  onLocationChange,
  isLoading = false,
  loadingMessage = 'Curating Itinerary...',
}) {
  const [address, setAddress] = useState('');
  const [coords, setCoords] = useState({ lat: null, lng: null });
  const [timeHours, setTimeHours] = useState(4.5);
  const [transportMode, setTransportMode] = useState('DRIVE');
  const [vibe, setVibe] = useState('');
  const [priceLevel, setPriceLevel] = useState('$$');
  const [startTime, setStartTime] = useState('09:30');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [formError, setFormError] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSearchingSuggestions, setIsSearchingSuggestions] = useState(false);
  const inputRef = useRef(null);
  const suggestionBoxRef = useRef(null);

  // Debounced search for live place suggestions
  useEffect(() => {
    if (!address || address.length < 2 || coords.lat !== null) {
      setSuggestions([]);
      return;
    }

    setIsSearchingSuggestions(true);
    const timer = setTimeout(async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/api/places/autocomplete`, {
          params: { query: address },
        });
        if (res.data?.results) {
          setSuggestions(res.data.results);
          setShowSuggestions(true);
        }
      } catch (err) {
        // Silent catch
      } finally {
        setIsSearchingSuggestions(false);
      }
    }, 280);

    return () => clearTimeout(timer);
  }, [address, coords.lat]);

  // Close suggestions on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        suggestionBoxRef.current &&
        !suggestionBoxRef.current.contains(e.target) &&
        inputRef.current &&
        !inputRef.current.contains(e.target)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleManualAddressChange = (e) => {
    setAddress(e.target.value);
    if (coords.lat !== null) {
      setCoords({ lat: null, lng: null });
    }
    setShowSuggestions(true);
    if (onLocationChange) {
      onLocationChange(null);
    }
  };

  const handleSelectSuggestion = (item) => {
    const displayName = item.address || item.name;
    setAddress(displayName);
    setCoords({ lat: item.lat, lng: item.lng });
    setShowSuggestions(false);
    setFormError('');
    if (onLocationChange) {
      onLocationChange({ lat: item.lat, lng: item.lng, address: displayName });
    }
  };

  const formatHoursDisplay = (hours) => {
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    if (m === 0) return `${h} hrs`;
    return `${h}h ${m}m`;
  };

  const formatTimeTo12Hour = (timeStr) => {
    if (!timeStr) return '09:30 AM';
    const [hStr, mStr] = timeStr.split(':');
    let h = parseInt(hStr, 10);
    const m = parseInt(mStr, 10);
    if (isNaN(h) || isNaN(m)) return '09:30 AM';
    const period = h >= 12 ? 'PM' : 'AM';
    const displayH = h % 12 === 0 ? 12 : h % 12;
    return `${String(displayH).padStart(2, '0')}:${String(m).padStart(2, '0')} ${period}`;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!address.trim() && coords.lat === null) {
      setFormError('Please enter a departure location.');
      return;
    }
    if (timeHours < 1.0) {
      setFormError('Please select at least 1.0 hour for an itinerary.');
      return;
    }
    setFormError('');
    setShowSuggestions(false);

    const formattedStart = formatTimeTo12Hour(startTime);

    if (onSubmit) {
      onSubmit({
        start_location: {
          lat: coords.lat,
          lng: coords.lng,
          address: address.trim(),
        },
        lat: coords.lat,
        lng: coords.lng,
        hours: Number(timeHours),
        available_time_minutes: Math.round(Number(timeHours) * 60),
        start_time: formattedStart,
        start_time_clock: formattedStart,
        start_time_24h: startTime || '09:30',
        transport_mode: transportMode,
        transportation_mode: transportMode,
        address: address.trim(),
        interests: vibe.trim() ? [vibe.trim()] : [],
        vibe: vibe.trim() || undefined,
        vibe_preference: vibe.trim() || undefined,
        price_level: priceLevel || undefined,
      });
    }
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 sm:p-8 shadow-sm">
      {/* Card Header */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-brand-navy tracking-tight">Design Your Journey</h2>
        <p className="text-xs text-gray-500 font-medium mt-1">Curated loop itineraries balanced for sightseeing, dining, and scenic driving</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-8">
        {/* Departure Point */}
        <div className="relative">
          <label htmlFor="starting-location-input" className="text-xs text-gray-500 uppercase tracking-widest font-semibold block mb-2">
            Starting Location
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <input
              id="starting-location-input"
              ref={inputRef}
              type="text"
              autoComplete="off"
              placeholder="Search address, hotel, or landmark (e.g. Union Square)..."
              value={address}
              onChange={handleManualAddressChange}
              onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
              className="w-full pl-10 pr-10 py-3 bg-gray-50/60 hover:bg-gray-50 border border-gray-200 focus:border-brand-navy focus:bg-white rounded-2xl text-brand-navy placeholder-gray-400 focus:outline-none text-sm transition"
            />
            {isSearchingSuggestions && coords.lat === null && (
              <span className="absolute right-3.5 top-3.5">
                <div className="w-4 h-4 border-2 border-brand-teal border-t-transparent rounded-full animate-spin"></div>
              </span>
            )}

            {/* Suggestions Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div
                ref={suggestionBoxRef}
                className="absolute left-0 right-0 top-full mt-2 bg-white border border-gray-200 rounded-2xl shadow-xl z-50 overflow-hidden divide-y divide-gray-100"
              >
                {suggestions.map((item, idx) => (
                  <button
                    key={item.place_id || `sugg-${idx}`}
                    type="button"
                    onClick={() => handleSelectSuggestion(item)}
                    className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-start space-x-3 transition cursor-pointer group"
                  >
                    <svg className="w-4 h-4 text-brand-teal group-hover:text-brand-navy mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    </svg>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-brand-navy group-hover:text-brand-teal truncate">{item.name}</p>
                      <p className="text-[11px] text-gray-500 truncate mt-0.5">{item.address}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Available Time Duration */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <label htmlFor="time-hours-slider" className="text-xs text-gray-500 uppercase tracking-widest font-semibold block">
              Available Time
            </label>
            <span className="text-xs font-bold text-brand-navy">
              {formatHoursDisplay(timeHours)}
            </span>
          </div>
          <input
            id="time-hours-slider"
            type="range"
            min="2"
            max="12"
            step="0.5"
            value={timeHours}
            onChange={(e) => setTimeHours(Number(e.target.value))}
            className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-brand-navy"
          />
        </div>

        {/* Collapsible Advanced Preferences */}
        <div>
          <button
            id="toggle-advanced-preferences"
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full py-1 flex items-center justify-between text-xs font-semibold text-gray-500 hover:text-brand-navy transition cursor-pointer group"
          >
            <span className="uppercase tracking-widest">Advanced Preferences</span>
            <span className="text-xs font-bold text-gray-400 group-hover:text-brand-navy transition">
              {showAdvanced ? 'Hide −' : 'Show +'}
            </span>
          </button>

          {showAdvanced && (
            <div className="mt-5 pt-5 border-t border-gray-100 flex flex-col gap-6 animate-fadeIn">
              {/* Trip Vibe & Atmosphere */}
              <div>
                <label htmlFor="vibe-input" className="text-xs text-gray-500 uppercase tracking-widest font-semibold block mb-2">
                  Trip Vibe
                </label>
                <input
                  id="vibe-input"
                  type="text"
                  placeholder="e.g., Relaxed waterfront walk and spicy food, no rushing"
                  value={vibe}
                  onChange={(e) => setVibe(e.target.value)}
                  className="w-full bg-transparent border-b border-gray-300 focus:border-brand-navy focus:outline-none text-brand-navy placeholder-gray-400 text-sm py-2 transition"
                />
              </div>

              {/* Transportation Mode - Segmented Control */}
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-widest font-semibold block mb-2">
                  Transportation Mode
                </label>
                <div className="p-1 bg-gray-100 rounded-xl flex space-x-1">
                  {[
                    { id: 'DRIVE', label: 'Driving' },
                    { id: 'WALK', label: 'Walking' },
                    { id: 'BICYCLE', label: 'Biking' },
                  ].map((mode) => {
                    const active = transportMode === mode.id;
                    return (
                      <button
                        key={mode.id}
                        type="button"
                        onClick={() => setTransportMode(mode.id)}
                        className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                          active
                            ? 'bg-white text-brand-navy shadow-sm'
                            : 'text-gray-500 hover:text-brand-navy'
                        }`}
                      >
                        {mode.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Budget Tier - Segmented Control */}
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-widest font-semibold block mb-2">
                  Budget Tier
                </label>
                <div className="p-1 bg-gray-100 rounded-xl flex space-x-1">
                  {[
                    { id: '$', label: '$ Budget' },
                    { id: '$$', label: '$$ Moderate' },
                    { id: '$$$', label: '$$$ Upscale' },
                  ].map((tier) => {
                    const active = priceLevel === tier.id;
                    return (
                      <button
                        key={tier.id}
                        type="button"
                        onClick={() => setPriceLevel(tier.id)}
                        className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                          active
                            ? 'bg-white text-brand-navy shadow-sm'
                            : 'text-gray-500 hover:text-brand-navy'
                        }`}
                      >
                        {tier.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Start Time - Single HTML5 Time Picker */}
              <div>
                <label htmlFor="start-time-input" className="text-xs text-gray-500 uppercase tracking-widest font-semibold block mb-2">
                  Start Time
                </label>
                <input
                  id="start-time-input"
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full bg-transparent border-b border-gray-300 focus:border-brand-navy focus:outline-none text-brand-navy font-semibold text-sm py-2 transition cursor-pointer"
                />
              </div>
            </div>
          )}
        </div>

        {formError && (
          <div className="p-3.5 rounded-2xl bg-brand-red/10 border border-brand-red/30 text-brand-red text-xs flex items-center space-x-2.5">
            <svg className="w-4 h-4 shrink-0 text-brand-red" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <span className="font-bold">{formError}</span>
          </div>
        )}

        {/* Primary Action Button */}
        <button
          id="generate-route-btn"
          type="submit"
          disabled={isLoading}
          className="w-full py-3.5 px-6 bg-brand-navy text-white hover:opacity-95 font-bold rounded-full shadow-md hover:shadow-lg transition duration-200 flex items-center justify-center space-x-2 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer text-sm tracking-wide"
        >
          {isLoading ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Generating Route...</span>
            </>
          ) : (
            <>
              <span>Generate Route</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </>
          )}
        </button>
      </form>
    </div>
  );
}

export default React.memo(SearchForm);
