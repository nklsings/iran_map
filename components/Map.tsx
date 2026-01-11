"use client";

import React, { useState, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { Map as ReactMap } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { ProtestEvent } from '../lib/types';

const INITIAL_VIEW_STATE = {
  longitude: 53.6880,
  latitude: 32.4279,
  zoom: 5,
  pitch: 0,
  bearing: 0
};

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

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

interface MapProps {
  events: ProtestEvent[];
  onEventClick: (event: ProtestEvent) => void;
  showPPU?: boolean;
}

export default function Map({ events, onEventClick, showPPU = true }: MapProps) {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  // Separate events by type for different heatmap colors
  const { protestEvents, policeEvents } = useMemo(() => {
    const protestEvents = events.filter(e => e.properties.event_type !== 'police_presence');
    const policeEvents = events.filter(e => e.properties.event_type === 'police_presence');
    return { protestEvents, policeEvents };
  }, [events]);

  // Get color based on event type and verified status
  const getEventColor = (d: ProtestEvent): [number, number, number] => {
    const eventType = d.properties.event_type || 'protest';
    const colors = EVENT_COLORS[eventType] || EVENT_COLORS.protest;
    return d.properties.verified ? colors.verified : colors.unverified;
  };

  const layers = [
    // Protest heatmap (red)
    new HeatmapLayer({
      id: 'heatmap-layer-protest',
      data: protestEvents,
      pickable: false,
      getPosition: (d: ProtestEvent) => d.geometry.coordinates,
      getWeight: (d: ProtestEvent) => d.properties.intensity,
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
      getWeight: (d: ProtestEvent) => d.properties.intensity * 1.5, // Boost visibility
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
      radiusMaxPixels: 20,
      lineWidthMinPixels: 1,
      getPosition: (d: ProtestEvent) => d.geometry.coordinates,
      getFillColor: (d: ProtestEvent) => getEventColor(d),
      getLineColor: [0, 0, 0],
      onClick: (info) => {
        if (info.object) {
          onEventClick(info.object as ProtestEvent);
        }
      },
      updateTriggers: {
        getFillColor: events
      }
    })
  ].filter(Boolean);  // Remove null layers (when showPPU is false)

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

