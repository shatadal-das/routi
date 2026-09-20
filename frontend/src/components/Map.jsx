import React, { useState, useEffect, useCallback, useRef } from 'react';
import { GoogleMap, MarkerF, PolylineF, InfoWindowF } from '@react-google-maps/api';
import { decodePolyline } from '../utils/polyline';

const containerStyle = {
  width: '100%',
  height: '100%',
  borderRadius: '1rem',
};

// Sleek, light, and minimalist map styling matching brand palette
const lightMapStyle = [
  // 1. Soft off-white / brand-cream background landscape
  {
    elementType: 'geometry',
    stylers: [{ color: '#F8F5EE' }],
  },
  {
    elementType: 'labels.text.stroke',
    stylers: [{ color: '#ffffff' }, { weight: 2 }],
  },
  {
    elementType: 'labels.text.fill',
    stylers: [{ color: '#9ca3af' }],
  },
  {
    featureType: 'administrative',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#9ca3af' }],
  },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#9ca3af' }],
  },
  // 2. CRUCIAL CLUTTER FIX: Hide POIs and Transit
  {
    featureType: 'poi',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'transit',
    stylers: [{ visibility: 'off' }],
  },
  // 3. Roads & Highways - clean light styling
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#ffffff' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#e2e8f0' }],
  },
  {
    featureType: 'road',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#9ca3af' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#ffffff' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#cbd5e1' }],
  },
  // 4. Water - soft, pale blue
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#cadce8' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#9ca3af' }],
  },
  {
    featureType: 'administrative.land_parcel',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
];

// SVG Pin Path for high quality custom map pins
const PIN_SVG_PATH =
  'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z';

// SVG Icon Helpers with brand color palette and white halo border
const getStartMarkerIcon = () => ({
  path: PIN_SVG_PATH,
  fillColor: '#EB5134', // Departure & Return: brand-red
  fillOpacity: 1,
  strokeWeight: 2.5,
  strokeColor: '#ffffff',
  scale: 1.6,
  anchor: { x: 12, y: 22 },
});

const getRestaurantMarkerIcon = () => ({
  path: PIN_SVG_PATH,
  fillColor: '#F4A222', // Dining: brand-yellow
  fillOpacity: 1,
  strokeWeight: 2.5,
  strokeColor: '#ffffff',
  scale: 1.6,
  anchor: { x: 12, y: 22 },
});

const getAttractionMarkerIcon = () => ({
  path: PIN_SVG_PATH,
  fillColor: '#084A79', // Attractions: brand-navy
  fillOpacity: 1,
  strokeWeight: 2.5,
  strokeColor: '#ffffff',
  scale: 1.6,
  anchor: { x: 12, y: 22 },
});

function Map({
  startLocation,
  places = [],
  polyline = '',
  isLoaded = true,
  loadError = null,
}) {
  const [map, setMap] = useState(null);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [polylinePath, setPolylinePath] = useState([]);

  // Default coordinates (San Francisco) if none selected
  const defaultCenter = { lat: 37.7749, lng: -122.4194 };
  const currentCenter =
    startLocation && startLocation.lat && startLocation.lng
      ? { lat: startLocation.lat, lng: startLocation.lng }
      : defaultCenter;

  // Decode polyline whenever it changes
  useEffect(() => {
    if (polyline) {
      const decoded = decodePolyline(polyline);
      setPolylinePath(decoded);
    } else if (places.length > 0 && startLocation?.lat) {
      // Fallback path connecting stops directly if no polyline
      const path = [
        { lat: startLocation.lat, lng: startLocation.lng },
        ...places.map((p) => ({ lat: p.lat, lng: p.lng })),
        { lat: startLocation.lat, lng: startLocation.lng },
      ];
      setPolylinePath(path);
    } else {
      setPolylinePath([]);
    }
  }, [polyline, places, startLocation]);

  // Automatically adjust bounds to fit all markers
  const fitAllBounds = useCallback(() => {
    if (!map || !window.google) return;

    if ((!places || places.length === 0) && startLocation?.lat && startLocation?.lng) {
      map.panTo({ lat: Number(startLocation.lat), lng: Number(startLocation.lng) });
      map.setZoom(13);
      return;
    }

    const bounds = new window.google.maps.LatLngBounds();

    let hasPoints = false;
    if (startLocation?.lat && startLocation?.lng) {
      bounds.extend({ lat: Number(startLocation.lat), lng: Number(startLocation.lng) });
      hasPoints = true;
    }

    places.forEach((p) => {
      if (p.lat && p.lng) {
        bounds.extend({ lat: Number(p.lat), lng: Number(p.lng) });
        hasPoints = true;
      }
    });

    if (hasPoints) {
      map.fitBounds(bounds, { top: 60, right: 60, bottom: 60, left: 60 });
      // If only one point, avoid overzooming
      const listener = window.google.maps.event.addListenerOnce(map, 'idle', () => {
        if (map.getZoom() > 15) {
          map.setZoom(14);
        }
      });
    }
  }, [map, startLocation, places]);

  useEffect(() => {
    fitAllBounds();
  }, [fitAllBounds]);

  // Clear attraction popup if stops are cleared
  useEffect(() => {
    if (selectedMarker && selectedMarker.type !== 'start' && (!places || places.length === 0)) {
      setSelectedMarker(null);
    }
  }, [places, selectedMarker]);

  const onMapLoad = useCallback((mapInstance) => {
    setMap(mapInstance);
  }, []);

  const onMapUnmount = useCallback(() => {
    setMap(null);
  }, []);

  if (loadError) {
    return (
      <div className="w-full h-full min-h-[380px] bg-white border border-brand-navy/15 rounded-2xl flex flex-col items-center justify-center p-6 text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-brand-red/10 text-brand-red flex items-center justify-center mb-3">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <p className="text-brand-navy font-semibold">Unable to load Google Maps</p>
        <p className="text-slate-500 text-xs mt-1">Please verify your VITE_GOOGLE_MAPS_API_KEY.</p>
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div className="w-full h-full min-h-[380px] bg-white border border-brand-navy/15 rounded-2xl flex flex-col items-center justify-center p-6 animate-pulse shadow-sm">
        <div className="w-10 h-10 border-2 border-brand-teal border-t-transparent rounded-full animate-spin mb-3"></div>
        <span className="text-sm text-brand-navy font-medium">Loading Map Environment...</span>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full min-h-[380px] rounded-2xl overflow-hidden border border-brand-navy/15 shadow-sm bg-brand-cream">
      {/* Map Legend Floating Overlay */}
      <div className="absolute top-3 left-3 z-10 bg-white/90 backdrop-blur-md border border-brand-navy/15 rounded-xl px-3.5 py-2 text-xs flex items-center space-x-3.5 shadow-sm">
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#EB5134]"></span>
          <span className="text-brand-navy text-[11px] font-semibold">Departure</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#F4A222]"></span>
          <span className="text-brand-navy text-[11px] font-semibold">Dining</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#084A79]"></span>
          <span className="text-brand-navy text-[11px] font-semibold">Attractions</span>
        </div>
      </div>

      <GoogleMap
        mapContainerStyle={containerStyle}
        center={currentCenter}
        zoom={13}
        onLoad={onMapLoad}
        onUnmount={onMapUnmount}
        options={{
          styles: lightMapStyle,
          disableDefaultUI: false,
          zoomControl: true,
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: true,
        }}
      >
        {/* Starting Location Marker */}
        {startLocation?.lat && startLocation?.lng && (
          <MarkerF
            position={{ lat: startLocation.lat, lng: startLocation.lng }}
            icon={getStartMarkerIcon()}
            title="Departure & Return Point"
            zIndex={100}
            onClick={() =>
              setSelectedMarker({
                name: startLocation.address || 'Departure Location',
                type: 'start',
                address: startLocation.address || 'Starting point coordinates',
                lat: startLocation.lat,
                lng: startLocation.lng,
              })
            }
          />
        )}

        {/* POI Markers: Attractions & Restaurants */}
        {places.map((place, idx) => {
          const isRestaurant = place.type === 'restaurant' || place.is_meal_stop || !!place.meal_type;
          return (
            <MarkerF
              key={place.place_id || `marker-${idx}`}
              position={{ lat: place.lat, lng: place.lng }}
              icon={isRestaurant ? getRestaurantMarkerIcon() : getAttractionMarkerIcon()}
              title={`Stop ${idx + 1}: ${place.name} (${isRestaurant ? (place.meal_type || 'Dining') : 'Attraction'})`}
              zIndex={50}
              onClick={() => setSelectedMarker({ ...place, stop_number: idx + 1, isRestaurant })}
            />
          );
        })}

        {/* Route Polyline */}
        {polylinePath.length > 0 && (
          <PolylineF
            path={polylinePath}
            options={{
              strokeColor: '#10857E',
              strokeOpacity: 0.85,
              strokeWeight: 6,
            }}
          />
        )}

        {/* InfoWindow for Clicked Marker */}
        {selectedMarker && (
          <InfoWindowF
            position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }}
            onCloseClick={() => setSelectedMarker(null)}
          >
            <div className="p-1.5 max-w-xs text-slate-900 font-sans">
              <div className="flex items-center justify-between gap-1 mb-1">
                <span
                  className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                    selectedMarker.isRestaurant || selectedMarker.type === 'restaurant' || selectedMarker.meal_type
                      ? 'bg-amber-100 text-amber-900 border border-amber-200'
                      : selectedMarker.type === 'start'
                      ? 'bg-red-100 text-brand-red border border-red-200'
                      : 'bg-sky-100 text-brand-navy border border-sky-200'
                  }`}
                >
                  {selectedMarker.stop_number ? `Stop ${selectedMarker.stop_number} • ` : ''}
                  {selectedMarker.meal_type
                    ? `🍽️ ${selectedMarker.meal_type}`
                    : selectedMarker.isRestaurant || selectedMarker.type === 'restaurant'
                    ? '🍽️ Dining'
                    : selectedMarker.type === 'start'
                    ? '🕐 Departure Point'
                    : selectedMarker.category || 'Attraction'}
                </span>
                {selectedMarker.arrival_time && selectedMarker.departure_time && (
                  <span className="text-[10px] font-bold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded font-mono">
                    {selectedMarker.arrival_time}–{selectedMarker.departure_time}
                  </span>
                )}
              </div>

              <h4 className="font-bold text-sm text-slate-900 leading-tight mt-0.5">
                {selectedMarker.name}
              </h4>

              {selectedMarker.rating && (
                <p className="text-xs text-amber-600 font-semibold mt-1 flex items-center space-x-1">
                  <span className="text-brand-yellow">★</span>
                  <span>{Number(selectedMarker.rating).toFixed(1)} / 5.0</span>
                </p>
              )}

              {(selectedMarker.visit_duration || selectedMarker.visit_duration_minutes || selectedMarker.duration_mins) && (
                <p className="text-xs text-brand-navy font-semibold mt-0.5">
                  ⏱️ {selectedMarker.meal_type ? 'Meal Duration' : 'Visit Duration'}: {selectedMarker.visit_duration || selectedMarker.visit_duration_minutes || selectedMarker.duration_mins} mins
                </p>
              )}

              {selectedMarker.travel_time_from_previous > 0 && (
                <p className="text-[11px] text-slate-600 mt-0.5">
                  🚗 Travel from previous: {selectedMarker.travel_time_from_previous} mins
                </p>
              )}

              {(selectedMarker.selection_reasons?.length > 0 || selectedMarker.reason || selectedMarker.ai_reasoning) && (
                <p className="text-[11px] text-slate-700 italic mt-1 pt-1 border-t border-slate-200">
                  <span className="font-semibold text-slate-900 not-italic">Reason: </span>
                  {selectedMarker.selection_reasons?.join(' • ') || selectedMarker.reason || selectedMarker.ai_reasoning}
                </p>
              )}

              {selectedMarker.address && (
                <p className="text-[10px] text-slate-500 mt-1 truncate">
                  📍 {selectedMarker.address}
                </p>
              )}
            </div>
          </InfoWindowF>
        )}
      </GoogleMap>
    </div>
  );
}

export default React.memo(Map);
