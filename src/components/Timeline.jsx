import React, { useState } from 'react';
import { Star, Clock, Car, Utensils } from 'lucide-react';

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

const formatMinutesToHours = (mins) => {
  if (!mins || mins <= 0) return '0m';
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  if (h > 0 && m > 0) return `${h}h ${m}m`;
  if (h > 0) return `${h}h`;
  return `${m}m`;
};

/**
 * Replace snake_case or raw strings with clean Title Case
 */
function formatCategory(category = '') {
  if (!category) return '';
  return String(category)
    .replace(/_/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Simplify verbose price string (e.g. "$$ (Moderate)" -> "$$")
 */
function formatPrice(price = '') {
  if (!price) return '';
  const match = String(price).match(/^(\$+)/);
  if (match) return match[1];
  return String(price).split('(')[0].trim();
}

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
  bufferedEndClock = '',
  timeAccounting = null,
  rejectedDestinations = [],
  narrative = '',
  routeScore = null,
}) {
  const tAct = timeAccounting || {};
  const startTime = tAct.start_time || startClock || '09:30 AM';
  const actualReturnTime = tAct.actual_return_time || endClock || '—';
  const travelMins = tAct.travel_minutes ?? totalTravelMins;
  const visitMins = tAct.visit_minutes ?? totalDwellMins;
  const actualElapsedMins = tAct.actual_elapsed_minutes ?? (travelMins + visitMins);
  const totalDisplayTime = formatMinutesToHours(actualElapsedMins || totalDurationMins) || totalTripTime || '—';

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
    <div className="bg-white border border-gray-100 rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
      {/* Header & Minimalist Summary */}
      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h3 className="text-xl font-bold text-brand-navy tracking-tight">Your Itinerary</h3>
          <span className="text-xs sm:text-sm text-gray-600 font-semibold">
            Total Duration: {totalDisplayTime} • {places.length} {places.length === 1 ? 'Stop' : 'Stops'}
          </span>
        </div>

        {/* Narrative AI Story */}
        {narrative && (
          <p className="text-xs sm:text-sm text-brand-navy italic leading-relaxed pt-1">
            "{narrative}"
          </p>
        )}
      </div>

      {/* Full-width Sleek Google Maps Button at the Top */}
      <button
        id="open-google-maps-btn"
        type="button"
        onClick={handleOpenGoogleMaps}
        className="w-full py-3.5 px-6 bg-brand-navy text-white hover:opacity-95 font-bold rounded-full shadow-md hover:shadow-lg transition duration-200 flex items-center justify-center space-x-2 text-sm cursor-pointer"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
        <span>Open in Google Maps</span>
      </button>

      {/* Clean Timeline Flow with Subtle Cool Gray Track */}
      <div className="relative border-l-2 border-gray-200 ml-3.5 pl-6 pt-2 space-y-6">
        
        {/* START NODE */}
        <div className="relative">
          <div className="relative flex items-center text-xs font-bold tracking-widest text-brand-teal uppercase mb-1">
            <div className="absolute -left-[31px] w-3 h-3 rounded-full bg-white border-[2.5px] border-brand-navy z-10" />
            <span>{startTime}</span>
          </div>
          <h4 className="text-base font-semibold text-brand-navy">
            Depart from {startAddress}
          </h4>
        </div>

        {/* DESTINATIONS & TRANSIT LEGS */}
        {places.map((place, idx) => {
          const leg = legs[idx];
          const prevTravelMins = place.travel_time_from_previous || (leg ? parseInt(leg.duration_text) : 15);
          const travelDistanceText = leg ? leg.distance_text : '';
          const isRestaurant = place.is_meal_stop || place.type === 'restaurant' || !!place.meal_type;
          const visitDurationMins = place.visit_duration || place.visit_duration_minutes || place.duration_mins || 45;

          // Assemble human-readable metadata components
          const metadataItems = [];

          if (visitDurationMins) {
            metadataItems.push(
              <span key="duration" className="inline-flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                <span>{visitDurationMins} mins</span>
              </span>
            );
          }

          if (place.rating) {
            metadataItems.push(
              <span key="rating" className="inline-flex items-center gap-1">
                <Star className="w-3.5 h-3.5 text-brand-yellow fill-brand-yellow shrink-0" />
                <span className="font-semibold text-gray-700">{Number(place.rating).toFixed(1)}</span>
              </span>
            );
          }

          const priceFormatted = formatPrice(place.price_level || place.price);
          if (priceFormatted) {
            metadataItems.push(
              <span key="price" className="font-semibold text-gray-700">
                {priceFormatted}
              </span>
            );
          }

          const rawCategory = isRestaurant
            ? (place.meal_type || place.cuisine || 'Dining')
            : (place.category || place.type || 'Sight');
          const categoryFormatted = formatCategory(rawCategory);

          if (categoryFormatted) {
            metadataItems.push(
              <span key="category">{categoryFormatted}</span>
            );
          }

          const selectionReason =
            (place.selection_reasons && place.selection_reasons.length > 0)
              ? place.selection_reasons.join(' • ')
              : place.reason || place.ai_reasoning;

          return (
            <React.Fragment key={place.place_id || place.id || `stop-${idx}`}>
              {/* TRAVEL TRANSITION PILL */}
              <div className="my-2 -ml-2">
                <div className="inline-flex items-center gap-2 bg-white border border-gray-100 shadow-sm rounded-full px-3 py-1 text-xs text-gray-500">
                  <Car className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                  <span>{prevTravelMins} mins travel</span>
                  {travelDistanceText && <span className="text-gray-300">•</span>}
                  {travelDistanceText && <span>{travelDistanceText}</span>}
                </div>
              </div>

              {/* DESTINATION NODE */}
              <div className="relative">
                <div className="space-y-1">
                  {/* Elegant Tracking-Wide Overline Time with Ring Center-Aligned */}
                  <div className="relative flex items-center text-xs font-bold tracking-widest text-brand-teal uppercase mb-1">
                    <div
                      className={`absolute -left-[31px] w-3 h-3 rounded-full z-10 ${
                        isRestaurant
                          ? 'bg-[#FFF8EE] border-[2.5px] border-brand-yellow ring-2 ring-brand-yellow/20'
                          : 'bg-white border-[2.5px] border-brand-navy'
                      }`}
                    />
                    <span>
                      {place.arrival_time && place.departure_time
                        ? `${place.arrival_time} – ${place.departure_time}`
                        : (place.arrival_time || startTime)}
                    </span>
                  </div>

                  {/* Destination Name with Dining Badge if Food Stop */}
                  <div className="flex items-center flex-wrap gap-2">
                    <h3 className="text-base font-semibold text-brand-navy tracking-tight leading-snug">
                      {place.name}
                    </h3>
                    {isRestaurant && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-brand-yellow/15 text-amber-900 border border-brand-yellow/30">
                        <Utensils className="w-3 h-3 text-brand-yellow shrink-0" />
                        <span>{formatCategory(place.meal_type) || 'Dining'}</span>
                      </span>
                    )}
                  </div>

                  {/* Refined Flexbox Metadata Row */}
                  <div className="flex items-center flex-wrap gap-1.5 text-sm text-gray-500 mt-1">
                    {metadataItems.map((item, itemIdx) => (
                      <React.Fragment key={itemIdx}>
                        {itemIdx > 0 && <span className="text-gray-300">•</span>}
                        {item}
                      </React.Fragment>
                    ))}
                  </div>

                  {/* Receding Physical Address */}
                  {place.address && (
                    <p className="text-xs text-gray-400 mt-0.5 truncate">
                      {place.address}
                    </p>
                  )}

                  {/* AI Reasoning Soft Container Block */}
                  {selectionReason && (
                    <div className="mt-2.5 bg-slate-50 border border-slate-100 rounded-lg p-2.5 text-xs text-slate-600 italic flex items-start gap-2 leading-relaxed">
                      <span className="shrink-0 text-brand-teal select-none not-italic text-xs">✨</span>
                      <span>{selectionReason}</span>
                    </div>
                  )}
                </div>
              </div>
            </React.Fragment>
          );
        })}

        {/* RETURN TRANSIT LEG PILL */}
        {places.length > 0 && (
          (() => {
            const returnLeg = legs[places.length];
            const returnTravelMins = returnLeg?.duration_mins || (returnLeg ? parseInt(returnLeg.duration_text) : 15);
            const returnDistanceText = returnLeg ? returnLeg.distance_text : '';

            return (
              <div className="my-2 -ml-2">
                <div className="inline-flex items-center gap-2 bg-white border border-gray-100 shadow-sm rounded-full px-3 py-1 text-xs text-gray-500">
                  <Car className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                  <span>{returnTravelMins} mins travel</span>
                  {returnDistanceText && <span className="text-gray-300">•</span>}
                  {returnDistanceText && <span>{returnDistanceText}</span>}
                </div>
              </div>
            );
          })()
        )}

        {/* RETURN NODE */}
        <div className="relative">
          <div className="relative flex items-center text-xs font-bold tracking-widest text-brand-teal uppercase mb-1">
            <div className="absolute -left-[31px] w-3 h-3 rounded-full bg-white border-[2.5px] border-brand-navy z-10" />
            <span>{actualReturnTime}</span>
          </div>
          <h4 className="text-base font-semibold text-brand-navy">
            Return to {startAddress}
          </h4>
        </div>

      </div>

      {/* Collapsible Candidate Alternatives (Minimalist) */}
      {rejectedDestinations && rejectedDestinations.length > 0 && (
        <div className="pt-4 border-t border-gray-100">
          <button
            type="button"
            onClick={() => setShowRejected(!showRejected)}
            className="w-full flex items-center justify-between text-xs text-gray-500 hover:text-brand-navy transition cursor-pointer"
          >
            <span>{rejectedDestinations.length} alternative places considered</span>
            <span className="font-semibold">{showRejected ? 'Hide −' : 'View +'}</span>
          </button>

          {showRejected && (
            <div className="mt-3 space-y-2 pt-2 divide-y divide-gray-100">
              {rejectedDestinations.map((cand, idx) => (
                <div key={`rej-${idx}`} className="pt-2 flex items-center justify-between text-xs">
                  <span className="text-gray-600 font-medium">{cand.place}</span>
                  <span className="text-[11px] text-gray-400">
                    {(cand.rejection_reasons || []).join(', ')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
