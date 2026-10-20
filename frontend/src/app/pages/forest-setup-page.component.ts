import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormArray, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import type { Feature } from 'geojson';

import { ApiService } from '../core/api.service';
import {
  CoordinateResponse,
  ForestCreateRequest,
  ForestDetailResponse,
  ForestGeoJsonValidationResponse,
  GeoJsonDocument,
  GeometryPayload,
} from '../core/api.models';
import { ForestMapComponent } from '../shared/components/forest-map/forest-map.component';

type SetupMode = 'upload' | 'builder';

@Component({
  selector: 'app-forest-setup-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, ForestMapComponent],
  templateUrl: './forest-setup-page.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForestSetupPageComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly currentForest = signal<ForestDetailResponse | null>(null);
  protected readonly setupMode = signal<SetupMode>('upload');
  protected readonly builderStep = signal(1);
  protected readonly saving = signal(false);
  protected readonly uploading = signal(false);
  protected readonly validating = signal(false);
  protected readonly statusMessage = signal('');
  protected readonly errorMessage = signal('');
  protected readonly geoJsonValidation = signal<ForestGeoJsonValidationResponse | null>(null);
  protected readonly previewSourceGeoJson = signal<GeoJsonDocument | null>(null);
  private readonly selectedFile = signal<File | null>(null);

  protected readonly selectedFileName = computed(() => this.selectedFile()?.name ?? '');
  protected readonly builderSteps = [
    { id: 1, title: 'Forest Basics' },
    { id: 2, title: 'Sensor Point' },
    { id: 3, title: 'Boundary & Save' },
  ] as const;
  protected readonly uploadReady = computed(() => !!this.selectedFile() && !!this.geoJsonValidation()?.is_compatible);
  protected readonly displayedPropertyKeys = computed(() => this.geoJsonValidation()?.summary.property_keys.slice(0, 12) ?? []);
  protected readonly previewBoundary = computed(
    () => this.geoJsonValidation()?.boundary_geojson ?? this.currentForest()?.boundary_geojson ?? this.draftBoundaryGeojson(),
  );
  protected readonly previewSensor = computed(
    () => this.geoJsonValidation()?.sensor_location ?? this.currentForest()?.sensor_location ?? this.draftSensorLocation(),
  );
  protected readonly previewGeoJson = computed(
    () => this.previewSourceGeoJson() ?? this.currentForest()?.source_geojson ?? this.draftSourceGeojson(),
  );

  protected readonly forestForm = this.fb.group({
    name: this.fb.nonNullable.control('BNMIT Demo Forest', Validators.required),
    admin_email: this.fb.control('demo@example.com'),
    vegetation_type: this.fb.control('mixed_forest'),
    tree_density: this.fb.nonNullable.control('high'),
    canopy_density: this.fb.nonNullable.control('medium'),
    fuel_load: this.fb.nonNullable.control('moderate'),
    moisture_class: this.fb.nonNullable.control('dry'),
    sensor_latitude: this.fb.control<number | null>(12.9717, Validators.required),
    sensor_longitude: this.fb.control<number | null>(77.5952, Validators.required),
    boundaryPoints: this.fb.array([
      this.createBoundaryPoint(12.9708, 77.594),
      this.createBoundaryPoint(12.9708, 77.5964),
      this.createBoundaryPoint(12.9726, 77.5964),
      this.createBoundaryPoint(12.9726, 77.594),
    ]),
  });

  constructor() {
    this.loadCurrentForest();
  }

  protected get boundaryPoints(): FormArray {
    return this.forestForm.controls.boundaryPoints;
  }

  protected switchMode(mode: SetupMode): void {
    this.setupMode.set(mode);
    this.statusMessage.set('');
    this.errorMessage.set('');
  }

  protected setBuilderStep(step: number): void {
    this.builderStep.set(step);
  }

  protected nextBuilderStep(): void {
    this.builderStep.update((step) => Math.min(step + 1, this.builderSteps.length));
  }

  protected previousBuilderStep(): void {
    this.builderStep.update((step) => Math.max(step - 1, 1));
  }

  protected addBoundaryPoint(): void {
    this.boundaryPoints.push(this.createBoundaryPoint(null, null));
  }

  protected removeBoundaryPoint(index: number): void {
    if (this.boundaryPoints.length <= 3) {
      return;
    }
    this.boundaryPoints.removeAt(index);
  }

  protected async onGeoJsonSelected(event: Event): Promise<void> {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0] ?? null;

    this.selectedFile.set(file);
    this.geoJsonValidation.set(null);
    this.previewSourceGeoJson.set(null);
    this.statusMessage.set('');
    this.errorMessage.set('');

    if (!file) {
      return;
    }

    if (!/\.(geojson|json)$/i.test(file.name)) {
      this.errorMessage.set('Please choose a .geojson or .json file.');
      return;
    }

    try {
      const parsed = JSON.parse(await file.text()) as GeoJsonDocument;
      this.previewSourceGeoJson.set(parsed);
    } catch {
      this.errorMessage.set('The selected file could not be parsed as JSON.');
      return;
    }

    this.validating.set(true);
    this.api
      .validateGeoJson(file)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (validation) => {
          this.geoJsonValidation.set(validation);
          this.validating.set(false);
          if (!validation.is_compatible) {
            this.errorMessage.set(validation.message);
            return;
          }
          this.statusMessage.set(validation.message);
        },
        error: (error) => {
          this.validating.set(false);
          this.errorMessage.set(error?.error?.detail || 'GeoJSON validation failed.');
        },
      });
  }

  protected uploadGeoJson(): void {
    const file = this.selectedFile();
    const validation = this.geoJsonValidation();
    if (!file || !validation?.is_compatible) {
      return;
    }

    this.uploading.set(true);
    this.errorMessage.set('');
    this.statusMessage.set('');

    this.api
      .uploadGeoJson(file, {
        name: this.forestForm.controls.name.value,
        admin_email: this.forestForm.controls.admin_email.value,
        vegetation_type: this.forestForm.controls.vegetation_type.value,
        tree_density: this.forestForm.controls.tree_density.value,
        canopy_density: this.forestForm.controls.canopy_density.value,
        fuel_load: this.forestForm.controls.fuel_load.value,
        moisture_class: this.forestForm.controls.moisture_class.value,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (forest) => {
          this.currentForest.set(forest);
          this.statusMessage.set(`GeoJSON uploaded and linked to ${forest.name}.`);
          this.selectedFile.set(null);
          this.geoJsonValidation.set(null);
          this.previewSourceGeoJson.set(null);
          this.uploading.set(false);
        },
        error: (error) => {
          this.errorMessage.set(error?.error?.detail || 'GeoJSON upload failed.');
          this.uploading.set(false);
        },
      });
  }

  protected submitForestBuilder(): void {
    if (this.forestForm.invalid) {
      this.forestForm.markAllAsTouched();
      return;
    }

    const boundaryGeojson = this.draftBoundaryGeojson();
    if (!boundaryGeojson) {
      this.errorMessage.set('At least three valid boundary points are required.');
      return;
    }

    const sensorLocation = this.draftSensorLocation();
    const payload: ForestCreateRequest = {
      name: this.forestForm.controls.name.value,
      admin_email: this.forestForm.controls.admin_email.value,
      vegetation_type: this.forestForm.controls.vegetation_type.value,
      tree_density: this.forestForm.controls.tree_density.value,
      canopy_density: this.forestForm.controls.canopy_density.value,
      fuel_load: this.forestForm.controls.fuel_load.value,
      moisture_class: this.forestForm.controls.moisture_class.value,
      boundary_geojson: boundaryGeojson,
      sensor_location: sensorLocation
        ? {
            latitude: sensorLocation.latitude,
            longitude: sensorLocation.longitude,
          }
        : null,
      source_geojson: this.draftSourceGeojson(),
    };

    this.saving.set(true);
    this.statusMessage.set('');
    this.errorMessage.set('');

    this.api
      .createForest(payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (forest) => {
          this.currentForest.set(forest);
          this.statusMessage.set(`Forest model saved for ${forest.name}.`);
          this.saving.set(false);
        },
        error: (error) => {
          this.errorMessage.set(error?.error?.detail || 'Saving the forest model failed.');
          this.saving.set(false);
        },
      });
  }

  protected draftBoundaryGeojson(): GeometryPayload | null {
    const points = this.boundaryPoints
      .getRawValue()
      .map((point) => ({
        latitude: Number(point.latitude),
        longitude: Number(point.longitude),
      }))
      .filter((point) => Number.isFinite(point.latitude) && Number.isFinite(point.longitude));

    if (points.length < 3) {
      return null;
    }

    const coordinates = points.map((point) => [point.longitude, point.latitude]);
    const [firstLongitude, firstLatitude] = coordinates[0];
    const [lastLongitude, lastLatitude] = coordinates[coordinates.length - 1];

    if (firstLongitude !== lastLongitude || firstLatitude !== lastLatitude) {
      coordinates.push([firstLongitude, firstLatitude]);
    }

    return {
      type: 'Polygon',
      coordinates: [coordinates],
    };
  }

  protected draftSensorLocation(): CoordinateResponse | null {
    const latitude = this.forestForm.controls.sensor_latitude.value;
    const longitude = this.forestForm.controls.sensor_longitude.value;

    if (latitude === null || longitude === null || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      return null;
    }

    return {
      latitude,
      longitude,
      source: 'sensor_point',
    };
  }

  protected draftSourceGeojson(): GeoJsonDocument | null {
    const boundaryGeojson = this.draftBoundaryGeojson();
    if (!boundaryGeojson) {
      return null;
    }

    const features: Array<Feature> = [
      {
        type: 'Feature',
        properties: {
          name: this.forestForm.controls.name.value,
          admin_email: this.forestForm.controls.admin_email.value,
          vegetation_type: this.forestForm.controls.vegetation_type.value,
          tree_density: this.forestForm.controls.tree_density.value,
          canopy_density: this.forestForm.controls.canopy_density.value,
          fuel_load: this.forestForm.controls.fuel_load.value,
          moisture_class: this.forestForm.controls.moisture_class.value,
        },
        geometry: boundaryGeojson,
      },
    ];

    const sensor = this.draftSensorLocation();
    if (sensor) {
      features.push({
        type: 'Feature',
        properties: {
          name: 'esp32_sensor_point',
          device_id: 'FFS_ESP32_01',
        },
        geometry: {
          type: 'Point',
          coordinates: [sensor.longitude, sensor.latitude],
        },
      });
    }

    return {
      type: 'FeatureCollection',
      features,
    };
  }

  private createBoundaryPoint(latitude: number | null, longitude: number | null) {
    return this.fb.group({
      latitude: this.fb.control<number | null>(latitude, Validators.required),
      longitude: this.fb.control<number | null>(longitude, Validators.required),
    });
  }

  private loadCurrentForest(): void {
    this.api
      .getCurrentForest()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (forest) => {
          this.currentForest.set(forest);
        },
      });
  }
}
