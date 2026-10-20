import { ChangeDetectionStrategy, Component, DestroyRef, OnDestroy, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin } from 'rxjs';

import { ApiService } from '../core/api.service';
import { FireSimulationResponse, FireSimulationStepResponse, ForestDetailResponse } from '../core/api.models';
import { ForestMapComponent } from '../shared/components/forest-map/forest-map.component';
import { SimulationReelComponent } from '../shared/components/simulation-reel/simulation-reel.component';

@Component({
  selector: 'app-simulation-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, ForestMapComponent, SimulationReelComponent],
  templateUrl: './simulation-page.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SimulationPageComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly forest = signal<ForestDetailResponse | null>(null);
  protected readonly simulation = signal<FireSimulationResponse | null>(null);
  protected readonly running = signal(false);
  protected readonly loading = signal(true);
  protected readonly playing = signal(false);
  protected readonly selectedHour = signal(1);
  protected readonly errorMessage = signal('');

  protected readonly runForm = this.fb.group({
    hours: this.fb.nonNullable.control(6, [Validators.min(1), Validators.max(24)]),
    cell_size_m: this.fb.nonNullable.control(45, [Validators.min(15), Validators.max(250)]),
    force_weather_refresh: this.fb.nonNullable.control(false),
  });

  protected readonly steps = computed(() => this.simulation()?.steps ?? []);
  protected readonly selectedStep = computed<FireSimulationStepResponse | null>(() => {
    const items = this.steps();
    const hour = this.selectedHour();
    return items.find((item) => item.hour_offset === hour) ?? items[0] ?? null;
  });
  protected readonly selectedStepIndex = computed(() => {
    const step = this.selectedStep();
    if (!step) {
      return 0;
    }
    return this.steps().findIndex((item) => item.hour_offset === step.hour_offset);
  });
  protected readonly maxEstimatedArea = computed(() =>
    this.steps().reduce((max, step) => Math.max(max, step.estimated_area_m2), 0),
  );
  protected readonly playbackProgress = computed(() => {
    const step = this.selectedStep();
    const items = this.steps();
    if (!step || items.length === 0) {
      return 0;
    }
    return Math.round((step.hour_offset / items.length) * 100);
  });
  protected readonly compatibleSimulation = computed(() => {
    const forest = this.forest();
    const simulation = this.simulation();
    if (!forest || !simulation) {
      return null;
    }

    if (simulation.forest_id === forest.id) {
      return simulation;
    }

    return null;
  });
  protected readonly effectiveSensorLocation = computed(
    () => this.compatibleSimulation()?.ignition_point ?? this.forest()?.sensor_location ?? null,
  );
  protected readonly effectiveWindDirection = computed(
    () => this.compatibleSimulation()?.weather?.wind_direction ?? null,
  );

  private playbackTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    forkJoin({
      forest: this.api.getCurrentForest(),
      simulation: this.api.getLatestSimulation(),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ forest, simulation }) => {
          this.forest.set(forest);
          const compatibleSimulation = forest && simulation && simulation.forest_id === forest.id ? simulation : null;
          this.simulation.set(compatibleSimulation);
          if (compatibleSimulation?.steps.length) {
            this.selectedHour.set(compatibleSimulation.steps[0].hour_offset);
          } else {
            this.selectedHour.set(1);
          }
          this.loading.set(false);
        },
        error: (error) => {
          this.errorMessage.set(error?.error?.detail || 'Simulation workspace could not be loaded.');
          this.loading.set(false);
        },
      });
  }

  ngOnDestroy(): void {
    this.stopPlayback();
  }

  protected runSimulation(): void {
    if (this.runForm.invalid) {
      this.runForm.markAllAsTouched();
      return;
    }

    const { hours, cell_size_m, force_weather_refresh } = this.runForm.getRawValue();
    this.running.set(true);
    this.errorMessage.set('');

    this.api
      .runSimulation(hours, cell_size_m, force_weather_refresh)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (simulation) => {
          this.simulation.set(simulation);
          this.selectedHour.set(simulation.steps[0]?.hour_offset ?? 1);
          this.running.set(false);
          this.playing.set(false);
          this.stopPlayback();
        },
        error: (error) => {
          this.running.set(false);
          this.errorMessage.set(error?.error?.detail || 'Simulation run failed.');
        },
      });
  }

  protected selectHour(hour: number): void {
    this.selectedHour.set(hour);
  }

  protected togglePlayback(): void {
    if (!this.steps().length) {
      return;
    }

    if (this.playing()) {
      this.stopPlayback();
      this.playing.set(false);
      return;
    }

    this.playing.set(true);
    this.playbackTimer = setInterval(() => {
      const items = this.steps();
      const currentIndex = this.selectedStepIndex();
      const nextIndex = currentIndex + 1;

      if (nextIndex >= items.length) {
        this.selectedHour.set(items[0].hour_offset);
        return;
      }

      this.selectedHour.set(items[nextIndex].hour_offset);
    }, 1200);
  }

  protected stepAreaPercent(step: FireSimulationStepResponse): number {
    const maxArea = this.maxEstimatedArea();
    if (!maxArea) {
      return 0;
    }
    return Math.max(8, Math.round((step.estimated_area_m2 / maxArea) * 100));
  }

  protected formatHeading(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return 'Not enough spread movement';
    }
    return `${Math.round(value)} deg`;
  }

  private stopPlayback(): void {
    if (this.playbackTimer !== null) {
      clearInterval(this.playbackTimer);
      this.playbackTimer = null;
    }
  }
}
