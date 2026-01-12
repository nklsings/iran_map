"use client";

import React, { useState, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer, PolygonLayer } from '@deck.gl/layers';
import { Map as ReactMap } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { ProtestEvent, AirspaceEvent, AirspaceType, ProvinceConnectivity, ConnectivityStatus, CONNECTIVITY_STATUS_CONFIG } from '../lib/types';

const INITIAL_VIEW_STATE = {
  longitude: 53.6880,
  latitude: 32.4279,
  zoom: 5,
  pitch: 0,
  bearing: 0
};

// Map style options:
// - dark-matter: Very dark (default CartoDB)
// - alidade_smooth_dark: Slightly lighter dark gray (Stadia)
// - dark-matter-nolabels: Dark without labels
const MAP_STYLE = "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json";

// Color scheme for different event types
const EVENT_COLORS = {
  protest: {
    unverified: [255, 0, 0] as [number, number, number],      // Red
    verified: [255, 255, 255] as [number, number, number],    // White
  },
  police_presence: {
    unverified: [0, 150, 255] as [number, number, number],    // Blue (PPU)
    verified: [0, 200, 255] as [number, number, number],      // Light Blue
  },
  clash: {
    unverified: [255, 100, 0] as [number, number, number],    // Orange
    verified: [255, 200, 100] as [number, number, number],    // Light Orange
  },
  arrest: {
    unverified: [150, 0, 150] as [number, number, number],    // Purple
    verified: [200, 100, 200] as [number, number, number],    // Light Purple
  },
  strike: {
    unverified: [255, 200, 0] as [number, number, number],    // Yellow
    verified: [255, 255, 150] as [number, number, number],    // Light Yellow
  },
};

// Airspace colors by type
const AIRSPACE_COLORS: Record<AirspaceType, { fill: [number, number, number, number]; line: [number, number, number] }> = {
  airspace_restriction: { fill: [255, 68, 68, 80], line: [255, 68, 68] },
  airport_closure: { fill: [255, 136, 0, 80], line: [255, 136, 0] },
  hazard_notice: { fill: [255, 204, 0, 80], line: [255, 204, 0] },
  temporary_restriction: { fill: [255, 0, 136, 80], line: [255, 0, 136] },
  warning_area: { fill: [136, 0, 255, 80], line: [136, 0, 255] },
};

// Connectivity colors by status - matches CONNECTIVITY_STATUS_CONFIG
const CONNECTIVITY_COLORS: Record<ConnectivityStatus, { fill: [number, number, number, number]; line: [number, number, number] }> = {
  normal: { fill: [34, 197, 94, 60], line: [34, 197, 94] },
  degraded: { fill: [234, 179, 8, 80], line: [234, 179, 8] },
  restricted: { fill: [249, 115, 22, 100], line: [249, 115, 22] },
  blackout: { fill: [239, 68, 68, 120], line: [239, 68, 68] },
  unknown: { fill: [107, 114, 128, 50], line: [107, 114, 128] },
};

interface MapProps {
  events: ProtestEvent[];
  onEventClick: (event: ProtestEvent) => void;
  showPPU?: boolean;
  airspaceData?: AirspaceEvent[];
  showAirspace?: boolean;
  onAirspaceClick?: (event: AirspaceEvent) => void;
  connectivityData?: ProvinceConnectivity[];
  showConnectivity?: boolean;
  onConnectivityClick?: (province: ProvinceConnectivity) => void;
}

export default function Map({ 
  events, 
  onEventClick, 
  showPPU = true,
  airspaceData = [],
  showAirspace = true,
  onAirspaceClick,
  connectivityData = [],
  showConnectivity = false,
  onConnectivityClick
}: MapProps) {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  // Separate events by type for different heatmap colors
  const { protestEvents, policeEvents } = useMemo(() => {
    const protestEvents = events.filter(e => e.properties.event_type !== 'police_presence');
    const policeEvents = events.filter(e => e.properties.event_type === 'police_presence');
    return { protestEvents, policeEvents };
  }, [events]);

  // Get airspace colors based on type
  const getAirspaceFillColor = (d: AirspaceEvent): [number, number, number, number] => {
    const airspaceType = d.properties.airspace_type || 'airspace_restriction';
    return AIRSPACE_COLORS[airspaceType]?.fill || AIRSPACE_COLORS.airspace_restriction.fill;
  };

  const getAirspaceLineColor = (d: AirspaceEvent): [number, number, number] => {
    const airspaceType = d.properties.airspace_type || 'airspace_restriction';
    return AIRSPACE_COLORS[airspaceType]?.line || AIRSPACE_COLORS.airspace_restriction.line;
  };

  // Get connectivity colors based on status
  const getConnectivityFillColor = (d: ProvinceConnectivity): [number, number, number, number] => {
    const status = d.properties.status || 'unknown';
    return CONNECTIVITY_COLORS[status]?.fill || CONNECTIVITY_COLORS.unknown.fill;
  };

  const getConnectivityLineColor = (d: ProvinceConnectivity): [number, number, number] => {
    const status = d.properties.status || 'unknown';
    return CONNECTIVITY_COLORS[status]?.line || CONNECTIVITY_COLORS.unknown.line;
  };

  // Get connectivity radius based on population (larger cities = larger circles)
  const getConnectivityRadius = (d: ProvinceConnectivity): number => {
    const pop = d.properties.population || 500000;
    if (pop > 5000000) return 40;  // Tehran
    if (pop > 2000000) return 30;  // Major cities
    if (pop > 1000000) return 25;
    if (pop > 500000) return 20;
    return 15;  // Smaller provinces
  };

  // Get color based on event type and verified status
  const getEventColor = (d: ProtestEvent): [number, number, number] => {
    const eventType = d.properties.event_type || 'protest';
    const colors = EVENT_COLORS[eventType] || EVENT_COLORS.protest;
    return d.properties.verified ? colors.verified : colors.unverified;
  };

  // Get radius based on cluster size
  const getEventRadius = (d: ProtestEvent): number => {
    const count = d.properties.cluster_count || 1;
    if (count === 1) return 3;
    if (count <= 3) return 5;
    if (count <= 5) return 7;
    if (count <= 10) return 9;
    return Math.min(12, 9 + Math.log2(count)); // Logarithmic scaling for large clusters
  };

  const layers = [
    // Airspace restrictions layer (render first/bottom - below everything else)
    showAirspace && airspaceData.length > 0 && new PolygonLayer({
      id: 'airspace-layer',
      data: airspaceData.filter(d => d.geometry.type === 'Polygon'),
      pickable: true,
      stroked: true,
      filled: true,
      extruded: false,
      wireframe: false,
      lineWidthMinPixels: 2,
      getPolygon: (d: AirspaceEvent) => {
        // GeoJSON Polygon coordinates are [[[lon, lat], ...]]
        const coords = d.geometry.coordinates as number[][][];
        return coords[0]; // First ring of polygon
      },
      getFillColor: getAirspaceFillColor,
      getLineColor: getAirspaceLineColor,
      getLineWidth: 2,
      onClick: (info) => {
        if (info.object && onAirspaceClick) {
          onAirspaceClick(info.object as AirspaceEvent);
        }
      },
      updateTriggers: {
        getFillColor: airspaceData,
        getLineColor: airspaceData
      }
    }),
    // Connectivity layer (above airspace, clickable)
    showConnectivity && connectivityData.length > 0 && new ScatterplotLayer({
      id: 'connectivity-layer',
      data: connectivityData,
      pickable: true,
      opacity: 0.85,
      stroked: true,
      filled: true,
      radiusScale: 1,
      radiusMinPixels: 18,
      radiusMaxPixels: 55,
      lineWidthMinPixels: 3,
      getPosition: (d: ProvinceConnectivity) => d.geometry.coordinates,
      getRadius: getConnectivityRadius,
      getFillColor: getConnectivityFillColor,
      getLineColor: getConnectivityLineColor,
      getLineWidth: 3,
      onClick: (info) => {
        if (info.object && onConnectivityClick) {
          onConnectivityClick(info.object as ProvinceConnectivity);
        }
      },
      updateTriggers: {
        getFillColor: connectivityData,
        getLineColor: connectivityData,
        getRadius: connectivityData
      }
    }),
    // Protest heatmap (red)
    new HeatmapLayer({
      id: 'heatmap-layer-protest',
      data: protestEvents,
      pickable: false,
      getPosition: (d: ProtestEvent) => d.geometry.coordinates,
      getWeight: (d: ProtestEvent) => d.properties.intensity * (d.properties.cluster_count || 1),
      radiusPixels: 30,
      intensity: 1,
      threshold: 0.05,
      colorRange: [
        [255, 255, 255, 0],   // Transparent
        [200, 0, 0, 50],      // Faint Red
        [220, 0, 0, 100],
        [240, 0, 0, 150],
        [255, 0, 0, 200],     // Bright Red
        [255, 255, 255, 255]  // White hot
      ],
    }),
    // Police presence heatmap (blue) - PPU
    showPPU && new HeatmapLayer({
      id: 'heatmap-layer-police',
      data: policeEvents,
      pickable: false,
      getPosition: (d: ProtestEvent) => d.geometry.coordinates,
      getWeight: (d: ProtestEvent) => d.properties.intensity * 1.5 * (d.properties.cluster_count || 1),
      radiusPixels: 40,
      intensity: 1.2,
      threshold: 0.03,
      colorRange: [
        [255, 255, 255, 0],   // Transparent
        [0, 100, 200, 50],    // Faint Blue
        [0, 120, 220, 100],
        [0, 150, 240, 150],
        [0, 180, 255, 200],   // Bright Blue
        [150, 220, 255, 255]  // Light Blue hot
      ],
    }),
    new ScatterplotLayer({
      id: 'scatterplot-layer',
      data: events,
      pickable: true,
      opacity: 0.8,
      stroked: true,
      filled: true,
      radiusScale: 1000,
      radiusMinPixels: 5,
      radiusMaxPixels: 30,  // Increased for clusters
      lineWidthMinPixels: 1,
      getPosition: (d: ProtestEvent) => d.geometry.coordinates,
      getRadius: (d: ProtestEvent) => getEventRadius(d),
      getFillColor: (d: ProtestEvent) => getEventColor(d),
      getLineColor: (d: ProtestEvent) => d.properties.is_cluster ? [255, 255, 255] : [0, 0, 0],
      getLineWidth: (d: ProtestEvent) => d.properties.is_cluster ? 2 : 1,
      onClick: (info) => {
        if (info.object) {
          onEventClick(info.object as ProtestEvent);
        }
      },
      updateTriggers: {
        getFillColor: events,
        getRadius: events,
        getLineColor: events,
        getLineWidth: events
      }
    })
  ].filter(Boolean);  // Remove null layers (when showPPU is false or no airspace)

  return (
    <div className="relative w-full h-full">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState }: any) => setViewState(viewState)}
        controller={true}
        layers={layers}
      >
        <ReactMap
          mapStyle={MAP_STYLE}
          reuseMaps
        />
      </DeckGL>
    </div>
  );
}

