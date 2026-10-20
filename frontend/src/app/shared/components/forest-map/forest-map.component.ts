import {
  AfterViewInit,
  ChangeDetectorRef,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
  inject,
} from '@angular/core';
import { CommonModule, DOCUMENT } from '@angular/common';
import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from 'geojson';
import maplibregl, { GeoJSONSource, LngLatBoundsLike, Map, Marker, NavigationControl } from 'maplibre-gl';

import { CoordinateResponse, GeometryPayload } from '../../../core/api.models';
import { BasemapMode, defaultBasemapMode, hasPremiumBasemap, resolveBasemapStyle } from '../../../core/map-style.config';

type CoordinateNode = number | CoordinateNode[];

@Component({
  selector: 'app-forest-map',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      #frameContainer
      class="map-fullscreen-shell relative overflow-hidden rounded-[2rem] border border-white/10 bg-[#09151b] shadow-2xl shadow-black/30"
      [class.map-fullscreen-active]="fullscreenActive"
    >
      <div class="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <p class="text-xs uppercase tracking-[0.3em] text-emerald-200/60">Geo-Intelligence</p>
          <h3 class="font-display text-lg text-white">{{ title }}</h3>
        </div>
        <div class="flex items-center gap-3">
          <button
            *ngIf="allowFullscreen"
            type="button"
            class="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-200 transition hover:border-cyan-300/30 hover:bg-white/10"
            (click)="toggleFullscreen()"
          >
            {{ fullscreenActive ? 'Exit Full Screen' : 'Full Screen' }}
          </button>
          <div class="hidden rounded-full border border-white/10 bg-white/5 p-1 sm:inline-flex">
            <button
              type="button"
              class="rounded-full px-3 py-1 text-xs transition"
              [class]="basemapMode === 'hybrid' ? 'bg-white text-slate-950' : 'text-stone-300 hover:text-white'"
              (click)="switchBasemap('hybrid')"
            >
              Hybrid
            </button>
            <button
              type="button"
              class="rounded-full px-3 py-1 text-xs transition"
              [class]="basemapMode === 'street' ? 'bg-white text-slate-950' : 'text-stone-300 hover:text-white'"
              (click)="switchBasemap('street')"
            >
              Street
            </button>
          </div>
          <span class="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
            {{ sensorLocation ? 'Sensor linked' : 'Forest boundary only' }}
          </span>
        </div>
      </div>

      <div *ngIf="!premiumBasemapEnabled" class="border-b border-white/10 bg-white/5 px-5 py-3 text-xs text-stone-300">
        Demo basemap active. Add a MapTiler API key in the frontend config to unlock a real hybrid satellite view.
      </div>

      <div class="relative">
        <div
          #mapContainer
          class="w-full"
          [ngClass]="fullscreenActive ? 'h-[calc(100vh-7rem)]' : 'h-[320px] md:h-[420px]'"
        ></div>

        <div class="pointer-events-none absolute inset-x-4 top-4 flex flex-wrap items-center gap-3">
          <span class="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-[0.68rem] uppercase tracking-[0.26em] text-cyan-50">
            3D Command Layer
          </span>
          <span class="rounded-full border border-orange-300/20 bg-orange-300/10 px-3 py-1 text-[0.68rem] uppercase tracking-[0.26em] text-orange-50">
            {{ windBadgeText() }}
          </span>
        </div>

        <div class="command-scanline"></div>
      </div>

      <div
        *ngIf="!boundaryGeojson"
        class="pointer-events-none absolute inset-x-6 bottom-6 rounded-2xl border border-dashed border-white/15 bg-black/35 p-4 text-sm text-stone-200 backdrop-blur-sm"
      >
        Upload or create a forest map to preview the boundary and ESP32 sensor point here.
      </div>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForestMapComponent implements AfterViewInit, OnChanges, OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly cdr = inject(ChangeDetectorRef);

  @Input() title = 'Forest Map Preview';
  @Input() boundaryGeojson: GeometryPayload | null = null;
  @Input() sourceGeojson: FeatureCollection<Geometry, GeoJsonProperties> | Feature<Geometry, GeoJsonProperties> | Geometry | null = null;
  @Input() overlayGeojson: GeometryPayload | null = null;
  @Input() sensorLocation: CoordinateResponse | null = null;
  @Input() windDirection: number | null = null;
  @Input() allowFullscreen = false;

  @ViewChild('mapContainer', { static: true }) private readonly mapContainer?: ElementRef<HTMLDivElement>;
  @ViewChild('frameContainer', { static: true }) private readonly frameContainer?: ElementRef<HTMLDivElement>;

  protected basemapMode: BasemapMode = defaultBasemapMode();
  protected readonly premiumBasemapEnabled = hasPremiumBasemap();
  protected fullscreenActive = false;

  private map?: Map;
  private sensorMarker?: Marker;
  private readonly fullscreenChangeHandler = () => {
    const target = this.frameContainer?.nativeElement;
    this.fullscreenActive = this.document.fullscreenElement === target;
    this.cdr.markForCheck();
    queueMicrotask(() => this.map?.resize());
  };

  ngAfterViewInit(): void {
    if (!this.mapContainer) {
      return;
    }

    this.document.addEventListener('fullscreenchange', this.fullscreenChangeHandler);

    this.map = new maplibregl.Map({
      container: this.mapContainer.nativeElement,
      style: resolveBasemapStyle(this.basemapMode),
      center: [77.5946, 12.9716],
      zoom: 12,
      attributionControl: false,
      pitch: 56,
      bearing: -18,
      canvasContextAttributes: { antialias: true },
    });

    this.map.addControl(new NavigationControl({ showCompass: true }), 'top-right');
    this.map.on('load', () => {
      this.applyCommandCamera();
      this.renderMapData();
    });
  }

  ngOnChanges(_: SimpleChanges): void {
    this.renderMapData();
  }

  ngOnDestroy(): void {
    this.document.removeEventListener('fullscreenchange', this.fullscreenChangeHandler);
    this.sensorMarker?.remove();
    this.map?.remove();
  }

  protected switchBasemap(mode: BasemapMode): void {
    if (this.basemapMode === mode) {
      return;
    }

    this.basemapMode = mode;
    if (!this.map) {
      return;
    }

    this.map.setStyle(resolveBasemapStyle(mode));
    this.map.once('styledata', () => {
      this.applyCommandCamera();
      this.renderMapData();
    });
  }

  protected async toggleFullscreen(): Promise<void> {
    if (!this.allowFullscreen || !this.frameContainer) {
      return;
    }

    const target = this.frameContainer.nativeElement;

    if (this.document.fullscreenElement === target) {
      await this.document.exitFullscreen?.();
      return;
    }

    await target.requestFullscreen?.();
    queueMicrotask(() => this.map?.resize());
  }

  private renderMapData(): void {
    if (!this.map || !this.map.isStyleLoaded()) {
      return;
    }

    const sourceId = 'forest-source';
    const polygonExtrusionId = 'forest-polygons-extrusion';
    const polygonFillId = 'forest-polygons-fill';
    const polygonLineId = 'forest-polygons-line';
    const lineId = 'forest-lines';
    const pointId = 'forest-points';
    const overlaySourceId = 'forest-overlay-source';
    const overlayExtrusionId = 'forest-overlay-extrusion';
    const overlayFillId = 'forest-overlay-fill';
    const overlayLineId = 'forest-overlay-line';
    const commandSourceId = 'forest-command-source';
    const commandPulseId = 'forest-command-pulse';
    const commandLineId = 'forest-command-line';
    const commandPointId = 'forest-command-point';
    const mapData = this.buildMapData();

    const existingSource = this.map.getSource(sourceId) as GeoJSONSource | undefined;
    if (existingSource) {
      existingSource.setData(mapData);
    } else {
      this.map.addSource(sourceId, {
        type: 'geojson',
        data: mapData,
      });

      this.ensureLayer({
        id: polygonExtrusionId,
        type: 'fill-extrusion',
        source: sourceId,
        filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
        paint: {
          'fill-extrusion-color': '#f97316',
          'fill-extrusion-height': 14,
          'fill-extrusion-opacity': 0.08,
        },
      });

      this.ensureLayer({
        id: polygonFillId,
        type: 'fill',
        source: sourceId,
        filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
        paint: {
          'fill-color': '#f97316',
          'fill-opacity': 0.035,
        },
      });

      this.ensureLayer({
        id: polygonLineId,
        type: 'line',
        source: sourceId,
        filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
        paint: {
          'line-color': '#fdba74',
          'line-width': 2.2,
          'line-opacity': 0.98,
        },
      });

      this.ensureLayer({
        id: lineId,
        type: 'line',
        source: sourceId,
        filter: ['any', ['==', ['geometry-type'], 'LineString'], ['==', ['geometry-type'], 'MultiLineString']],
        paint: {
          'line-color': '#67e8f9',
          'line-width': 2.4,
          'line-dasharray': [2, 1],
          'line-opacity': 0.88,
        },
      });

      this.ensureLayer({
        id: pointId,
        type: 'circle',
        source: sourceId,
        filter: ['==', ['geometry-type'], 'Point'],
        paint: {
          'circle-radius': 5.5,
          'circle-color': '#34d399',
          'circle-stroke-color': '#ecfeff',
          'circle-stroke-width': 1.2,
          'circle-opacity': 0.92,
        },
      });
    }

    const overlayData = this.overlayGeojson
      ? {
          type: 'FeatureCollection' as const,
          features: [
            {
              type: 'Feature' as const,
              properties: {},
              geometry: this.overlayGeojson,
            },
          ],
        }
      : {
          type: 'FeatureCollection' as const,
          features: [],
        };
    const existingOverlaySource = this.map.getSource(overlaySourceId) as GeoJSONSource | undefined;
    if (existingOverlaySource) {
      existingOverlaySource.setData(overlayData);
    } else {
      this.map.addSource(overlaySourceId, {
        type: 'geojson',
        data: overlayData,
      });

      this.ensureLayer({
        id: overlayExtrusionId,
        type: 'fill-extrusion',
        source: overlaySourceId,
        paint: {
          'fill-extrusion-color': '#ef4444',
          'fill-extrusion-height': 18,
          'fill-extrusion-opacity': 0.45,
        },
      });

      this.ensureLayer({
        id: overlayFillId,
        type: 'fill',
        source: overlaySourceId,
        paint: {
          'fill-color': '#ef4444',
          'fill-opacity': 0.28,
        },
      });

      this.ensureLayer({
        id: overlayLineId,
        type: 'line',
        source: overlaySourceId,
        paint: {
          'line-color': '#fb7185',
          'line-width': 2.6,
        },
      });
    }

    const commandData = this.buildCommandCenterData();
    const existingCommandSource = this.map.getSource(commandSourceId) as GeoJSONSource | undefined;
    if (existingCommandSource) {
      existingCommandSource.setData(commandData);
    } else {
      this.map.addSource(commandSourceId, {
        type: 'geojson',
        data: commandData,
      });

      this.ensureLayer({
        id: commandPulseId,
        type: 'fill',
        source: commandSourceId,
        filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
        paint: {
          'fill-color': '#38bdf8',
          'fill-opacity': 0.1,
        },
      });

      this.ensureLayer({
        id: commandLineId,
        type: 'line',
        source: commandSourceId,
        filter: ['any', ['==', ['geometry-type'], 'LineString'], ['==', ['geometry-type'], 'MultiLineString']],
        paint: {
          'line-color': '#7dd3fc',
          'line-width': 3,
          'line-dasharray': [0.8, 1.2],
          'line-opacity': 0.9,
        },
      });

      this.ensureLayer({
        id: commandPointId,
        type: 'circle',
        source: commandSourceId,
        filter: ['==', ['geometry-type'], 'Point'],
        paint: {
          'circle-radius': 8,
          'circle-color': '#f97316',
          'circle-stroke-color': '#fff7ed',
          'circle-stroke-width': 1.6,
          'circle-opacity': 0.95,
        },
      });
    }

    this.sensorMarker?.remove();
    if (this.sensorLocation) {
      const markerElement = document.createElement('div');
      markerElement.className = 'sensor-marker';
      markerElement.innerHTML = '<span></span>';

      this.sensorMarker = new Marker({ element: markerElement, anchor: 'center' })
        .setLngLat([this.sensorLocation.longitude, this.sensorLocation.latitude])
        .addTo(this.map);
    }

    const bounds = this.computeBounds();
    if (bounds) {
      this.map.fitBounds(bounds, {
        padding: 60,
        maxZoom: 15,
        duration: 1200,
        pitch: 56,
        bearing: -18,
      });
    }
  }

  private buildMapData(): FeatureCollection<Geometry, GeoJsonProperties> | Feature<Geometry, GeoJsonProperties> | Geometry {
    if (this.sourceGeojson) {
      return this.sourceGeojson;
    }

    if (this.boundaryGeojson) {
      return {
        type: 'FeatureCollection' as const,
        features: [
          {
            type: 'Feature' as const,
            properties: {},
            geometry: this.boundaryGeojson,
          },
        ],
      };
    }

    return {
      type: 'FeatureCollection' as const,
      features: [],
    };
  }

  protected windBadgeText(): string {
    if (this.windDirection === null || this.windDirection === undefined) {
      return 'Geo Context Active';
    }
    return `Wind ${Math.round(this.windDirection)} deg`;
  }

  private applyCommandCamera(): void {
    if (!this.map) {
      return;
    }

    this.map.easeTo({
      pitch: 56,
      bearing: -18,
      duration: 0,
    });
  }

  private ensureLayer(layer: Parameters<Map['addLayer']>[0]): void {
    if (!this.map || this.map.getLayer(layer.id)) {
      return;
    }
    this.map.addLayer(layer);
  }

  private buildCommandCenterData(): FeatureCollection<Geometry, GeoJsonProperties> {
    const origin = this.resolveCommandOrigin();
    if (!origin) {
      return {
        type: 'FeatureCollection',
        features: [],
      };
    }

    const features: Array<Feature<Geometry, GeoJsonProperties>> = [
      {
        type: 'Feature',
        properties: { kind: 'command_origin' },
        geometry: {
          type: 'Point',
          coordinates: [origin.longitude, origin.latitude],
        },
      },
      {
        type: 'Feature',
        properties: { kind: 'command_radius' },
        geometry: this.buildCirclePolygon(origin.longitude, origin.latitude, 260),
      },
    ];

    if (this.windDirection !== null) {
      const target = this.projectPoint(origin.longitude, origin.latitude, this.windDirection, 720);
      features.push({
        type: 'Feature',
        properties: { kind: 'wind_corridor' },
        geometry: {
          type: 'LineString',
          coordinates: [
            [origin.longitude, origin.latitude],
            [target.longitude, target.latitude],
          ],
        },
      });
    }

    return {
      type: 'FeatureCollection',
      features,
    };
  }

  private resolveCommandOrigin(): CoordinateResponse | null {
    if (this.sensorLocation) {
      return this.sensorLocation;
    }

    const bounds = this.computeBounds();
    if (!bounds || !(bounds instanceof maplibregl.LngLatBounds)) {
      return null;
    }

    const center = bounds.getCenter();
    return {
      latitude: center.lat,
      longitude: center.lng,
      source: 'forest_center',
    };
  }

  private buildCirclePolygon(longitude: number, latitude: number, radiusMeters: number): GeometryPayload {
    const steps = 40;
    const coordinates: number[][] = [];
    for (let index = 0; index <= steps; index += 1) {
      const bearing = (index / steps) * 360;
      const point = this.projectPoint(longitude, latitude, bearing, radiusMeters);
      coordinates.push([point.longitude, point.latitude]);
    }

    return {
      type: 'Polygon',
      coordinates: [coordinates],
    };
  }

  private projectPoint(longitude: number, latitude: number, bearingDegrees: number, distanceMeters: number) {
    const radians = (bearingDegrees * Math.PI) / 180;
    const deltaLatitude = (distanceMeters * Math.cos(radians)) / 111320;
    const deltaLongitude =
      (distanceMeters * Math.sin(radians)) / (111320 * Math.max(Math.cos((latitude * Math.PI) / 180), 0.2));

    return {
      longitude: longitude + deltaLongitude,
      latitude: latitude + deltaLatitude,
    };
  }

  private computeBounds(): LngLatBoundsLike | null {
    const bounds = new maplibregl.LngLatBounds();
    let hasBounds = false;

    const extendFromCoordinates = (node: CoordinateNode): void => {
      if (!Array.isArray(node)) {
        return;
      }

      if (node.length >= 2 && typeof node[0] === 'number' && typeof node[1] === 'number') {
        bounds.extend([node[0], node[1]]);
        hasBounds = true;
        return;
      }

      node.forEach((child) => extendFromCoordinates(child as CoordinateNode));
    };

    const extendFromGeoJsonObject = (geoJson: unknown): void => {
      if (!geoJson || typeof geoJson !== 'object') {
        return;
      }

      const candidate = geoJson as {
        type?: string;
        coordinates?: CoordinateNode;
        geometry?: unknown;
        features?: unknown[];
      };

      if (candidate.type === 'FeatureCollection' && Array.isArray(candidate.features)) {
        candidate.features.forEach((feature) => extendFromGeoJsonObject(feature));
        return;
      }

      if (candidate.type === 'Feature' && candidate.geometry) {
        extendFromGeoJsonObject(candidate.geometry);
        return;
      }

      if (candidate.coordinates) {
        extendFromCoordinates(candidate.coordinates);
      }
    };

    if (this.sourceGeojson) {
      extendFromGeoJsonObject(this.sourceGeojson);
    }

    if (this.boundaryGeojson) {
      if ('coordinates' in this.boundaryGeojson) {
        extendFromCoordinates(this.boundaryGeojson.coordinates as CoordinateNode);
      }
    }

    if (this.overlayGeojson && 'coordinates' in this.overlayGeojson) {
      extendFromCoordinates(this.overlayGeojson.coordinates as CoordinateNode);
    }

    if (this.sensorLocation) {
      bounds.extend([this.sensorLocation.longitude, this.sensorLocation.latitude]);
      hasBounds = true;
    }

    return hasBounds ? bounds : null;
  }
}
