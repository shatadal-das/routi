import React, { useState } from 'react';

/**
 * Universal Google Maps Directions URL generator
 */
export function buildUniversalGoogleMapsUrl(startLocation, places = [], travelmode = 'driving') {
  if (!startLocation) return '';
  const origin =
    startLocation.lat && startLocation.lng
      ? `${startLocation.lat},${startLocation.lng}`
      : startLocation.address || '';
  const destination = origin;

  const waypoints = (places || [])
    .slice(0, 9)
    .map((p) => `${p.lat},${p.lng}`)
    .join('|');

  let url = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(
    origin
  )}&destination=${encodeURIComponent(destination)}&travelmode=${travelmode}`;

  if (waypoints) {
    url += `&waypoints=${encodeURIComponent(waypoints)}`;
  }
  return url;
}

/**
 * Category styling and icons helper
 */
function getCategoryMeta(category = '', mealType = null) {
  const cat = (category || '').toLowerCase();
  if (mealType || cat.includes('restaurant') || cat.includes('dining') || cat.includes('food')) {
    const meal = mealType ? mealType.charAt(0).toUpperCase() + mealType.slice(1).toLowerCase() : 'Dining';
    return {
      icon: '🍽️',
      name: mealType ? meal : 'Dining',
      colorBg: 'bg-amber-500/20',
      colorBorder: 'border-amber-400',
      colorText: 'text-amber-400',
      colorDot: 'bg-amber-400',
      cardBg: 'bg-amber-950/15 hover:bg-amber-950/25 border-amber-800/40',
      badgeBg: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    };
  }
  if (cat.includes('cafe') || cat.includes('coffee') || cat.includes('bakery')) {
    return {
      icon: '☕',
      name: 'Cafe',
      colorBg: 'bg-orange-500/20',
      colorBorder: 'border-orange-400',
      colorText: 'text-orange-400',
      colorDot: 'bg-orange-400',
      cardBg: 'bg-orange-950/15 hover:bg-orange-950/25 border-orange-800/40',
      badgeBg: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    };
  }
  if (cat.includes('lake') || cat.includes('water') || cat.includes('beach')) {
    return {
      icon: '🌳',
      name: cat.includes('lake') ? 'Lake' : 'Waterfront',
      colorBg: 'bg-cyan-500/20',
      colorBorder: 'border-cyan-400',
      colorText: 'text-cyan-400',
      colorDot: 'bg-cyan-400',
      cardBg: 'bg-cyan-950/15 hover:bg-cyan-950/25 border-cyan-800/40',
      badgeBg: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    };
  }
  if (cat.includes('park') || cat.includes('nature') || cat.includes('garden')) {
    return {
      icon: '🌳',
      name: 'Park',
      colorBg: 'bg-emerald-500/20',
      colorBorder: 'border-emerald-400',
      colorText: 'text-emerald-400',
      colorDot: 'bg-emerald-400',
      cardBg: 'bg-emerald-950/15 hover:bg-emerald-950/25 border-emerald-800/40',
      badgeBg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    };
  }
  if (cat.includes('viewpoint') || cat.includes('scenic') || cat.includes('lookout')) {
    return {
      icon: '🌄',
      name: 'Viewpoint',
      colorBg: 'bg-sky-500/20',
      colorBorder: 'border-sky-400',
      colorText: 'text-sky-400',
      colorDot: 'bg-sky-400',
      cardBg: 'bg-sky-950/15 hover:bg-sky-950/25 border-sky-800/40',
      badgeBg: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
    };
  }
  if (cat.includes('museum') || cat.includes('art') || cat.includes('history') || cat.includes('gallery')) {
    return {
      icon: '🏛️',
      name: 'Museum',
      colorBg: 'bg-purple-500/20',
      colorBorder: 'border-purple-400',
      colorText: 'text-purple-400',
      colorDot: 'bg-purple-400',
      cardBg: 'bg-purple-950/15 hover:bg-purple-950/25 border-purple-800/40',
      badgeBg: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    };
  }
  return {
    icon: '🏛️',
    name: 'Attraction',
    colorBg: 'bg-indigo-500/20',
    colorBorder: 'border-indigo-400',
    colorText: 'text-indigo-400',
    colorDot: 'bg-indigo-400',
    cardBg: 'bg-slate-800/50 hover:bg-slate-800/80 border-slate-700/60',
    badgeBg: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  };
}

const formatMinutesToHours = (mins) => {
  if (!mins || mins <= 0) return '0m';
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  if (h > 0 && m > 0) return `${h}h ${m}m`;
  if (h > 0) return `${h}h`;
  return `${m}m`;
};

export default function Timeline({
  startLocation,
  places = [],
  legs = [],
  totalTripTime = '',
  totalDurationMins = 0,
  googleMapsUrl = '',
  totalTravelMins = 0,
  totalDwellMins = 0,
  slackRemainingMins = 0,
  safetyBufferMins = 0,
  startClock = '09:30 AM',
  endClock = '',
  rejectedDestinations = [],
  narrative = '',
}) {
  const effectiveBufferMins = safetyBufferMins || 0;
  const computedTotalMins = totalDurationMins || (totalTravelMins + totalDwellMins + effectiveBufferMins);
  const formattedTotalDuration = formatMinutesToHours(computedTotalMins) || totalTripTime;
  const [showRejected, setShowRejected] = useState(false);
  const startAddress = startLocation?.address || startLocation?.name || 'Starting Point';

  const finalGoogleMapsUrl =
    googleMapsUrl || buildUniversalGoogleMapsUrl(startLocation, places, 'driving');

  const handleOpenGoogleMaps = () => {
    if (finalGoogleMapsUrl) {
      window.open(finalGoogleMapsUrl, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-5 sm:p-7 shadow-2xl backdrop-blur-xl">
      {/* Header & Planning Pillars */}
      <div className="pb-5 border-b border-slate-800/80 mb-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">Optimized Day Itinerary</h3>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              Deterministic round-trip loop • Verified travel legs & category visit times
            </p>
          </div>

          {/* Distinguished Timing Badges */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="bg-slate-800/90 border border-slate-700/70 text-slate-200 px-2.5 py-1 rounded-xl flex items-center space-x-1" title="Trip departure clock">
              <span>🕐</span>
              <span className="text-slate-400 font-medium">Start</span>
            </span>
            <span className="bg-slate-800/90 border border-slate-700/70 text-slate-200 px-2.5 py-1 rounded-xl flex items-center space-x-1" title="Total transit on road">
              <span>🚗</span>
              <span className="text-slate-400 font-medium">Travel</span>
            </span>
            <span className="bg-slate-800/90 border border-slate-700/70 text-slate-200 px-2.5 py-1 rounded-xl flex items-center space-x-1" title="Destination dwell and meal time">
              <span>📍</span>
              <span className="text-slate-400 font-medium">Visits</span>
            </span>
            <span className="bg-indigo-950/80 border border-indigo-500/40 text-indigo-300 px-2.5 py-1 rounded-xl flex items-center space-x-1" title="Reserved travel uncertainty margin (isolated from activities)">
              <span>🛡</span>
              <span className="text-indigo-400 font-medium">Safety Buffer</span>
            </span>
            <span className="bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 px-2.5 py-1 rounded-xl flex items-center space-x-1" title="Return to start point">
              <span>🏁</span>
              <span className="text-emerald-400 font-medium">Return</span>
            </span>
          </div>
        </div>

        {/* Narrative Day Flow Summary */}
        {narrative && (
          <div className="mt-2 p-3 rounded-2xl bg-indigo-950/40 border border-indigo-500/20 text-xs text-indigo-200/90 leading-relaxed italic">
            "{narrative}"
          </div>
        )}
      </div>

      {/* SUMMARY LEVEL (Strictly conforms to required specification) */}
      <div className="mb-6 p-4 sm:p-5 rounded-2xl bg-slate-950/95 border border-slate-800 shadow-xl">
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center justify-between">
          <span>Itinerary Summary</span>
          <span className="text-indigo-400 font-semibold">Backend Optimizer Truth</span>
        </div>

        {/* Landmark Schedule Row */}
        <div className="grid grid-cols-3 gap-2 sm:gap-4 pb-3 border-b border-slate-800/80 text-center sm:text-left">
          <div>
            <div className="text-xs text-slate-400 font-medium flex items-center justify-center sm:justify-start space-x-1">
              <span>🕐</span>
              <span>Start:</span>
            </div>
            <div className="text-sm sm:text-base font-extrabold text-white mt-0.5 font-mono">
              {startClock || '09:30 AM'}
            </div>
          </div>

          <div>
            <div className="text-xs text-slate-400 font-medium flex items-center justify-center sm:justify-start space-x-1">
              <span>🏁</span>
              <span>Return:</span>
            </div>
            <div className="text-sm sm:text-base font-extrabold text-emerald-400 mt-0.5 font-mono">
              {endClock || '—'}
            </div>
          </div>

          <div>
            <div className="text-xs text-slate-400 font-medium flex items-center justify-center sm:justify-start space-x-1">
              <span>⏱️</span>
              <span>Total:</span>
            </div>
            <div className="text-sm sm:text-base font-extrabold text-indigo-300 mt-0.5 font-mono">
              {formattedTotalDuration || '—'}
            </div>
          </div>
        </div>

        {/* Duration Breakdown Row (Safety buffer kept separate from activities) */}
        <div className="grid grid-cols-3 gap-2 sm:gap-4 pt-3 text-center sm:text-left">
          <div>
            <div className="text-xs text-slate-400 font-medium flex items-center justify-center sm:justify-start space-x-1">
              <span>🚗</span>
              <span>Travel:</span>
            </div>
            <div className="text-sm sm:text-base font-bold text-slate-200 mt-0.5 font-mono">
              {totalTravelMins}m
            </div>
          </div>

          <div>
            <div className="text-xs text-slate-400 font-medium flex items-center justify-center sm:justify-start space-x-1">
              <span>📍</span>
              <span>Visits:</span>
            </div>
            <div className="text-sm sm:text-base font-bold text-slate-200 mt-0.5 font-mono">
              {totalDwellMins}m
            </div>
          </div>

          <div title="Reserved travel uncertainty margin; NOT counted as an activity">
            <div className="text-xs text-slate-400 font-medium flex items-center justify-center sm:justify-start space-x-1">
              <span>🛡</span>
              <span>Safety buffer:</span>
            </div>
            <div className="text-sm sm:text-base font-bold text-indigo-300 mt-0.5 font-mono">
              {effectiveBufferMins}m
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Export Banner */}
      <div className="mb-6 p-4 rounded-2xl bg-gradient-to-r from-slate-800/90 via-slate-800/70 to-indigo-950/40 border border-indigo-500/25 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center space-x-3 w-full sm:w-auto">
          <div className="w-9 h-9 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <div>
            <h4 className="text-xs font-bold text-white uppercase tracking-wider">Turn-by-Turn Navigation</h4>
            <p className="text-[11px] text-slate-400">Export sequenced loop itinerary to Google Maps</p>
          </div>
        </div>

        <button
          id="open-google-maps-btn"
          type="button"
          onClick={handleOpenGoogleMaps}
          className="w-full sm:w-auto px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white text-xs font-bold rounded-xl shadow-lg shadow-emerald-500/20 flex items-center justify-center space-x-1.5 transition duration-200 cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          <span>Open in Google Maps</span>
        </button>
      </div>

      {/* SEQUENTIAL ITINERARY TIMELINE */}
      <div className="relative border-l-2 border-indigo-500/30 ml-4 sm:ml-5 space-y-4 pl-6 sm:pl-7">
        
        {/* START NODE */}
        <div className="relative group">
          <span className="absolute -left-[31px] sm:-left-[35px] top-1 w-5 h-5 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          </span>

          <div className="bg-slate-800/50 hover:bg-slate-800/80 border border-slate-700/60 rounded-2xl p-4 transition shadow-sm">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-black uppercase tracking-wider text-emerald-400 flex items-center space-x-1.5 font-mono">
                <span>{startClock || '09:30 AM'} — Start</span>
              </span>
              <span className="text-[10px] font-bold text-emerald-400/80 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                Origin
              </span>
            </div>
            <h4 className="text-sm font-bold text-white">Depart from {startAddress}</h4>
            <p className="text-xs text-slate-400 mt-0.5">Begin your round-trip journey from your chosen departure location.</p>
          </div>
        </div>

        {/* DESTINATIONS & TRANSIT LEGS */}
        {places.map((place, idx) => {
          const leg = legs[idx];
          const prevTravelMins = place.travel_time_from_previous || (leg ? parseInt(leg.duration_text) : 15);
          const travelDistanceText = leg ? leg.distance_text : '';
          const isRestaurant = place.is_meal_stop || place.type === 'restaurant' || !!place.meal_type;
          const meta = getCategoryMeta(place.category || place.type, place.meal_type);
          const stopNumber = idx + 1;
          const visitDurationMins = place.visit_duration || place.visit_duration_minutes || place.duration_mins || 45;

          // Sequential leg timing: previous departure to current arrival
          const prevDepartureTime = idx === 0 ? (startClock || '09:30 AM') : (places[idx - 1]?.departure_time || '');
          const currentArrivalTime = place.arrival_time || '';
          const legTimeWindow = prevDepartureTime && currentArrivalTime ? `${prevDepartureTime}–${currentArrivalTime}` : '';

          return (
            <React.Fragment key={place.place_id || place.id || `stop-${idx}`}>
              {/* TRANSIT LEG CONNECTOR */}
              <div className="relative py-1">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-medium text-slate-300 bg-slate-950/90 border border-slate-800/90 py-2 px-3.5 rounded-xl shadow-sm">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm">🚗</span>
                    <span className="font-bold text-slate-200">Travel · {prevTravelMins} mins</span>
                    {travelDistanceText && <span className="text-slate-500">• {travelDistanceText}</span>}
                  </div>
                  {legTimeWindow && (
                    <span className="text-[11px] font-semibold text-indigo-300 font-mono bg-indigo-950/60 border border-indigo-500/30 px-2 py-0.5 rounded-md">
                      {legTimeWindow}
                    </span>
                  )}
                </div>
              </div>

              {/* DESTINATION / RESTAURANT CARD */}
              <div className="relative group">
                <span
                  className={`absolute -left-[31px] sm:-left-[35px] top-2 w-5 h-5 rounded-full border-2 flex items-center justify-center ${meta.colorBg} ${meta.colorBorder}`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${meta.colorDot}`}></span>
                </span>

                <div className={`border rounded-2xl p-4 transition shadow-sm ${meta.cardBg}`}>
                  {/* Top Bar: Stop number, Category / Meal badge, and Arrival–Departure */}
                  <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-extrabold text-slate-300 bg-slate-900/90 px-2.5 py-0.5 rounded-md border border-slate-700/60">
                        Stop {stopNumber}
                      </span>

                      {/* Explicit Distinction for Restaurants vs Other Destinations */}
                      {isRestaurant ? (
                        <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/25 text-amber-300 font-bold border border-amber-500/40 uppercase tracking-wide flex items-center space-x-1">
                          <span>🍽️</span>
                          <span>{place.meal_type || 'Lunch'}</span>
                        </span>
                      ) : (
                        <span className={`text-xs font-bold uppercase tracking-wider ${meta.colorText} flex items-center space-x-1`}>
                          <span>{meta.icon}</span>
                          <span>{meta.name}</span>
                        </span>
                      )}

                      {place.cuisine && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 font-medium border border-amber-500/30">
                          {place.cuisine}
                        </span>
                      )}
                    </div>

                    {/* Arrival - Departure Times */}
                    {place.arrival_time && place.departure_time && (
                      <div className="text-xs font-bold text-slate-200 bg-slate-900/90 px-2.5 py-1 rounded-lg border border-slate-700/60 flex items-center space-x-1 font-mono">
                        <span>🕐</span>
                        <span>{place.arrival_time} – {place.departure_time}</span>
                      </div>
                    )}
                  </div>

                  {/* Destination Name */}
                  <h4 className="text-base font-bold text-white tracking-tight leading-snug">
                    {place.name}
                  </h4>

                  {/* Destination Attributes: Duration, Rating, Category, Travel from Prior */}
                  <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs">
                    {isRestaurant ? (
                      <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-amber-950/70 border border-amber-500/40 text-amber-300 font-semibold shadow-sm">
                        <span>🍽️</span>
                        <span>Meal Duration: {visitDurationMins} mins</span>
                      </div>
                    ) : (
                      <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-indigo-950/70 border border-indigo-500/40 text-indigo-300 font-semibold shadow-sm">
                        <span>📍</span>
                        <span>Visit Duration: {visitDurationMins} mins</span>
                      </div>
                    )}

                    {place.rating && (
                      <span className="text-amber-400 font-bold flex items-center space-x-1 bg-slate-800/80 border border-slate-700/60 px-2.5 py-1 rounded-lg">
                        <span>★</span>
                        <span>{Number(place.rating).toFixed(1)}</span>
                      </span>
                    )}

                    <span className="text-slate-300 bg-slate-800/80 border border-slate-700/60 px-2.5 py-1 rounded-lg font-medium">
                      {place.category || meta.name}
                    </span>

                    {prevTravelMins > 0 && (
                      <span className="text-slate-400 bg-slate-900/60 border border-slate-800 px-2.5 py-1 rounded-lg text-[11px]">
                        🚗 Travel from prior: {prevTravelMins} mins
                      </span>
                    )}
                  </div>

                  {place.address && (
                    <p className="text-slate-400 text-xs mt-2 truncate">
                      📍 {place.address}
                    </p>
                  )}

                  {/* SELECTION REASON (Required for every destination) */}
                  <div className="mt-3 pt-2.5 border-t border-slate-700/50 text-xs">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                      Selection Reason:
                    </span>
                    <p className="text-slate-200 leading-relaxed">
                      {place.selection_reasons && place.selection_reasons.length > 0
                        ? place.selection_reasons.join(' • ')
                        : place.reason || place.ai_reasoning || 'Matches selected interests, optimal category pacing, and smooth route geometry.'}
                    </p>
                  </div>
                </div>
              </div>
            </React.Fragment>
          );
        })}

        {/* RETURN TRANSIT LEG CONNECTOR */}
        {places.length > 0 && (
          <div className="relative py-1">
            {(() => {
              const returnLeg = legs[places.length];
              const lastStop = places[places.length - 1];
              const returnTravelMins = returnLeg?.duration_mins || (returnLeg ? parseInt(returnLeg.duration_text) : 15);
              const returnDistanceText = returnLeg ? returnLeg.distance_text : '';
              const returnTimeWindow = lastStop?.departure_time && endClock ? `${lastStop.departure_time}–${endClock}` : '';

              return (
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-medium text-slate-300 bg-slate-950/90 border border-slate-800/90 py-2 px-3.5 rounded-xl shadow-sm">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm">🚗</span>
                    <span className="font-bold text-slate-200">Return · {returnTravelMins} mins</span>
                    {returnDistanceText && <span className="text-slate-500">• {returnDistanceText}</span>}
                  </div>
                  {returnTimeWindow && (
                    <span className="text-[11px] font-semibold text-emerald-300 font-mono bg-emerald-950/60 border border-emerald-500/30 px-2 py-0.5 rounded-md">
                      {returnTimeWindow}
                    </span>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        {/* BACK AT START NODE */}
        <div className="relative group">
          <span className="absolute -left-[31px] sm:-left-[35px] top-1 w-5 h-5 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          </span>

          <div className="bg-slate-800/50 hover:bg-slate-800/80 border border-slate-700/60 rounded-2xl p-4 transition shadow-sm">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-black uppercase tracking-wider text-emerald-400 flex items-center space-x-1.5 font-mono">
                <span>🏁 {endClock || 'Trip Return'} — Back at Start</span>
              </span>
              <span className="text-[10px] font-bold text-emerald-400/80 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                Round Trip Complete
              </span>
            </div>
            <h4 className="text-sm font-bold text-white">Return to {startAddress}</h4>
            <p className="text-xs text-slate-400 mt-0.5">Safely concluded your trip on schedule.</p>
          </div>
        </div>

      </div>

      {/* Destination Alternatives & Tradeoffs */}
      {rejectedDestinations && rejectedDestinations.length > 0 && (
        <div className="mt-8 pt-5 border-t border-slate-800/80">
          <button
            type="button"
            onClick={() => setShowRejected(!showRejected)}
            className="w-full flex items-center justify-between p-3.5 rounded-2xl bg-slate-800/40 hover:bg-slate-800/70 border border-slate-700/60 text-xs text-slate-300 font-semibold transition cursor-pointer"
          >
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Evaluated Candidates & Tradeoffs ({rejectedDestinations.length} considered)</span>
            </div>
            <span className="text-indigo-400 text-xs font-bold">
              {showRejected ? 'Hide ▲' : 'Show ▼'}
            </span>
          </button>

          {showRejected && (
            <div className="mt-3 space-y-2 p-3.5 bg-slate-950/50 border border-slate-800/80 rounded-2xl animate-fadeIn">
              <p className="text-[11px] text-slate-400 mb-2">
                Scanned spots from your area that were omitted to respect your duration limit, transit efficiency, or meal window balance:
              </p>
              <div className="divide-y divide-slate-800/60">
                {rejectedDestinations.map((cand, idx) => (
                  <div key={`rej-${idx}`} className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs">
                    <div>
                      <span className="font-semibold text-slate-200">{cand.place}</span>
                      <span className="ml-2 text-[10px] text-slate-400 uppercase tracking-wide">
                        ({cand.category || 'venue'})
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(cand.rejection_reasons || []).map((r, rIdx) => (
                        <span
                          key={`rr-${rIdx}`}
                          className="text-[10px] px-2 py-0.5 rounded-md bg-rose-950/40 border border-rose-800/40 text-rose-300 font-medium"
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
