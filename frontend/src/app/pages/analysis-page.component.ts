import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin } from 'rxjs';

import { ApiService } from '../core/api.service';
import { FireAnalysisResponse, FireSimulationResponse, ForestDetailResponse } from '../core/api.models';
import { ForestMapComponent } from '../shared/components/forest-map/forest-map.component';

@Component({
  selector: 'app-analysis-page',
  standalone: true,
  imports: [CommonModule, RouterLink, ForestMapComponent],
  templateUrl: './analysis-page.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalysisPageComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly reportDownloadUrl = this.api.getLatestAnalysisReportUrl();
  protected readonly forest = signal<ForestDetailResponse | null>(null);
  protected readonly simulation = signal<FireSimulationResponse | null>(null);
  protected readonly analysis = signal<FireAnalysisResponse | null>(null);
  protected readonly generating = signal(false);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal('');

  protected readonly impactedOverlay = computed(() => this.simulation()?.steps.at(-1)?.affected_geojson ?? null);
  protected readonly impactLevelClass = computed(() => {
    const level = this.analysis()?.impact_level ?? '';
    if (level === 'critical') {
      return 'alert-chip status-chip';
    }
    if (level === 'high') {
      return 'rounded-full border border-orange-300/20 bg-orange-300/10 px-3 py-1 text-xs text-orange-50';
    }
    if (level === 'moderate') {
      return 'rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs text-amber-50';
    }
    return 'status-chip';
  });

  constructor() {
    this.loadPage();
  }

  protected generateAnalysis(): void {
    this.generating.set(true);
    this.errorMessage.set('');

    this.api
      .generateAnalysis()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (analysis) => {
          this.analysis.set(analysis);
          this.generating.set(false);
        },
        error: (error) => {
          this.generating.set(false);
          this.errorMessage.set(error?.error?.detail || 'Impact analysis could not be generated.');
        },
      });
  }

  protected downloadPdfReport(): void {
    if (!this.analysis()) {
      return;
    }
    window.open(this.reportDownloadUrl, '_blank', 'noopener');
  }

  private loadPage(): void {
    forkJoin({
      forest: this.api.getCurrentForest(),
      simulation: this.api.getLatestSimulation(),
      analysis: this.api.getLatestAnalysis(),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ forest, simulation, analysis }) => {
          this.forest.set(forest);
          this.simulation.set(simulation);
          this.analysis.set(analysis);
          this.loading.set(false);
        },
        error: (error) => {
          this.errorMessage.set(error?.error?.detail || 'Analysis workspace could not be loaded.');
          this.loading.set(false);
        },
      });
  }
}
