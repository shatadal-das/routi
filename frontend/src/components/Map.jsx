import React, { useState, useEffect, useCallback, useRef } from 'react';
import { GoogleMap, MarkerF, PolylineF, InfoWindowF } from '@react-google-maps/api';
import { decodePolyline } from '../utils/polyline';

const containerStyle = {
  width: '100%',
  height: '100%',
  minHeight: '520px',
  borderRadius: '1rem',
};

// Sleek dark mode map styling
const darkMapStyle = [
  { elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#1e293b' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#94a3b8' }] },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#cbd5e1' }],
  },
  {
    featureType: 'poi',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#64748b' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'geometry',
    stylers: [{ color: '#0f172a' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#334155' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#1e293b' }],
  },
  {
    featureType: 'road',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#94a3b8' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#475569' }],
  },
  {
    featureType: 'transit',
    elementType: 'geometry',
    stylers: [{ color: '#1e293b' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#090d16' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#475569' }],
  },
];

// SVG Pin Path for high quality custom map pins
const PIN_SVG_PATH =
  'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z';

// SVG Icon Helpers
const getStartMarkerIcon = () => ({
  path: PIN_SVG_PATH,
  fillColor: '#10b981', // Emerald green
  fillOpacity: 1,
  strokeWeight: 2,
  strokeColor: '#ffffff',
  scale: 1.6,
  anchor: { x: 12, y: 22 },
});

const getRestaurantMarkerIcon = () => ({
  path: PIN_SVG_PATH,
  fillColor: '#f59e0b', // Amber / Orange
  fillOpacity: 1,
  strokeWeight: 2,
  strokeColor: '#ffffff',
  scale: 1.6,
  anchor: { x: 12, y: 22 },
});

const getAttractionMarkerIcon = () => ({
  path: PIN_SVG_PATH,
  fillColor: '#6366f1', // Indigo / Purple
  fillOpacity: 1,
  strokeWeight: 2,
  strokeColor: '#ffffff',
  scale: 1.6,
  anchor: { x: 12, y: 22 },
});

export default function Map({
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
    const bounds = new window.google.maps.LatLngBounds();

    let hasPoints = false;
    if (startLocation?.lat && startLocation?.lng) {
      bounds.extend({ lat: startLocation.lat, lng: startLocation.lng });
      hasPoints = true;
    }

    places.forEach((p) => {
      if (p.lat && p.lng) {
        bounds.extend({ lat: p.lat, lng: p.lng });
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

  const onMapLoad = useCallback((mapInstance) => {
    setMap(mapInstance);
  }, []);

  const onMapUnmount = useCallback(() => {
    setMap(null);
  }, []);

  if (loadError) {
    return (
      <div className="w-full h-full min-h-[520px] bg-slate-900 border border-slate-800 rounded-2xl flex flex-col items-center justify-center p-6 text-center">
        <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center mb-3">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <p className="text-slate-300 font-semibold">Unable to load Google Maps</p>
        <p className="text-slate-500 text-xs mt-1">Please verify your VITE_GOOGLE_MAPS_API_KEY.</p>
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div className="w-full h-full min-h-[520px] bg-slate-900/60 border border-slate-800 rounded-2xl flex flex-col items-center justify-center p-6 animate-pulse">
        <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-3"></div>
        <span className="text-sm text-slate-400">Loading Map Environment...</span>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full min-h-[520px] rounded-2xl overflow-hidden border border-slate-800 shadow-2xl bg-slate-950">
      {/* Map Legend Floating Overlay */}
      <div className="absolute top-3 left-3 z-10 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-xl px-3.5 py-2 text-xs flex items-center space-x-3.5 shadow-lg">
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
          <span className="text-slate-300 text-[11px] font-medium">Departure & Return</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
          <span className="text-slate-300 text-[11px] font-medium">Curated Dining</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
          <span className="text-slate-300 text-[11px] font-medium">Attractions</span>
        </div>
      </div>

      <GoogleMap
        mapContainerStyle={containerStyle}
        center={currentCenter}
        zoom={13}
        onLoad={onMapLoad}
        onUnmount={onMapUnmount}
        options={{
          styles: darkMapStyle,
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
          const isRestaurant = place.type === 'restaurant';
          return (
            <MarkerF
              key={place.place_id || `marker-${idx}`}
              position={{ lat: place.lat, lng: place.lng }}
              icon={isRestaurant ? getRestaurantMarkerIcon() : getAttractionMarkerIcon()}
              title={`${place.name} (${isRestaurant ? 'Dining' : 'Attraction'})`}
              onClick={() => setSelectedMarker(place)}
            />
          );
        })}

        {/* Route Polyline */}
        {polylinePath.length > 0 && (
          <PolylineF
            path={polylinePath}
            options={{
              strokeColor: '#6366f1',
              strokeOpacity: 0.9,
              strokeWeight: 5,
            }}
          />
        )}

        {/* InfoWindow for Clicked Marker */}
        {selectedMarker && (
          <InfoWindowF
            position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }}
            onCloseClick={() => setSelectedMarker(null)}
          >
            <div className="p-1 max-w-xs text-slate-900">
              <span
                className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full mb-1 ${
                  selectedMarker.type === 'restaurant'
                    ? 'bg-amber-100 text-amber-800'
                    : selectedMarker.type === 'start'
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-indigo-100 text-indigo-800'
                }`}
              >
                {selectedMarker.type === 'restaurant'
                  ? 'Curated Dining'
                  : selectedMarker.type === 'start'
                  ? 'Departure & Return'
                  : 'Featured Highlight'}
              </span>
              <h4 className="font-bold text-sm text-slate-900 leading-tight">
                {selectedMarker.name}
              </h4>
              {selectedMarker.rating && (
                <p className="text-xs text-amber-600 font-semibold mt-0.5">
                  ★ {Number(selectedMarker.rating).toFixed(1)} / 5.0
                </p>
              )}
              {(selectedMarker.duration_mins || selectedMarker.duration_hours) && (
                <p className="text-xs text-indigo-700 font-semibold mt-0.5">
                  ⏱️ AI Estimated Stay: {selectedMarker.duration_mins ? `${selectedMarker.duration_mins} mins` : `${selectedMarker.duration_hours || 1.0} hr`}
                </p>
              )}
              {selectedMarker.time_estimate_reason && (
                <p className="text-[11px] text-slate-600 italic mt-0.5">
                  {selectedMarker.time_estimate_reason}
                </p>
              )}
              {selectedMarker.address && (
                <p className="text-[11px] text-slate-500 mt-1 truncate">
                  {selectedMarker.address}
                </p>
              )}
            </div>
          </InfoWindowF>
        )}
      </GoogleMap>
    </div>
  );
}
