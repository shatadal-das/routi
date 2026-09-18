import React from 'react';

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

export default function Timeline({
  startLocation,
  places = [],
  legs = [],
  totalTripTime = '',
  googleMapsUrl = '',
}) {
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
      <div className="flex flex-wrap items-center justify-between gap-3 pb-5 border-b border-slate-800/80 mb-6">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">Optimized Day Itinerary</h3>
          <p className="text-xs text-slate-400 font-medium mt-0.5">Balanced for minimal transit and generous stop time</p>
        </div>

        {totalTripTime && (
          <span className="text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/25 px-3 py-1.5 rounded-full">
            {totalTripTime} Total Experience
          </span>
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
                Departure Point
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
          const isRestaurant = place.type === 'restaurant';
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
                  className={`absolute -left-6 sm:-left-7 top-1 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                    isRestaurant
                      ? 'bg-amber-500/20 border-amber-400'
                      : 'bg-indigo-500/20 border-indigo-400'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isRestaurant ? 'bg-amber-400' : 'bg-indigo-400'
                    }`}
                  ></span>
                </span>

                <div
                  className={`border rounded-2xl p-4 transition shadow-sm ${
                    isRestaurant
                      ? 'bg-amber-950/15 hover:bg-amber-950/25 border-amber-800/40'
                      : 'bg-slate-800/50 hover:bg-slate-800/80 border-slate-700/60'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`text-[11px] font-bold uppercase tracking-wider ${
                          isRestaurant ? 'text-amber-400' : 'text-indigo-400'
                        }`}
                      >
                        {isRestaurant ? 'Curated Dining' : 'Featured Highlight'}
                      </span>
                      {isRestaurant && place.cuisine && (
                        <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30">
                          {place.cuisine}
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] font-semibold text-slate-500">Stop {stopNumber}</span>
                  </div>

                  <h4 className="text-sm font-bold text-white">
                    {place.name}
                  </h4>

                  {/* AI Estimated Duration Badge & Details */}
                  <div className="mt-2.5 flex flex-wrap items-center gap-2">
                    <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-indigo-950/70 border border-indigo-500/40 text-indigo-300 font-semibold text-xs shadow-sm">
                      <svg className="w-3.5 h-3.5 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>AI Estimated Stay: {place.duration_mins ? `${place.duration_mins} mins` : `${Math.round((place.duration_hours || 1.0) * 60)} mins`}</span>
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

                  {/* AI Rationale Badge */}
                  {place.ai_reasoning && (
                    <div className="mt-2.5 p-2.5 rounded-xl bg-indigo-950/60 border border-indigo-500/30 text-xs leading-relaxed shadow-sm">
                      <span className="font-semibold text-amber-300">✨ AI Chose this: </span>
                      <span className="italic text-indigo-100/90">{place.ai_reasoning}</span>
                    </div>
                  )}

                  {/* AI Time Estimation Explanation */}
                  {place.time_estimate_reason && (
                    <p className="text-[11px] text-slate-300/80 mt-1.5 italic bg-slate-950/40 border border-slate-800/60 px-2.5 py-1 rounded-xl">
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
                Return
              </span>
              <span className="text-[11px] font-semibold text-slate-500">Conclusion</span>
            </div>
            <h4 className="text-sm font-bold text-white">Return to {startAddress}</h4>
            <p className="text-xs text-slate-400 mt-1">Conclude your journey back at the departure point.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
