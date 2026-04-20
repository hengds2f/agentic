import { useRef, useEffect } from 'react';
import type { Itinerary } from '../types';

/* Leaflet is loaded via CDN in index.html */
declare const L: any;

interface Props {
  itinerary: Itinerary;
}

export default function MapView({ itinerary }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);

  useEffect(() => {
    if (!mapRef.current || typeof L === 'undefined') return;

    // Clean up previous map
    if (mapInstance.current) {
      mapInstance.current.remove();
      mapInstance.current = null;
    }

    // Collect city waypoints from the itinerary
    const cities = itinerary.cities || [];

    // Also collect all item coordinates as fallback
    const allCoords: [number, number][] = [];
    itinerary.days.forEach(day => {
      day.items.forEach(item => {
        if (item.latitude && item.longitude && item.latitude !== 0 && item.longitude !== 0) {
          allCoords.push([item.latitude, item.longitude]);
        }
      });
    });

    // If we have city waypoints, use those; otherwise use item coords
    const waypoints: { name: string; lat: number; lon: number; dayLabel: string }[] = [];

    if (cities.length > 0) {
      cities.forEach((city, i) => {
        waypoints.push({ name: city.name, lat: city.lat, lon: city.lon, dayLabel: `Stop ${i + 1}` });
      });
    } else {
      // Group first coord per day
      const seenCities = new Set<string>();
      itinerary.days.forEach(day => {
        const item = day.items.find(
          i => i.latitude && i.longitude && i.latitude !== 0 && i.longitude !== 0
        );
        if (item) {
          const key = `${item.latitude.toFixed(2)},${item.longitude.toFixed(2)}`;
          if (!seenCities.has(key)) {
            seenCities.add(key);
            waypoints.push({
              name: item.location || day.title,
              lat: item.latitude,
              lon: item.longitude,
              dayLabel: `Day ${day.day}`,
            });
          }
        }
      });
    }

    if (waypoints.length === 0 && allCoords.length === 0) return;

    const center: [number, number] =
      waypoints.length > 0
        ? [waypoints[0].lat, waypoints[0].lon]
        : allCoords[0];

    const map = L.map(mapRef.current).setView(center, 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    const bounds: [number, number][] = [];

    // Add numbered markers for each city
    waypoints.forEach((wp, idx) => {
      const icon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="
          background: #2563eb;
          color: white;
          border-radius: 50%;
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: 14px;
          border: 3px solid white;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        ">${idx + 1}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      L.marker([wp.lat, wp.lon], { icon })
        .addTo(map)
        .bindPopup(`<b>${wp.dayLabel}</b><br>${wp.name}`);

      bounds.push([wp.lat, wp.lon]);
    });

    // Draw route polyline between waypoints
    if (bounds.length > 1) {
      L.polyline(bounds, {
        color: '#2563eb',
        weight: 3,
        opacity: 0.7,
        dashArray: '10, 8',
      }).addTo(map);
    }

    // Also add small dots for individual POIs
    allCoords.forEach(coord => {
      L.circleMarker(coord, {
        radius: 4,
        fillColor: '#f97316',
        color: '#fff',
        weight: 1,
        fillOpacity: 0.8,
      }).addTo(map);
    });

    // Fit map to all markers
    const allBounds = [...bounds, ...allCoords];
    if (allBounds.length > 1) {
      map.fitBounds(allBounds, { padding: [40, 40] });
    }

    mapInstance.current = map;

    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [itinerary]);

  const cities = itinerary.cities || [];

  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-lg">🗺️ Route Map</h3>

      {/* City route summary */}
      {cities.length > 1 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="text-sm font-medium text-blue-800 mb-2">Touring Route</div>
          <div className="flex items-center flex-wrap gap-1 text-sm">
            {cities.map((city, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="inline-flex items-center justify-center w-5 h-5 bg-blue-600 text-white text-xs rounded-full font-bold">
                  {i + 1}
                </span>
                <span className="text-blue-900">{city.name}</span>
                {i < cities.length - 1 && <span className="text-blue-400 mx-1">→</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Leaflet map */}
      <div
        ref={mapRef}
        style={{ height: '500px', borderRadius: '12px', overflow: 'hidden' }}
        className="border border-gray-200 shadow-sm"
      />

      {/* Google Maps link */}
      {itinerary.map_url && (
        <a
          href={itinerary.map_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition text-sm font-medium"
        >
          🗺️ Open Route in Google Maps ↗
        </a>
      )}
    </div>
  );
}
