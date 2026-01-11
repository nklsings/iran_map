"use client";

import React, { useState } from 'react';
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

interface MapProps {
  events: ProtestEvent[];
  onEventClick: (event: ProtestEvent) => void;
}

export default function Map({ events, onEventClick }: MapProps) {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  const layers = [
    new HeatmapLayer({
      id: 'heatmap-layer',
      data: events,
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
      getFillColor: (d: ProtestEvent) => d.properties.verified ? [255, 255, 255] : [255, 0, 0],
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
  ];

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

