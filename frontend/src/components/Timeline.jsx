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

function getCategoryColor(category) {
  const cat = (category || '').toLowerCase();
  if (cat.includes('restaurant') || cat.includes('dining')) {
    return {
      bg: 'bg-amber-500/20',
      border: 'border-amber-400',
      text: 'text-amber-400',
      dot: 'bg-amber-400',
      cardBg: 'bg-amber-950/15 hover:bg-amber-950/25 border-amber-800/40',
      label: 'Dining & Food',
    };
  }
  if (cat.includes('cafe') || cat.includes('coffee') || cat.includes('bakery')) {
    return {
      bg: 'bg-orange-500/20',
      border: 'border-orange-400',
      text: 'text-orange-400',
      dot: 'bg-orange-400',
      cardBg: 'bg-orange-950/15 hover:bg-orange-950/25 border-orange-800/40',
      label: 'Cafe & Bakery',
    };
  }
  if (cat.includes('park') || cat.includes('nature') || cat.includes('garden')) {
    return {
      bg: 'bg-emerald-500/20',
      border: 'border-emerald-400',
      text: 'text-emerald-400',
      dot: 'bg-emerald-400',
      cardBg: 'bg-emerald-950/15 hover:bg-emerald-950/25 border-emerald-800/40',
      label: 'Park & Outdoors',
    };
  }
  if (cat.includes('viewpoint') || cat.includes('scenic') || cat.includes('monument')) {
    return {
      bg: 'bg-cyan-500/20',
      border: 'border-cyan-400',
      text: 'text-cyan-400',
      dot: 'bg-cyan-400',
      cardBg: 'bg-cyan-950/15 hover:bg-cyan-950/25 border-cyan-800/40',
      label: 'Viewpoint & Scenic',
    };
  }
  if (cat.includes('museum') || cat.includes('art') || cat.includes('gallery') || cat.includes('history')) {
    return {
      bg: 'bg-purple-500/20',
      border: 'border-purple-400',
      text: 'text-purple-400',
      dot: 'bg-purple-400',
      cardBg: 'bg-purple-950/15 hover:bg-purple-950/25 border-purple-800/40',
      label: 'Arts & Culture',
    };
  }
  return {
    bg: 'bg-indigo-500/20',
    border: 'border-indigo-400',
    text: 'text-indigo-400',
    dot: 'bg-indigo-400',
    cardBg: 'bg-slate-800/50 hover:bg-slate-800/80 border-slate-700/60',
    label: 'Featured Attraction',
  };
}

export default function Timeline({
  startLocation,
  places = [],
  legs = [],
  totalTripTime = '',
  googleMapsUrl = '',
  totalTravelMins = 0,
  totalDwellMins = 0,
  slackRemainingMins = 0,
  startClock = '09:30 AM',
  endClock = '',
  rejectedDestinations = [],
  narrative = '',
}) {
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
      {/* Header */}
      <div className="pb-5 border-b border-slate-800/80 mb-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">Optimized Day Itinerary</h3>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              Strict loop guarantee • Guaranteed return within time budget
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {startClock && endClock && (
              <span className="text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 px-3 py-1.5 rounded-full flex items-center space-x-1.5">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{startClock} – {endClock}</span>
              </span>
            )}

            {totalTripTime && (
              <span className="text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/25 px-3 py-1.5 rounded-full">
                {totalTripTime} Total Experience
              </span>
            )}
          </div>
        </div>

        {/* Schedule Metric Pills */}
        {(totalTravelMins > 0 || totalDwellMins > 0) && (
          <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px]">
            <span className="bg-slate-800/80 border border-slate-700/60 text-slate-300 px-2.5 py-1 rounded-xl flex items-center space-x-1.5">
              <span>🚗</span>
              <span className="font-semibold text-slate-200">{totalTravelMins} mins</span>
              <span className="text-slate-400">transit</span>
            </span>
            <span className="bg-slate-800/80 border border-slate-700/60 text-slate-300 px-2.5 py-1 rounded-xl flex items-center space-x-1.5">
              <span>📍</span>
              <span className="font-semibold text-slate-200">{totalDwellMins} mins</span>
              <span className="text-slate-400">in destinations</span>
            </span>
            {slackRemainingMins > 0 && (
              <span className="bg-indigo-950/60 border border-indigo-800/50 text-indigo-300 px-2.5 py-1 rounded-xl flex items-center space-x-1.5">
                <span>🛡️</span>
                <span className="font-semibold text-indigo-200">{slackRemainingMins} mins</span>
                <span className="text-indigo-400">safety buffer</span>
              </span>
            )}
          </div>
        )}

        {/* Narrative Day Flow Summary */}
        {narrative && (
          <div className="mt-3 p-3.5 rounded-2xl bg-indigo-950/40 border border-indigo-500/20 text-xs text-indigo-200/90 leading-relaxed italic">
            "{narrative}"
          </div>
        )}
      </div>

      {/* Navigation Export Banner */}
      <div className="mb-7 p-4 sm:p-5 rounded-2xl bg-gradient-to-r from-slate-800/90 via-slate-800/70 to-indigo-950/40 border border-indigo-500/25 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center space-x-3.5 w-full sm:w-auto">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <div>
            <h4 className="text-xs font-bold text-white uppercase tracking-wider">Turn-by-Turn Navigation</h4>
            <p className="text-xs text-slate-400">Export complete route and stops to Google Maps</p>
          </div>
        </div>

        <button
          id="open-google-maps-btn"
          type="button"
          onClick={handleOpenGoogleMaps}
          className="w-full sm:w-auto px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white text-xs font-bold rounded-xl shadow-lg shadow-emerald-500/20 flex items-center justify-center space-x-2 transition duration-200 cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          <span>Open in Google Maps</span>
        </button>
      </div>

      {/* Step by Step Timeline */}
      <div className="relative pl-6 sm:pl-7 space-y-6 before:absolute before:left-2.5 sm:before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-700/60">
        {/* Step 1: Departure Point */}
        <div className="relative group">
          <span className="absolute -left-6 sm:-left-7 top-1 w-5 h-5 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          </span>

          <div className="bg-slate-800/50 hover:bg-slate-800/80 border border-slate-700/60 rounded-2xl p-4 transition shadow-sm">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                Departure Point • {startClock || '09:30 AM'}
              </span>
              <span className="text-[11px] font-semibold text-slate-500">Stop 1</span>
            </div>
            <h4 className="text-sm font-bold text-white">Depart from {startAddress}</h4>
            <p className="text-xs text-slate-400 mt-1">Begin your day tour from your chosen departure location.</p>
          </div>
        </div>

        {/* Stops and Legs */}
        {places.map((place, idx) => {
          const leg = legs[idx];
          const travelDurationText = leg ? leg.duration_text : '12 mins';
          const travelDistanceText = leg ? leg.distance_text : '';
          const style = getCategoryColor(place.category || place.type);
          const stopNumber = idx + 2;

          return (
            <React.Fragment key={place.place_id || `stop-${idx}`}>
              {/* Transit Pill */}
              <div className="relative py-0.5">
                <div className="flex items-center space-x-2 text-[11px] font-medium text-slate-400 bg-slate-950/90 border border-slate-800/90 py-1.5 px-3 rounded-xl w-fit shadow-sm">
                  <svg className="w-3.5 h-3.5 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                  <span>{travelDurationText} drive</span>
                  {travelDistanceText && <span className="text-slate-500">• {travelDistanceText}</span>}
                </div>
              </div>

              {/* Stop Card */}
              <div className="relative group">
                <span
                  className={`absolute -left-6 sm:-left-7 top-1 w-5 h-5 rounded-full border-2 flex items-center justify-center ${style.bg} ${style.border}`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`}></span>
                </span>

                <div className={`border rounded-2xl p-4 transition shadow-sm ${style.cardBg}`}>
                  {/* Category and Stop Tag */}
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center space-x-2">
                      <span className={`text-[11px] font-bold uppercase tracking-wider ${style.text}`}>
                        {style.label}
                      </span>
                      {place.cuisine && (
                        <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30">
                          {place.cuisine}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-2">
                      {place.arrival_time && place.departure_time && (
                        <span className="text-[11px] font-semibold text-slate-300 bg-slate-900/80 px-2 py-0.5 rounded-md border border-slate-700/60">
                          {place.arrival_time} – {place.departure_time}
                        </span>
                      )}
                      <span className="text-[11px] font-semibold text-slate-500">Stop {stopNumber}</span>
                    </div>
                  </div>

                  <h4 className="text-sm font-bold text-white">
                    {place.name}
                  </h4>

                  {/* Badges: Dwell, Rating, Price */}
                  <div className="mt-2.5 flex flex-wrap items-center gap-2">
                    <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-indigo-950/70 border border-indigo-500/40 text-indigo-300 font-semibold text-xs shadow-sm">
                      <svg className="w-3.5 h-3.5 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>
                        Dwell: {place.duration_mins ? `${place.duration_mins} mins` : `${Math.round((place.duration_hours || 1.0) * 60)} mins`}
                      </span>
                    </div>

                    {place.rating && (
                      <span className="text-amber-400 text-xs font-semibold flex items-center space-x-1 bg-slate-800/80 border border-slate-700/60 px-2 py-0.5 rounded-lg">
                        <span>★</span>
                        <span>{Number(place.rating).toFixed(1)}</span>
                      </span>
                    )}
                    {place.price_level && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-medium border border-slate-700/80">
                        {place.price_level}
                      </span>
                    )}
                  </div>

                  {place.address && (
                    <p className="text-slate-400 text-[11px] truncate mt-1.5">
                      {place.address}
                    </p>
                  )}

                  {/* Explainability Layer: Selection Reasons */}
                  {place.selection_reasons && place.selection_reasons.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-slate-700/50">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                        Why this was chosen:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {place.selection_reasons.map((reason, rIdx) => (
                          <span
                            key={`sr-${rIdx}`}
                            className="text-[10px] px-2.5 py-0.5 rounded-lg bg-indigo-950/70 border border-indigo-500/30 text-indigo-200 font-medium flex items-center space-x-1"
                          >
                            <span>✨</span>
                            <span>{reason}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* AI Rationale Badge */}
                  {place.ai_reasoning && (
                    <div className="mt-2.5 p-2.5 rounded-xl bg-slate-900/80 border border-slate-700/60 text-xs leading-relaxed shadow-sm">
                      <span className="font-semibold text-amber-300">Highlight: </span>
                      <span className="italic text-slate-200">{place.ai_reasoning}</span>
                    </div>
                  )}

                  {/* AI Time Estimation Explanation */}
                  {place.time_estimate_reason && (
                    <p className="text-[11px] text-slate-400 mt-1.5 italic">
                      <span className="text-indigo-400 font-semibold not-italic">Timing: </span>
                      {place.time_estimate_reason}
                    </p>
                  )}
                </div>
              </div>
            </React.Fragment>
          );
        })}

        {/* Return Transit Pill */}
        {places.length > 0 && (
          <div className="relative py-0.5">
            <div className="flex items-center space-x-2 text-[11px] font-medium text-slate-400 bg-slate-950/90 border border-slate-800/90 py-1.5 px-3 rounded-xl w-fit shadow-sm">
              <svg className="w-3.5 h-3.5 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              <span>
                {legs[places.length]?.duration_text || '15 mins'} drive back
                {legs[places.length]?.distance_text ? ` • ${legs[places.length]?.distance_text}` : ''}
              </span>
            </div>
          </div>
        )}

        {/* Final Step: Return */}
        <div className="relative group">
          <span className="absolute -left-6 sm:-left-7 top-1 w-5 h-5 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          </span>

          <div className="bg-slate-800/50 hover:bg-slate-800/80 border border-slate-700/60 rounded-2xl p-4 transition shadow-sm">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                Return • {endClock || 'Trip Conclusion'}
              </span>
              <span className="text-[11px] font-semibold text-slate-500">Conclusion</span>
            </div>
            <h4 className="text-sm font-bold text-white">Return to {startAddress}</h4>
            <p className="text-xs text-slate-400 mt-1">Conclude your journey safely back at the departure point.</p>
          </div>
        </div>
      </div>

      {/* Explainability Layer: Destination Alternatives & Tradeoffs */}
      {rejectedDestinations && rejectedDestinations.length > 0 && (
        <div className="mt-8 pt-6 border-t border-slate-800/80">
          <button
            type="button"
            onClick={() => setShowRejected(!showRejected)}
            className="w-full flex items-center justify-between p-3.5 rounded-2xl bg-slate-800/40 hover:bg-slate-800/70 border border-slate-700/60 text-xs text-slate-300 font-semibold transition cursor-pointer"
          >
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Destination Alternatives & Tradeoffs ({rejectedDestinations.length} evaluated)</span>
            </div>
            <span className="text-indigo-400 text-xs font-bold">
              {showRejected ? 'Hide ▲' : 'Show ▼'}
            </span>
          </button>

          {showRejected && (
            <div className="mt-3 space-y-2 p-3 bg-slate-950/50 border border-slate-800/80 rounded-2xl animate-fadeIn">
              <p className="text-[11px] text-slate-400 mb-2">
                These venues were scanned from the area but omitted to satisfy your schedule, transit efficiency, or category balance:
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
