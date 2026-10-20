import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import type { Feature, GeoJsonProperties, Geometry } from 'geojson';

import { FireSimulationResponse, ForestDetailResponse, GeoJsonDocument } from '../../../core/api.models';

type Coord = [number, number];
type Point2D = { x: number; y: number };
type Polygon = Point2D[][];
type Scene = {
  boundary: Polygon[];
  vegetation: Polygon[];
  waters: Polygon[];
  habitats: Polygon[];
  roads: Point2D[][];
  ignition: Point2D | null;
  wildlife: Point2D[];
  trees: Array<Point2D & { size: number; alpha: number; hue: number }>;
  steps: Polygon[][];
};
type Bounds = { minLng: number; maxLng: number; minLat: number; maxLat: number };

const WIDTH = 1280;
const HEIGHT = 720;
const PADDING = 72;
const DURATION_MS = 10000;
const INTRO = 0.16;
const SPREAD = 0.68;

@Component({
  selector: 'app-simulation-reel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './simulation-reel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SimulationReelComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() forest: ForestDetailResponse | null = null;
  @Input() simulation: FireSimulationResponse | null = null;

  @ViewChild('reelCanvas', { static: true }) private readonly reelCanvas?: ElementRef<HTMLCanvasElement>;

  protected readonly playing = signal(false);
  protected readonly exporting = signal(false);
  protected readonly statusMessage = signal('Run a simulation to unlock the cinematic reel.');
  protected readonly errorMessage = signal('');
  protected readonly downloadUrl = signal<string | null>(null);
  protected readonly exportSupported =
    typeof MediaRecorder !== 'undefined' && typeof HTMLCanvasElement !== 'undefined';

  private ctx: CanvasRenderingContext2D | null = null;
  private scene: Scene | null = null;
  private animationFrameId: number | null = null;
  private previewStartTime = 0;
  private currentProgress = 0;

  ngAfterViewInit(): void {
    const canvas = this.reelCanvas?.nativeElement;
    if (!canvas) {
      return;
    }
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    this.ctx = canvas.getContext('2d');
    this.rebuildScene();
  }

  ngOnChanges(_: SimpleChanges): void {
    this.rebuildScene();
  }

  ngOnDestroy(): void {
    this.stopPreview();
    this.releaseDownloadUrl();
  }

  protected hasRenderableScene(): boolean {
    return !!this.scene && !!this.simulation;
  }

  protected togglePreview(): void {
    if (!this.hasRenderableScene()) {
      return;
    }
    if (this.playing()) {
      this.stopPreview();
      return;
    }
    this.errorMessage.set('');
    this.statusMessage.set('Playing cinematic simulation reel preview.');
    this.playing.set(true);
    this.previewStartTime = performance.now() - this.currentProgress * DURATION_MS;
    this.animationFrameId = requestAnimationFrame((t) => this.animatePreview(t));
  }

  protected async exportVideo(): Promise<void> {
    const canvas = this.reelCanvas?.nativeElement;
    if (!canvas || !this.ctx || !this.scene || !this.exportSupported || this.exporting()) {
      return;
    }

    const mimeType = this.resolveMimeType();
    if (!mimeType) {
      this.errorMessage.set('This browser cannot export WebM with the current MediaRecorder support.');
      return;
    }

    this.stopPreview();
    this.errorMessage.set('');
    this.statusMessage.set('Rendering cinematic reel to WebM. This takes about 10 seconds.');
    this.exporting.set(true);

    const stream = canvas.captureStream(30);
    const recorder = new MediaRecorder(stream, { mimeType });
    const chunks: BlobPart[] = [];

    const blobPromise = new Promise<Blob>((resolve, reject) => {
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };
      recorder.onerror = () => reject(new Error('MediaRecorder failed while exporting the simulation reel.'));
      recorder.onstop = () => resolve(new Blob(chunks, { type: mimeType }));
    });

    recorder.start(250);
    const start = performance.now();

    await new Promise<void>((resolve) => {
      const tick = (timestamp: number) => {
        const elapsed = timestamp - start;
        const progress = this.clamp(elapsed / DURATION_MS, 0, 1);
        this.currentProgress = progress;
        this.render(progress);
        if (elapsed < DURATION_MS) {
          requestAnimationFrame(tick);
          return;
        }
        this.render(1);
        resolve();
      };
      requestAnimationFrame(tick);
    });

    recorder.stop();

    try {
      const blob = await blobPromise;
      this.releaseDownloadUrl();
      this.downloadUrl.set(URL.createObjectURL(blob));
      this.statusMessage.set('Simulation reel exported. You can download the WebM file now.');
    } catch (error) {
      this.errorMessage.set(error instanceof Error ? error.message : 'Simulation reel export failed.');
    } finally {
      stream.getTracks().forEach((track) => track.stop());
      this.exporting.set(false);
      this.render(this.currentProgress);
    }
  }

  private animatePreview(timestamp: number): void {
    if (!this.playing()) {
      return;
    }
    const progress = ((timestamp - this.previewStartTime) % DURATION_MS) / DURATION_MS;
    this.currentProgress = progress;
    this.render(progress);
    this.animationFrameId = requestAnimationFrame((t) => this.animatePreview(t));
  }

  private stopPreview(): void {
    this.playing.set(false);
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  private rebuildScene(): void {
    if (!this.ctx) {
      return;
    }
    if (!this.forest?.boundary_geojson || !this.simulation?.steps.length) {
      this.scene = null;
      this.clearCanvas();
      this.drawEmptyState();
      this.statusMessage.set('Run a simulation to unlock the cinematic reel.');
      return;
    }

    this.scene = this.buildScene(this.forest, this.simulation);
    this.statusMessage.set('Cinematic simulation reel is ready for preview and export.');
    this.render(this.currentProgress || 0.02);
  }

  private buildScene(forest: ForestDetailResponse, simulation: FireSimulationResponse): Scene {
    const source = forest.source_geojson;
    const bounds = this.computeBounds(forest, simulation, source);
    const project = (lng: number, lat: number): Point2D => this.projectPoint(lng, lat, bounds);

    const boundary = this.extractPolygons(forest.boundary_geojson).map((polygon) => polygon.map((ring) => ring.map(([lng, lat]) => project(lng, lat))));
    const vegetation: Polygon[] = [];
    const waters: Polygon[] = [];
    const habitats: Polygon[] = [];
    const roads: Point2D[][] = [];
    const wildlife: Point2D[] = [];

    this.iterateFeatures(source, (feature) => {
      const blob = this.stringifyProperties(feature.properties ?? {});
      const geometry = feature.geometry;
      if (!geometry) {
        return;
      }

      const polygons = this.extractPolygons(geometry).map((polygon) => polygon.map((ring) => ring.map(([lng, lat]) => project(lng, lat))));
      const lines = this.extractLines(geometry).map((line) => line.map(([lng, lat]) => project(lng, lat)));
      const points = this.extractPoints(geometry).map(([lng, lat]) => project(lng, lat));

      if (polygons.length) {
        if (this.hasKeyword(blob, ['water', 'lake', 'river', 'stream', 'pond', 'wetland'])) {
          waters.push(...polygons);
          return;
        }
        if (this.hasKeyword(blob, ['habitat', 'wildlife', 'animal', 'fauna', 'species', 'corridor'])) {
          habitats.push(...polygons);
          polygons.forEach((polygon) => {
            const centroid = this.centroid(polygon);
            if (centroid) {
              wildlife.push(centroid);
            }
          });
          return;
        }
        vegetation.push(...polygons);
      }

      if (lines.length && this.hasKeyword(blob, ['road', 'trail', 'path', 'track', 'route', 'access'])) {
        roads.push(...lines);
      }

      if (points.length && this.hasKeyword(blob, ['habitat', 'wildlife', 'animal', 'fauna'])) {
        wildlife.push(...points);
      }
    });

    const ignition = simulation.ignition_point
      ? project(simulation.ignition_point.longitude, simulation.ignition_point.latitude)
      : null;

    const steps = simulation.steps.map((step) =>
      this.extractPolygons(step.affected_geojson).map((polygon) => polygon.map((ring) => ring.map(([lng, lat]) => project(lng, lat)))),
    );

    return {
      boundary,
      vegetation,
      waters,
      habitats,
      roads,
      ignition,
      wildlife,
      trees: this.buildTreePoints(boundary, forest.tree_density ?? null, simulation.id),
      steps,
    };
  }

  private render(progress: number): void {
    if (!this.ctx || !this.scene || !this.simulation) {
      return;
    }
    const ctx = this.ctx;
    ctx.clearRect(0, 0, WIDTH, HEIGHT);
    this.drawBackground(ctx, progress);
    this.drawGrid(ctx);
    this.drawPolygons(ctx, this.scene.vegetation, 'rgba(74, 222, 128, 0.08)', 'rgba(74, 222, 128, 0.12)');
    this.drawTrees(ctx, this.scene.trees);
    this.drawPolygons(ctx, this.scene.waters, 'rgba(56, 189, 248, 0.18)', 'rgba(125, 211, 252, 0.38)');
    this.drawRoads(ctx, this.scene.roads);
    this.drawHabitats(ctx, this.scene.habitats, this.scene.wildlife, progress);
    this.drawBoundary(ctx, this.scene.boundary);
    this.drawIgnition(ctx, this.scene.ignition, progress);
    this.drawFire(ctx, this.scene.steps, progress, this.simulation.weather?.wind_direction ?? 0);
    this.drawHeader(ctx, progress);
    this.drawWeatherPanel(ctx, progress);
    this.drawTimeline(ctx, progress);
    this.drawSummary(ctx, progress);
  }

  private drawBackground(ctx: CanvasRenderingContext2D, progress: number): void {
    const gradient = ctx.createLinearGradient(0, 0, WIDTH, HEIGHT);
    gradient.addColorStop(0, '#051118');
    gradient.addColorStop(0.45, '#0a1b1f');
    gradient.addColorStop(1, '#19110e');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    const glow = ctx.createRadialGradient(WIDTH * (0.18 + progress * 0.1), HEIGHT * 0.2, 0, WIDTH * 0.22, HEIGHT * 0.24, WIDTH * 0.62);
    glow.addColorStop(0, 'rgba(16, 185, 129, 0.18)');
    glow.addColorStop(0.42, 'rgba(251, 146, 60, 0.09)');
    glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
  }

  private drawGrid(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.035)';
    ctx.lineWidth = 1;
    for (let x = 40; x < WIDTH; x += 50) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, HEIGHT);
      ctx.stroke();
    }
    for (let y = 40; y < HEIGHT; y += 50) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(WIDTH, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  private drawPolygons(ctx: CanvasRenderingContext2D, polygons: Polygon[], fill: string, stroke: string): void {
    polygons.forEach((polygon) => {
      this.tracePolygon(ctx, polygon);
      ctx.fillStyle = fill;
      ctx.fill('evenodd');
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    });
  }

  private drawTrees(ctx: CanvasRenderingContext2D, trees: Scene['trees']): void {
    ctx.save();
    trees.forEach((tree) => {
      ctx.strokeStyle = `hsla(${130 + tree.hue}, 58%, 62%, ${tree.alpha})`;
      ctx.lineWidth = tree.size * 0.55;
      ctx.beginPath();
      ctx.moveTo(tree.x, tree.y + tree.size * 1.6);
      ctx.lineTo(tree.x, tree.y - tree.size * 1.4);
      ctx.stroke();

      ctx.fillStyle = `hsla(${120 + tree.hue}, 54%, 45%, ${tree.alpha})`;
      ctx.beginPath();
      ctx.arc(tree.x, tree.y - tree.size * 0.5, tree.size * 1.25, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  private drawRoads(ctx: CanvasRenderingContext2D, roads: Point2D[][]): void {
    ctx.save();
    ctx.strokeStyle = 'rgba(241, 245, 249, 0.48)';
    ctx.setLineDash([10, 8]);
    ctx.lineWidth = 2;
    roads.forEach((line) => {
      if (line.length < 2) {
        return;
      }
      ctx.beginPath();
      ctx.moveTo(line[0].x, line[0].y);
      for (let index = 1; index < line.length; index += 1) {
        ctx.lineTo(line[index].x, line[index].y);
      }
      ctx.stroke();
    });
    ctx.restore();
  }

  private drawHabitats(ctx: CanvasRenderingContext2D, habitats: Polygon[], wildlife: Point2D[], progress: number): void {
    this.drawPolygons(ctx, habitats, 'rgba(253, 224, 71, 0.06)', 'rgba(253, 224, 71, 0.18)');
    ctx.save();
    wildlife.forEach((marker, index) => {
      const pulse = 0.5 + 0.5 * Math.sin(progress * Math.PI * 8 + index);
      const radius = 10 + pulse * 12;
      ctx.fillStyle = `rgba(253, 224, 71, ${0.14 + pulse * 0.12})`;
      ctx.beginPath();
      ctx.arc(marker.x, marker.y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(255, 244, 197, 0.92)';
      ctx.beginPath();
      ctx.arc(marker.x, marker.y, 3.2, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  private drawBoundary(ctx: CanvasRenderingContext2D, polygons: Polygon[]): void {
    ctx.save();
    polygons.forEach((polygon) => {
      this.tracePolygon(ctx, polygon);
      ctx.strokeStyle = 'rgba(254, 215, 170, 0.92)';
      ctx.lineWidth = 2.8;
      ctx.stroke();
    });
    ctx.restore();
  }

  private drawIgnition(ctx: CanvasRenderingContext2D, ignition: Point2D | null, progress: number): void {
    if (!ignition) {
      return;
    }
    const pulse = 0.5 + 0.5 * Math.sin(progress * Math.PI * 10);
    ctx.save();
    ctx.fillStyle = `rgba(251, 146, 60, ${0.16 + pulse * 0.2})`;
    ctx.beginPath();
    ctx.arc(ignition.x, ignition.y, 22 + pulse * 12, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = 'rgba(255, 237, 213, 0.96)';
    ctx.beginPath();
    ctx.arc(ignition.x, ignition.y, 5.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.88)';
    ctx.font = '600 15px Manrope, sans-serif';
    ctx.fillText('ESP32 ignition node', ignition.x + 16, ignition.y - 14);
    ctx.restore();
  }

  private drawFire(ctx: CanvasRenderingContext2D, steps: Polygon[][], progress: number, windDirection: number): void {
    if (!steps.length) {
      return;
    }
    const spreadProgress = this.clamp((progress - INTRO) / SPREAD, 0, 1);
    const scaled = spreadProgress * steps.length;
    const activeIndex = Math.min(Math.floor(scaled), steps.length - 1);
    const localProgress = scaled - activeIndex;

    steps.forEach((polygons, index) => {
      let opacity = 0;
      if (index < activeIndex) {
        opacity = 0.14 + index * 0.018;
      } else if (index === activeIndex) {
        opacity = 0.12 + localProgress * 0.34;
      }
      if (opacity <= 0) {
        return;
      }

      polygons.forEach((polygon) => {
        ctx.save();
        ctx.filter = index === activeIndex ? 'blur(14px)' : 'blur(8px)';
        this.tracePolygon(ctx, polygon);
        ctx.fillStyle = `rgba(249, 115, 22, ${opacity})`;
        ctx.fill('evenodd');
        ctx.restore();

        this.tracePolygon(ctx, polygon);
        ctx.strokeStyle = `rgba(248, 113, 113, ${Math.min(opacity + 0.18, 0.8)})`;
        ctx.lineWidth = index === activeIndex ? 2.6 : 1.4;
        ctx.stroke();
      });
    });

    const centroid = this.centroid(steps[activeIndex][0]);
    if (centroid) {
      this.drawSmoke(ctx, centroid, windDirection, progress);
    }
  }

  private drawSmoke(ctx: CanvasRenderingContext2D, centroid: Point2D, windDirection: number, progress: number): void {
    const angle = ((windDirection - 90) * Math.PI) / 180;
    const driftX = Math.cos(angle);
    const driftY = Math.sin(angle);
    ctx.save();
    for (let index = 0; index < 18; index += 1) {
      const phase = progress * 12 + index * 0.7;
      const distance = 12 + index * 9 + Math.sin(phase) * 6;
      const x = centroid.x + driftX * distance + Math.cos(phase * 0.8) * 14;
      const y = centroid.y + driftY * distance + Math.sin(phase) * 11;
      const radius = 18 + (index % 4) * 6;
      ctx.fillStyle = `rgba(214, 211, 209, ${0.03 + (18 - index) * 0.008})`;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
    for (let index = 0; index < 14; index += 1) {
      const phase = progress * 15 + index;
      const x = centroid.x + driftX * (35 + index * 10) + Math.cos(phase * 1.7) * 8;
      const y = centroid.y + driftY * (20 + index * 6) + Math.sin(phase * 1.5) * 7;
      ctx.fillStyle = `rgba(251, 191, 36, ${0.18 + (index % 4) * 0.03})`;
      ctx.beginPath();
      ctx.arc(x, y, 1.8 + (index % 3), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  private drawHeader(ctx: CanvasRenderingContext2D, progress: number): void {
    const forestName = this.forest?.name ?? 'Forest Fire Shield Forest';
    const fade = this.clamp(progress / 0.12, 0, 1);
    ctx.save();
    ctx.globalAlpha = fade;
    ctx.fillStyle = 'rgba(4, 16, 24, 0.72)';
    this.roundRect(ctx, 38, 34, 420, 112, 24, true);
    ctx.fillStyle = 'rgba(253, 186, 116, 0.76)';
    ctx.font = '600 16px Manrope, sans-serif';
    ctx.fillText('FOREST FIRE SHIELD // CINEMATIC REEL', 58, 64);
    ctx.fillStyle = '#ffffff';
    ctx.font = '700 36px "Space Grotesk", sans-serif';
    ctx.fillText(forestName, 58, 106);
    ctx.fillStyle = 'rgba(231, 229, 228, 0.85)';
    ctx.font = '500 16px Manrope, sans-serif';
    ctx.fillText('Wildfire spread preview driven by the current simulation run', 58, 132);
    ctx.restore();
  }

  private drawWeatherPanel(ctx: CanvasRenderingContext2D, progress: number): void {
    const weather = this.simulation?.weather;
    const windDirection = weather?.wind_direction ?? this.simulation?.assumptions.wind_push_direction ?? 0;
    ctx.save();
    ctx.globalAlpha = 0.95;
    ctx.fillStyle = 'rgba(4, 16, 24, 0.74)';
    this.roundRect(ctx, WIDTH - 318, 34, 280, 162, 24, true);
    ctx.fillStyle = 'rgba(167, 243, 208, 0.74)';
    ctx.font = '600 15px Manrope, sans-serif';
    ctx.fillText('WEATHER + WIND', WIDTH - 294, 64);

    const rows = [
      `Temp  ${weather?.temperature ?? '--'} C`,
      `Humidity  ${weather?.relative_humidity ?? '--'}%`,
      `Wind speed  ${weather?.wind_speed ?? '--'} km/h`,
      `Wind dir  ${windDirection ?? '--'} deg`,
    ];
    ctx.fillStyle = '#ffffff';
    ctx.font = '600 20px "Space Grotesk", sans-serif';
    rows.forEach((row, index) => ctx.fillText(row, WIDTH - 294, 98 + index * 24));

    const arrowCenterX = WIDTH - 88;
    const arrowCenterY = 150;
    const angle = (((windDirection - 90) * Math.PI) / 180) + progress * 0.02;
    ctx.strokeStyle = 'rgba(125, 211, 252, 0.92)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(arrowCenterX, arrowCenterY);
    ctx.lineTo(arrowCenterX + Math.cos(angle) * 34, arrowCenterY + Math.sin(angle) * 34);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(arrowCenterX, arrowCenterY, 4, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.95)';
    ctx.fill();
    ctx.restore();
  }

  private drawTimeline(ctx: CanvasRenderingContext2D, progress: number): void {
    if (!this.simulation) {
      return;
    }
    const timelineWidth = WIDTH - 120;
    const timelineX = 60;
    const timelineY = HEIGHT - 74;
    const steps = this.simulation.steps.length;
    const spreadProgress = this.clamp((progress - INTRO) / SPREAD, 0, 1);
    const activeSegments = Math.max(1, Math.floor(spreadProgress * steps));

    ctx.save();
    ctx.fillStyle = 'rgba(4, 16, 24, 0.72)';
    this.roundRect(ctx, 42, HEIGHT - 110, WIDTH - 84, 58, 22, true);
    ctx.fillStyle = 'rgba(214, 211, 209, 0.85)';
    ctx.font = '600 14px Manrope, sans-serif';
    ctx.fillText('SPREAD TIMELINE', timelineX, timelineY - 12);

    const segmentWidth = timelineWidth / steps;
    for (let index = 0; index < steps; index += 1) {
      const x = timelineX + index * segmentWidth;
      const active = index < activeSegments;
      ctx.fillStyle = active ? 'rgba(251, 146, 60, 0.94)' : 'rgba(255,255,255,0.08)';
      this.roundRect(ctx, x, timelineY, Math.max(segmentWidth - 8, 8), 10, 999, true);
      ctx.fillStyle = active ? 'rgba(255, 237, 213, 0.92)' : 'rgba(214, 211, 209, 0.55)';
      ctx.fillText(`H${this.simulation.steps[index].hour_offset}`, x, timelineY + 28);
    }
    ctx.restore();
  }

  private drawSummary(ctx: CanvasRenderingContext2D, progress: number): void {
    const finalStep = this.simulation?.steps.at(-1);
    const summaryProgress = this.clamp((progress - 0.82) / 0.16, 0, 1);
    if (!finalStep || summaryProgress <= 0) {
      return;
    }
    ctx.save();
    ctx.globalAlpha = summaryProgress;
    ctx.fillStyle = 'rgba(4, 16, 24, 0.84)';
    this.roundRect(ctx, WIDTH - 392, HEIGHT - 244, 344, 128, 26, true);
    ctx.fillStyle = 'rgba(251, 191, 36, 0.88)';
    ctx.font = '600 15px Manrope, sans-serif';
    ctx.fillText('FINAL ESTIMATE', WIDTH - 364, HEIGHT - 208);
    ctx.fillStyle = '#ffffff';
    ctx.font = '700 34px "Space Grotesk", sans-serif';
    ctx.fillText(`${Math.round(finalStep.estimated_area_m2).toLocaleString()} m2`, WIDTH - 364, HEIGHT - 166);
    ctx.fillStyle = 'rgba(231, 229, 228, 0.84)';
    ctx.font = '500 16px Manrope, sans-serif';
    ctx.fillText(`Burnt cells  ${finalStep.burnt_cells}`, WIDTH - 364, HEIGHT - 132);
    ctx.fillText(`Spread heading  ${Math.round(finalStep.spread_heading ?? 0)} deg`, WIDTH - 364, HEIGHT - 108);
    ctx.restore();
  }

  private clearCanvas(): void {
    this.ctx?.clearRect(0, 0, WIDTH, HEIGHT);
  }

  private drawEmptyState(): void {
    if (!this.ctx) {
      return;
    }
    const ctx = this.ctx;
    const gradient = ctx.createLinearGradient(0, 0, WIDTH, HEIGHT);
    gradient.addColorStop(0, '#051118');
    gradient.addColorStop(1, '#10141b');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    ctx.fillStyle = 'rgba(255,255,255,0.08)';
    this.roundRect(ctx, 120, 120, WIDTH - 240, HEIGHT - 240, 32, true);
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1.2;
    this.roundRect(ctx, 120, 120, WIDTH - 240, HEIGHT - 240, 32, false);

    ctx.fillStyle = 'rgba(253, 186, 116, 0.76)';
    ctx.font = '600 18px Manrope, sans-serif';
    ctx.fillText('SIMULATION REEL LOCKED', 180, 238);
    ctx.fillStyle = '#ffffff';
    ctx.font = '700 46px "Space Grotesk", sans-serif';
    ctx.fillText('Run a simulation first', 180, 304);
    ctx.fillStyle = 'rgba(231, 229, 228, 0.84)';
    ctx.font = '500 20px Manrope, sans-serif';
    ctx.fillText('The cinematic export uses your saved forest, weather snapshot, and hourly spread polygons.', 180, 350);
    ctx.fillText('Once a scenario is generated, this canvas becomes a premium preview and WebM export surface.', 180, 384);
  }

  private resolveMimeType(): string | null {
    const candidates = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
    for (const candidate of candidates) {
      if (MediaRecorder.isTypeSupported(candidate)) {
        return candidate;
      }
    }
    return null;
  }

  private tracePolygon(ctx: CanvasRenderingContext2D, polygon: Polygon): void {
    ctx.beginPath();
    polygon.forEach((ring) => {
      if (!ring.length) {
        return;
      }
      ctx.moveTo(ring[0].x, ring[0].y);
      for (let index = 1; index < ring.length; index += 1) {
        ctx.lineTo(ring[index].x, ring[index].y);
      }
      ctx.closePath();
    });
  }

  private computeBounds(
    forest: ForestDetailResponse,
    simulation: FireSimulationResponse,
    source: GeoJsonDocument | null | undefined,
  ): Bounds {
    const coordinates: Coord[] = [
      ...this.collectCoordinatePairs(forest.boundary_geojson),
      ...this.collectCoordinatePairs(source),
      ...simulation.steps.flatMap((step) => this.collectCoordinatePairs(step.affected_geojson)),
    ];

    if (simulation.ignition_point) {
      coordinates.push([simulation.ignition_point.longitude, simulation.ignition_point.latitude]);
    }

    if (!coordinates.length) {
      const center = forest.center;
      return {
        minLng: center.longitude - 0.002,
        maxLng: center.longitude + 0.002,
        minLat: center.latitude - 0.002,
        maxLat: center.latitude + 0.002,
      };
    }

    const lngs = coordinates.map(([lng]) => lng);
    const lats = coordinates.map(([, lat]) => lat);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const lngPad = Math.max((maxLng - minLng) * 0.08, 0.00035);
    const latPad = Math.max((maxLat - minLat) * 0.08, 0.00035);

    return {
      minLng: minLng - lngPad,
      maxLng: maxLng + lngPad,
      minLat: minLat - latPad,
      maxLat: maxLat + latPad,
    };
  }

  private collectCoordinatePairs(input: GeoJsonDocument | Geometry | null | undefined): Coord[] {
    if (!input) {
      return [];
    }

    if ('type' in input && input.type === 'FeatureCollection') {
      return input.features.flatMap((feature) => this.collectCoordinatePairs(feature));
    }

    if ('type' in input && input.type === 'Feature') {
      return this.collectCoordinatePairs(input.geometry ?? null);
    }

    if (!('type' in input)) {
      return [];
    }

    switch (input.type) {
      case 'Point':
        return [this.toCoord(input.coordinates)];
      case 'MultiPoint':
      case 'LineString':
        return input.coordinates.map((coordinate) => this.toCoord(coordinate));
      case 'MultiLineString':
      case 'Polygon':
        return input.coordinates.flatMap((segment) => segment.map((coordinate) => this.toCoord(coordinate)));
      case 'MultiPolygon':
        return input.coordinates.flatMap((polygon) =>
          polygon.flatMap((segment) => segment.map((coordinate) => this.toCoord(coordinate))),
        );
      case 'GeometryCollection':
        return input.geometries.flatMap((geometry) => this.collectCoordinatePairs(geometry));
      default:
        return [];
    }
  }

  private projectPoint(lng: number, lat: number, bounds: Bounds): Point2D {
    const lngSpan = Math.max(bounds.maxLng - bounds.minLng, 0.000001);
    const latSpan = Math.max(bounds.maxLat - bounds.minLat, 0.000001);
    const scale = Math.min((WIDTH - PADDING * 2) / lngSpan, (HEIGHT - PADDING * 2) / latSpan);
    const contentWidth = lngSpan * scale;
    const contentHeight = latSpan * scale;
    const offsetX = (WIDTH - contentWidth) / 2;
    const offsetY = (HEIGHT - contentHeight) / 2;

    return {
      x: offsetX + (lng - bounds.minLng) * scale,
      y: HEIGHT - offsetY - (lat - bounds.minLat) * scale,
    };
  }

  private iterateFeatures(
    document: GeoJsonDocument | null | undefined,
    visitor: (feature: Feature<Geometry, GeoJsonProperties>) => void,
  ): void {
    if (!document) {
      return;
    }

    if (document.type === 'FeatureCollection') {
      document.features.forEach((feature) => visitor(feature));
      return;
    }

    if (document.type === 'Feature') {
      visitor(document);
      return;
    }

    visitor({
      type: 'Feature',
      properties: {},
      geometry: document,
    });
  }

  private extractPolygons(input: GeoJsonDocument | Geometry | null | undefined): Coord[][][] {
    if (!input) {
      return [];
    }

    if ('type' in input && input.type === 'FeatureCollection') {
      return input.features.flatMap((feature) => this.extractPolygons(feature));
    }

    if ('type' in input && input.type === 'Feature') {
      return this.extractPolygons(input.geometry ?? null);
    }

    if (!('type' in input)) {
      return [];
    }

    switch (input.type) {
      case 'Polygon':
        return [input.coordinates.map((ring) => ring.map((coordinate) => this.toCoord(coordinate)))];
      case 'MultiPolygon':
        return input.coordinates.map((polygon) => polygon.map((ring) => ring.map((coordinate) => this.toCoord(coordinate))));
      case 'GeometryCollection':
        return input.geometries.flatMap((geometry) => this.extractPolygons(geometry));
      default:
        return [];
    }
  }

  private extractLines(input: GeoJsonDocument | Geometry | null | undefined): Coord[][] {
    if (!input) {
      return [];
    }

    if ('type' in input && input.type === 'FeatureCollection') {
      return input.features.flatMap((feature) => this.extractLines(feature));
    }

    if ('type' in input && input.type === 'Feature') {
      return this.extractLines(input.geometry ?? null);
    }

    if (!('type' in input)) {
      return [];
    }

    switch (input.type) {
      case 'LineString':
        return [input.coordinates.map((coordinate) => this.toCoord(coordinate))];
      case 'MultiLineString':
        return input.coordinates.map((line) => line.map((coordinate) => this.toCoord(coordinate)));
      case 'GeometryCollection':
        return input.geometries.flatMap((geometry) => this.extractLines(geometry));
      default:
        return [];
    }
  }

  private extractPoints(input: GeoJsonDocument | Geometry | null | undefined): Coord[] {
    if (!input) {
      return [];
    }

    if ('type' in input && input.type === 'FeatureCollection') {
      return input.features.flatMap((feature) => this.extractPoints(feature));
    }

    if ('type' in input && input.type === 'Feature') {
      return this.extractPoints(input.geometry ?? null);
    }

    if (!('type' in input)) {
      return [];
    }

    switch (input.type) {
      case 'Point':
        return [this.toCoord(input.coordinates)];
      case 'MultiPoint':
        return input.coordinates.map((coordinate) => this.toCoord(coordinate));
      case 'GeometryCollection':
        return input.geometries.flatMap((geometry) => this.extractPoints(geometry));
      default:
        return [];
    }
  }

  private stringifyProperties(properties: GeoJsonProperties): string {
    return Object.entries(properties ?? {})
      .flatMap(([key, value]) => [key, String(value)])
      .join(' ')
      .toLowerCase();
  }

  private hasKeyword(blob: string, keywords: string[]): boolean {
    return keywords.some((keyword) => blob.includes(keyword));
  }

  private buildTreePoints(boundary: Polygon[], treeDensity: string | null, seedBase: number): Scene['trees'] {
    const outerRings = boundary
      .map((polygon) => polygon[0])
      .filter((ring): ring is Point2D[] => Array.isArray(ring) && ring.length >= 3);
    if (!outerRings.length) {
      return [];
    }

    const bounds = outerRings.reduce(
      (acc, ring) => {
        ring.forEach((point) => {
          acc.minX = Math.min(acc.minX, point.x);
          acc.maxX = Math.max(acc.maxX, point.x);
          acc.minY = Math.min(acc.minY, point.y);
          acc.maxY = Math.max(acc.maxY, point.y);
        });
        return acc;
      },
      { minX: Number.POSITIVE_INFINITY, maxX: Number.NEGATIVE_INFINITY, minY: Number.POSITIVE_INFINITY, maxY: Number.NEGATIVE_INFINITY },
    );

    const density = (treeDensity ?? '').toLowerCase();
    const target =
      density.includes('dense') || density.includes('high')
        ? 180
        : density.includes('sparse') || density.includes('low')
          ? 72
          : 120;

    const random = this.mulberry32(seedBase || 1);
    const trees: Scene['trees'] = [];
    const maxAttempts = target * 18;
    let attempts = 0;

    while (trees.length < target && attempts < maxAttempts) {
      attempts += 1;
      const x = bounds.minX + random() * (bounds.maxX - bounds.minX);
      const y = bounds.minY + random() * (bounds.maxY - bounds.minY);
      const point = { x, y };
      if (!outerRings.some((ring) => this.isPointInside(point, ring))) {
        continue;
      }

      trees.push({
        ...point,
        size: 2.2 + random() * 4.4,
        alpha: 0.18 + random() * 0.24,
        hue: -6 + random() * 22,
      });
    }

    return trees;
  }

  private centroid(shape: Polygon | Point2D[]): Point2D | null {
    const ring = Array.isArray(shape[0]) && 'x' in shape[0] ? (shape as Point2D[]) : (shape as Polygon)[0];
    if (!ring.length) {
      return null;
    }

    let area = 0;
    let cx = 0;
    let cy = 0;
    for (let index = 0; index < ring.length; index += 1) {
      const current = ring[index];
      const next = ring[(index + 1) % ring.length];
      const factor = current.x * next.y - next.x * current.y;
      area += factor;
      cx += (current.x + next.x) * factor;
      cy += (current.y + next.y) * factor;
    }

    if (Math.abs(area) < 0.000001) {
      const avgX = ring.reduce((sum, point) => sum + point.x, 0) / ring.length;
      const avgY = ring.reduce((sum, point) => sum + point.y, 0) / ring.length;
      return { x: avgX, y: avgY };
    }

    const scale = 1 / (3 * area);
    return { x: cx * scale, y: cy * scale };
  }

  private isPointInside(point: Point2D, ring: Point2D[]): boolean {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i].x;
      const yi = ring[i].y;
      const xj = ring[j].x;
      const yj = ring[j].y;
      const intersect =
        yi > point.y !== yj > point.y &&
        point.x < ((xj - xi) * (point.y - yi)) / Math.max(yj - yi, 0.0000001) + xi;
      if (intersect) {
        inside = !inside;
      }
    }
    return inside;
  }

  private roundRect(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    radius: number,
    fill: boolean,
  ): void {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + width - r, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + r);
    ctx.lineTo(x + width, y + height - r);
    ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
    ctx.lineTo(x + r, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
    if (fill) {
      ctx.fill();
    } else {
      ctx.stroke();
    }
  }

  private clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
  }

  private toCoord(position: number[]): Coord {
    return [position[0] ?? 0, position[1] ?? 0];
  }

  private mulberry32(seed: number): () => number {
    let t = seed + 0x6d2b79f5;
    return () => {
      t += 0x6d2b79f5;
      let value = Math.imul(t ^ (t >>> 15), t | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  private releaseDownloadUrl(): void {
    const current = this.downloadUrl();
    if (current) {
      URL.revokeObjectURL(current);
      this.downloadUrl.set(null);
    }
  }
}
