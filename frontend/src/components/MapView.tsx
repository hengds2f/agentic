import { useRef, useEffect } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Itinerary } from '../types';

interface Props {
  itinerary: Itinerary;
}

export default function MapView({ itinerary }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapRef.current) return;

    // Clean up previous map
    if (mapInstance.current) {
      mapInstance.current.remove();
      mapInstance.current = null;
    }

    // Collect city waypoints
    const cities = itinerary.cities || [];

    // Collect all item coordinates
    const allCoords: [number, number][] = [];
    itinerary.days.forEach(day => {
      day.items.forEach(item => {
        if (item.latitude && item.longitude && item.latitude !== 0 && item.longitude !== 0) {
          allCoords.push([item.latitude, item.longitude]);
        }
      });
    });

    // Build waypoints from cities or from per-day item coords
    const waypoints: { name: string; lat: number; lon: number; dayLabel: string }[] = [];

    if (cities.length > 0) {
      cities.forEach((city, i) => {
        if (city.lat && city.lon) {
          waypoints.push({ name: city.name, lat: city.lat, lon: city.lon, dayLabel: `Stop ${i + 1}` });
        }
      });
    }

    if (waypoints.length === 0) {
      // Fallback: use first coord from each day
      const seenKeys = new Set<string>();
      itinerary.days.forEach(day => {
        const item = day.items.find(
          i => i.latitude && i.longitude && i.latitude !== 0 && i.longitude !== 0
        );
        if (item) {
          const key = `${item.latitude.toFixed(2)},${item.longitude.toFixed(2)}`;
          if (!seenKeys.has(key)) {
            seenKeys.add(key);
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

    // Determine center
    let center: [number, number] = [35.68, 139.69]; // default Tokyo
    if (waypoints.length > 0) {
      center = [waypoints[0].lat, waypoints[0].lon];
    } else if (allCoords.length > 0) {
      center = allCoords[0];
    }

    const map = L.map(mapRef.current).setView(center, 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    const boundsArr: [number, number][] = [];

    // Add numbered markers
    waypoints.forEach((wp, idx) => {
      const icon = L.divIcon({
        className: '',
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

      boundsArr.push([wp.lat, wp.lon]);
    });

    // Draw route polyline
    if (boundsArr.length > 1) {
      L.polyline(boundsArr, {
        color: '#2563eb',
        weight: 3,
        opacity: 0.7,
        dashArray: '10, 8',
      }).addTo(map);
    }

    // Add small dots for individual POIs
    allCoords.forEach(coord => {
      L.circleMarker(coord, {
        radius: 4,
        fillColor: '#f97316',
        color: '#fff',
        weight: 1,
        fillOpacity: 0.8,
      }).addTo(map);
    });

    // Fit bounds
    const allBounds = [...boundsArr, ...allCoords];
    if (allBounds.length > 1) {
      map.fitBounds(allBounds as L.LatLngBoundsExpression, { padding: [40, 40] });
    } else if (allBounds.length === 1) {
      map.setView(allBounds[0], 11);
    }

    // Force a size recalc after render
    setTimeout(() => map.invalidateSize(), 100);

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
