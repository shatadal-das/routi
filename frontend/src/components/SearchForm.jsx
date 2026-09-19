import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function SearchForm({
  onSubmit,
  onLocationChange,
  isLoading = false,
  loadingMessage = 'Curating Itinerary...',
}) {
  const [address, setAddress] = useState('');
  const [coords, setCoords] = useState({ lat: null, lng: null });
  const [timeHours, setTimeHours] = useState(4.5);
  const [transportMode, setTransportMode] = useState('DRIVE');
  const [selectedInterests, setSelectedInterests] = useState([]);
  const [vibe, setVibe] = useState('');
  const [priceLevel, setPriceLevel] = useState('$$');
  const [startHour, setStartHour] = useState('');
  const [startMinute, setStartMinute] = useState('');
  const [startPeriod, setStartPeriod] = useState('AM');
  const [timeSelectedExplicitly, setTimeSelectedExplicitly] = useState(false);
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

  const handleUsePreset = (presetName, lat, lng) => {
    setAddress(presetName);
    setCoords({ lat, lng });
    setFormError('');
    setShowSuggestions(false);
    if (onLocationChange) {
      onLocationChange({ lat, lng, address: presetName });
    }
  };

  const formatHoursDisplay = (hours) => {
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    if (m === 0) return `${h} hrs`;
    return `${h}h ${m}m`;
  };

  const getFormattedStartTime = () => {
    if (!startHour || !startMinute) return '';
    return `${startHour.padStart(2, '0')}:${startMinute.padStart(2, '0')} ${startPeriod}`;
  };

  const get24HourStartTime = () => {
    if (!startHour || !startMinute) return '';
    let h = parseInt(startHour, 10);
    const m = parseInt(startMinute, 10);
    if (startPeriod === 'PM' && h !== 12) h += 12;
    if (startPeriod === 'AM' && h === 12) h = 0;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  };

  const calculateExpectedReturnClock = (hStr, mStr, periodStr, hoursDuration) => {
    if (!hStr || !mStr) return 'Select start time';
    let h = parseInt(hStr, 10);
    const m = parseInt(mStr, 10);
    if (periodStr === 'PM' && h !== 12) h += 12;
    if (periodStr === 'AM' && h === 12) h = 0;
    const totalStartMins = h * 60 + m;
    const totalEndMins = (totalStartMins + Math.round(hoursDuration * 60)) % 1440;
    const endH = Math.floor(totalEndMins / 60);
    const endM = totalEndMins % 60;
    const endPeriod = endH >= 12 ? 'PM' : 'AM';
    const displayH = endH % 12 === 0 ? 12 : endH % 12;
    return `${String(displayH).padStart(2, '0')}:${String(endM).padStart(2, '0')} ${endPeriod}`;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!address.trim() && coords.lat === null) {
      setFormError('Please select a departure location or choose a featured city.');
      return;
    }
    if (timeHours < 1.0) {
      setFormError('Please select at least 1.0 hour for an itinerary.');
      return;
    }
    if (!startHour || !startMinute || !timeSelectedExplicitly) {
      setFormError('Start Time must be explicitly selected. Please select your trip Start Time (Hour, Minute, and AM/PM) or click a quick preset.');
      return;
    }
    setFormError('');
    setShowSuggestions(false);

    const combinedInterests = [...selectedInterests];
    if (vibe.trim() && !combinedInterests.includes(vibe.trim())) {
      combinedInterests.push(vibe.trim());
    }

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
        start_time: getFormattedStartTime(),
        start_time_clock: getFormattedStartTime(),
        start_time_24h: get24HourStartTime(),
        transport_mode: transportMode,
        transportation_mode: transportMode,
        address: address.trim(),
        interests: combinedInterests,
        vibe: combinedInterests.join(', ') || undefined,
        vibe_preference: combinedInterests.join(', ') || undefined,
        price_level: priceLevel || undefined,
      });
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-5 sm:p-7 shadow-2xl backdrop-blur-xl">
      {/* Card Header */}
      <div className="flex items-center space-x-3.5 mb-6">
        <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 shadow-inner">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </div>
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Plan Your Day Trip</h2>
          <p className="text-xs text-slate-400 font-medium">Curated loop itineraries balanced for sightseeing, dining, and scenic driving</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Departure Point */}
        <div className="relative">
          <div className="flex items-center justify-between mb-2">
            <label htmlFor="starting-location-input" className="text-xs font-bold text-slate-200 tracking-wide uppercase">
              Starting Location
            </label>
            <span className="text-[11px] font-medium text-indigo-300 bg-indigo-950/60 border border-indigo-800/40 px-2.5 py-0.5 rounded-full">
              Round-Trip Loop
            </span>
          </div>

          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
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
              className="w-full pl-10 pr-10 py-3 bg-slate-950/90 border border-slate-700/80 rounded-2xl text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:border-transparent text-sm transition font-normal shadow-inner"
            />
            {isSearchingSuggestions && coords.lat === null && (
              <span className="absolute right-3.5 top-3.5">
                <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin"></div>
              </span>
            )}

            {/* Suggestions Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div
                ref={suggestionBoxRef}
                className="absolute left-0 right-0 top-full mt-2 bg-slate-900/98 backdrop-blur-xl border border-slate-700 rounded-2xl shadow-2xl z-50 overflow-hidden divide-y divide-slate-800"
              >
                {suggestions.map((item, idx) => (
                  <button
                    key={item.place_id || `sugg-${idx}`}
                    type="button"
                    onClick={() => handleSelectSuggestion(item)}
                    className="w-full text-left px-4 py-3 hover:bg-indigo-950/40 flex items-start space-x-3 transition cursor-pointer group"
                  >
                    <svg className="w-4 h-4 text-indigo-400 group-hover:text-indigo-300 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    </svg>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-slate-200 group-hover:text-white truncate">{item.name}</p>
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">{item.address}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Featured Destinations */}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-medium text-slate-400 mr-1">Popular origins:</span>
            <button
              type="button"
              onClick={() => handleUsePreset('San Francisco, CA', 37.7749, -122.4194)}
              className="text-[11px] font-medium px-3 py-1 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition cursor-pointer border border-slate-700/50"
            >
              San Francisco
            </button>
            <button
              type="button"
              onClick={() => handleUsePreset('New York, NY', 40.7128, -74.0060)}
              className="text-[11px] font-medium px-3 py-1 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition cursor-pointer border border-slate-700/50"
            >
              New York
            </button>
            <button
              type="button"
              onClick={() => handleUsePreset('London, UK', 51.5074, -0.1278)}
              className="text-[11px] font-medium px-3 py-1 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition cursor-pointer border border-slate-700/50"
            >
              London
            </button>
          </div>
        </div>

        {/* Trip Vibe & Atmosphere (AI Curated) */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <label htmlFor="vibe-input" className="text-xs font-bold text-slate-200 tracking-wide uppercase flex items-center space-x-1.5">
              <span>Trip Vibe</span>
              <span className="text-[11px] text-indigo-400 font-medium">✨ AI Curated</span>
            </label>
            {vibe && (
              <button
                type="button"
                onClick={() => setVibe('')}
                className="text-[11px] text-slate-400 hover:text-rose-400 transition cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
              <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <input
              id="vibe-input"
              type="text"
              placeholder="e.g., Relaxed waterfront walk and spicy food, no rushing."
              value={vibe}
              onChange={(e) => setVibe(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950/90 border border-slate-700/80 rounded-2xl text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:border-transparent text-sm transition"
            />
          </div>

          {/* Quick Interest Filter Chips */}
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            {[
              { id: 'nature', label: '🌲 Nature & Parks' },
              { id: 'cafe', label: '☕ Cafes & Coffee' },
              { id: 'food', label: '🍽️ Dining & Food' },
              { id: 'culture', label: '🏛️ Art & Culture' },
              { id: 'viewpoint', label: '🌄 Scenic Views' },
              { id: 'waterfront', label: '🌊 Waterfront' }
            ].map((chip) => {
              const isSelected = selectedInterests.includes(chip.id);
              return (
                <button
                  key={chip.id}
                  type="button"
                  onClick={() => {
                    setSelectedInterests((prev) =>
                      isSelected ? prev.filter((i) => i !== chip.id) : [...prev, chip.id]
                    );
                  }}
                  className={`text-[11px] font-medium px-3 py-1 rounded-xl transition cursor-pointer ${
                    isSelected
                      ? 'bg-indigo-500/25 text-indigo-200 border border-indigo-500/60 shadow-sm'
                      : 'bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700/50'
                  }`}
                >
                  {chip.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Transportation Mode */}
        <div>
          <label className="text-xs font-bold text-slate-200 tracking-wide uppercase block mb-2">
            Transportation Mode
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: 'DRIVE', icon: '🚗', label: 'Driving', desc: 'Standard road trip' },
              { id: 'WALK', icon: '🚶', label: 'Walking', desc: 'Compact neighborhood' },
              { id: 'BICYCLE', icon: '🚲', label: 'Biking', desc: 'Active cycling loop' },
            ].map((mode) => (
              <button
                key={mode.id}
                type="button"
                onClick={() => setTransportMode(mode.id)}
                className={`p-2.5 rounded-2xl border text-center transition cursor-pointer ${
                  transportMode === mode.id
                    ? 'bg-indigo-950/70 border-indigo-500/80 text-white shadow-md'
                    : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                }`}
              >
                <span className="text-base block mb-0.5">{mode.icon}</span>
                <span className="text-xs font-bold block">{mode.label}</span>
                <span className="text-[10px] text-slate-500 block truncate">{mode.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Budget Tier */}
        <div>
          <label className="text-xs font-bold text-slate-200 tracking-wide uppercase block mb-2">
            Budget Tier
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: '$', label: '$ Budget', desc: 'Casual & street eats' },
              { id: '$$', label: '$$ Moderate', desc: 'Popular cafes & bistros' },
              { id: '$$$', label: '$$$ Upscale', desc: 'Fine dining & landmarks' }
            ].map((tier) => (
              <button
                key={tier.id}
                type="button"
                onClick={() => setPriceLevel(tier.id)}
                className={`p-2.5 rounded-2xl border text-left transition cursor-pointer ${
                  priceLevel === tier.id
                    ? 'bg-indigo-950/70 border-indigo-500/80 text-white shadow-md'
                    : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                }`}
              >
                <span className="text-xs font-bold block">{tier.label}</span>
                <span className="text-[10px] text-slate-500 block truncate">{tier.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Explicit Departure Time Input: Hour, Minute, AM/PM */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <div>
              <label htmlFor="start-time-hour" className="text-xs font-bold text-slate-200 tracking-wide uppercase block">
                Start Time
              </label>
              <span className="text-[11px] text-slate-400">
                Paces meal windows & departure/return schedule
              </span>
            </div>
            {getFormattedStartTime() ? (
              <div className="px-3 py-1 bg-indigo-950/70 border border-indigo-500/40 rounded-xl text-xs font-bold text-indigo-300 flex items-center space-x-1.5">
                <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>🕐 {getFormattedStartTime()}</span>
              </div>
            ) : (
              <div className="px-2.5 py-1 bg-amber-500/15 border border-amber-500/40 rounded-xl text-xs font-semibold text-amber-300 flex items-center space-x-1">
                <span>⚠️ Required: Select Time</span>
              </div>
            )}
          </div>

          {/* 3-Part Time Selector: Hour, Minute, AM/PM */}
          <div className="grid grid-cols-12 gap-2">
            {/* Hour Select */}
            <div className="col-span-5">
              <label htmlFor="start-time-hour" className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                Hour
              </label>
              <select
                id="start-time-hour"
                value={startHour}
                onChange={(e) => {
                  setStartHour(e.target.value);
                  if (e.target.value && startMinute) {
                    setTimeSelectedExplicitly(true);
                  }
                }}
                className={`w-full px-3 py-2.5 bg-slate-950/90 border rounded-2xl font-semibold text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/80 cursor-pointer ${
                  !startHour ? 'border-amber-500/60 text-amber-200/80' : 'border-slate-700/80 text-slate-100'
                }`}
              >
                <option value="" disabled className="bg-slate-900 text-slate-400">
                  -- Hour --
                </option>
                {['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'].map((hr) => (
                  <option key={hr} value={hr} className="bg-slate-900 text-white font-medium">
                    {hr}
                  </option>
                ))}
              </select>
            </div>

            {/* Minute Select */}
            <div className="col-span-4">
              <label htmlFor="start-time-minute" className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                Minute
              </label>
              <select
                id="start-time-minute"
                value={startMinute}
                onChange={(e) => {
                  setStartMinute(e.target.value);
                  if (startHour && e.target.value) {
                    setTimeSelectedExplicitly(true);
                  }
                }}
                className={`w-full px-3 py-2.5 bg-slate-950/90 border rounded-2xl font-semibold text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/80 cursor-pointer ${
                  !startMinute ? 'border-amber-500/60 text-amber-200/80' : 'border-slate-700/80 text-slate-100'
                }`}
              >
                <option value="" disabled className="bg-slate-900 text-slate-400">
                  -- Min --
                </option>
                {['00', '05', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55'].map((mn) => (
                  <option key={mn} value={mn} className="bg-slate-900 text-white font-medium">
                    :{mn}
                  </option>
                ))}
              </select>
            </div>

            {/* AM / PM Toggle */}
            <div className="col-span-3">
              <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                Period
              </label>
              <div className="grid grid-cols-2 gap-1 bg-slate-950/90 border border-slate-700/80 rounded-2xl p-1">
                <button
                  type="button"
                  onClick={() => {
                    setStartPeriod('AM');
                    setTimeSelectedExplicitly(true);
                  }}
                  className={`py-1.5 text-xs font-bold rounded-xl transition cursor-pointer ${
                    startPeriod === 'AM'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  AM
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStartPeriod('PM');
                    setTimeSelectedExplicitly(true);
                  }}
                  className={`py-1.5 text-xs font-bold rounded-xl transition cursor-pointer ${
                    startPeriod === 'PM'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  PM
                </button>
              </div>
            </div>
          </div>

          {/* Quick Preset Buttons (including user test cases: 09:00 AM, 12:00 PM, 05:30 PM) */}
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-slate-500 uppercase font-bold mr-1">Presets:</span>
            {[
              { label: '09:00 AM', h: '09', m: '00', p: 'AM' },
              { label: '09:30 AM', h: '09', m: '30', p: 'AM' },
              { label: '12:00 PM', h: '12', m: '00', p: 'PM' },
              { label: '05:30 PM', h: '05', m: '30', p: 'PM' },
            ].map((preset) => {
              const isActive = startHour === preset.h && startMinute === preset.m && startPeriod === preset.p;
              return (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    setStartHour(preset.h);
                    setStartMinute(preset.m);
                    setStartPeriod(preset.p);
                    setTimeSelectedExplicitly(true);
                  }}
                  className={`text-[11px] font-semibold px-2.5 py-1 rounded-xl transition cursor-pointer ${
                    isActive
                      ? 'bg-indigo-500/30 text-indigo-200 border border-indigo-500/60 shadow-sm'
                      : 'bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700/50'
                  }`}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>

          {/* Dynamic Schedule Preview Badge */}
          <div className="mt-2 p-2 rounded-xl bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
            <span>
              Expected Return: <strong className="text-indigo-300 font-semibold">{calculateExpectedReturnClock(startHour, startMinute, startPeriod, timeHours)}</strong>
            </span>
            <span className="text-slate-500">
              ({formatHoursDisplay(timeHours)} duration)
            </span>
          </div>
        </div>

        {/* Available Time Duration */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <div>
              <label htmlFor="time-hours-slider" className="text-xs font-bold text-slate-200 tracking-wide uppercase block">
                Available Time
              </label>
              <span className="text-[11px] text-slate-400">Includes sightseeing stops, dining, and driving buffers</span>
            </div>
            <div className="px-3 py-1 bg-indigo-950/50 border border-indigo-800/50 rounded-xl text-sm font-bold text-indigo-300">
              {formatHoursDisplay(timeHours)}
            </div>
          </div>

          <input
            id="time-hours-slider"
            type="range"
            min="2"
            max="12"
            step="0.5"
            value={timeHours}
            onChange={(e) => setTimeHours(Number(e.target.value))}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
          />
          <div className="flex justify-between text-[11px] font-medium text-slate-500 mt-1.5">
            <span>2h (Express Tour)</span>
            <span>6h (Half Day)</span>
            <span>12h (Full Day)</span>
          </div>
        </div>

        {formError && (
          <div className="p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2.5">
            <svg className="w-4 h-4 shrink-0 text-rose-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <span className="font-medium">{formError}</span>
          </div>
        )}

        {/* Primary Action Button */}
        <button
          id="generate-route-btn"
          type="submit"
          disabled={isLoading}
          className="w-full py-3.5 px-5 bg-gradient-to-r from-indigo-500 via-indigo-600 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-semibold rounded-2xl shadow-xl shadow-indigo-500/20 transition duration-200 flex items-center justify-center space-x-2.5 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer text-sm"
        >
          {isLoading ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>{loadingMessage}</span>
            </>
          ) : (
            <>
              <span>Generate Day Trip</span>
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
