import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin, timer } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { ApiService } from '../core/api.service';
import { LiveStreamService } from '../core/live-stream.service';
import {
  AutomationJobStatus,
  AutomationStatus,
  DashboardSummary,
  ForestDetailResponse,
  LiveStreamEvent,
  ObservabilityStatus,
  SensorReadingSummary,
} from '../core/api.models';
import { ForestMapComponent } from '../shared/components/forest-map/forest-map.component';

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [CommonModule, RouterLink, ForestMapComponent],
  templateUrl: './dashboard-page.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardPageComponent {
  private readonly api = inject(ApiService);
  private readonly liveStream = inject(LiveStreamService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly summary = signal<DashboardSummary | null>(null);
  protected readonly automation = signal<AutomationStatus | null>(null);
  protected readonly observability = signal<ObservabilityStatus | null>(null);
  protected readonly history = signal<SensorReadingSummary[]>([]);
  protected readonly forest = signal<ForestDetailResponse | null>(null);
  protected readonly errorMessage = signal('');
  protected readonly liveConnectionState = this.liveStream.connectionState;
  protected readonly liveEventAt = this.liveStream.lastEventAt;
  protected readonly latestReading = computed(() => this.summary()?.latest_reading ?? null);
  protected readonly orderedHistory = computed(() => [...this.history()].reverse());
  protected readonly displayedFireEvent = computed(
    () => this.summary()?.active_fire_event ?? this.summary()?.latest_fire_event ?? null,
  );
  protected readonly severityTrend = computed(() => {
    const items = this.orderedHistory();
    if (!items.length) {
      return {
        polyline: '',
        area: '',
        points: [] as Array<{ x: number; y: number; reading: SensorReadingSummary }>,
      };
    }

    const width = 100;
    const height = 42;
    const step = items.length > 1 ? width / (items.length - 1) : 0;
    const points = items.map((reading, index) => ({
      x: Number((index * step).toFixed(2)),
      y: Number((height - (reading.severity_score / 100) * height).toFixed(2)),
      reading,
    }));
    const polyline = points.map((point) => `${point.x},${point.y}`).join(' ');
    const area = polyline ? `${polyline} ${width},${height} 0,${height}` : '';

    return { polyline, area, points };
  });
  protected readonly latestSeverityDelta = computed(() => {
    const items = this.orderedHistory();
    if (items.length < 2) {
      return null;
    }
    return items.at(-1)!.severity_score - items.at(-2)!.severity_score;
  });
  protected readonly alarmWindowCount = computed(() => this.history().filter((reading) => reading.fire_logic.alarm).length);
  protected readonly triggerMix = computed(() => {
    const counts = new Map<string, number>();
    this.history().forEach((reading) => {
      const key = (reading.fire_logic.trigger || 'none').toLowerCase();
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    const [top] = [...counts.entries()].sort((left, right) => right[1] - left[1]);
    return top ? `${top[0]} (${top[1]})` : 'none';
  });

  constructor() {
    timer(0, 12000)
      .pipe(
        switchMap(() =>
          forkJoin({
            summary: this.api.getDashboardSummary(),
            automation: this.api.getAutomationStatus(),
            observability: this.api.getObservabilityStatus(),
            history: this.api.getReadingsHistory(14),
            forest: this.api.getCurrentForest(),
          }),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: ({ summary, automation, observability, history, forest }) => {
          this.summary.set(summary);
          this.automation.set(automation);
          this.observability.set(observability);
          this.history.set(history.items);
          this.forest.set(forest);
          this.errorMessage.set('');
        },
        error: (error) => {
          this.errorMessage.set(error?.error?.detail || 'Dashboard data could not be loaded.');
        },
      });

    this.liveStream
      .connect()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((event) => {
        if (event.type === 'sensor_update') {
          this.applyLiveSensorEvent(event);
        }
      });
  }

  protected manualRefresh(): void {
    forkJoin({
      summary: this.api.getDashboardSummary(),
      automation: this.api.getAutomationStatus(),
      observability: this.api.getObservabilityStatus(),
      history: this.api.getReadingsHistory(14),
      forest: this.api.getCurrentForest(),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ summary, automation, observability, history, forest }) => {
          this.summary.set(summary);
          this.automation.set(automation);
          this.observability.set(observability);
          this.history.set(history.items);
          this.forest.set(forest);
          this.errorMessage.set('');
        },
        error: (error) => {
          this.errorMessage.set(error?.error?.detail || 'Dashboard refresh failed.');
        },
      });
  }

  protected prettyStatus(status: string | undefined): string {
    if (!status) {
      return 'Unknown';
    }

    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  protected statusSummaryText(): string {
    const deviceStatus = this.summary()?.device_status;
    if (!deviceStatus) {
      return 'Waiting for device heartbeat.';
    }

    if (deviceStatus.seconds_since_last_seen === null) {
      return 'No heartbeat has been stored yet.';
    }

    return `Last packet ${deviceStatus.seconds_since_last_seen}s ago.`;
  }

  protected sensorPanels(reading: SensorReadingSummary): Array<{
    label: string;
    analog: number;
    digitalLabel: string;
    fill: number;
  }> {
    const channels = [
      { label: 'MQ2', data: reading.gas_sensors.mq2 },
      { label: 'MQ4', data: reading.gas_sensors.mq4 },
      { label: 'MQ7', data: reading.gas_sensors.mq7 },
      { label: 'MQ135', data: reading.gas_sensors.mq135 },
    ];

    return channels.map((channel) => ({
      label: channel.label,
      analog: channel.data.analog,
      digitalLabel: channel.data.digital === 0 ? 'Triggered' : 'Nominal',
      fill: Math.min(Math.round((channel.data.analog / 4095) * 100), 100),
    }));
  }

  protected fireAlertLabel(): string {
    const fireEvent = this.displayedFireEvent();
    if (!fireEvent) {
      return 'Armed';
    }
    return fireEvent.alert_sent ? 'Email Sent' : 'Pending';
  }

  protected fireAlertTone(): string {
    const fireEvent = this.displayedFireEvent();
    if (!fireEvent) {
      return 'status-chip';
    }
    if (fireEvent.alert_sent) {
      return 'status-chip';
    }
    return 'alert-chip status-chip';
  }

  protected fireAlertSummaryText(): string {
    const fireEvent = this.displayedFireEvent();
    if (!fireEvent) {
      return 'SMTP alerting is ready. The backend will send mail when an ESP32 alarm opens a fire event.';
    }

    if (fireEvent.status === 'active') {
      return 'This event is active. The backend has already attempted the SMTP alert for it.';
    }

    return 'Showing the latest fire event so the last email dispatch result stays visible after resolution.';
  }

  protected automationJobs(): AutomationJobStatus[] {
    const automation = this.automation();
    if (!automation) {
      return [];
    }

    return [automation.weather_refresh, automation.fire_event_cleanup, automation.device_status_sync];
  }

  protected automationLabel(jobName: string): string {
    if (jobName === 'weather_refresh') {
      return 'Weather Refresh';
    }
    if (jobName === 'fire_event_cleanup') {
      return 'Fire Cleanup';
    }
    if (jobName === 'device_status_sync') {
      return 'Device Sync';
    }
    return jobName.replaceAll('_', ' ');
  }

  protected automationTone(status: string | undefined): string {
    if (status === 'ok') {
      return 'status-chip';
    }
    if (status === 'running') {
      return 'rounded-full border border-sky-300/20 bg-sky-300/10 px-3 py-1 text-xs text-sky-50';
    }
    if (status === 'error') {
      return 'alert-chip status-chip';
    }
    return 'rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300';
  }

  protected automationSummaryText(): string {
    const automation = this.automation();
    if (!automation) {
      return 'Automation status is loading.';
    }
    if (!automation.enabled) {
      return 'Background jobs are disabled. Weather refresh, device sync, and stale fire cleanup run only on direct API activity.';
    }
    return `Automation worker polls every ${automation.poll_interval_seconds}s. Stale fire events resolve after ${automation.stale_fire_event_seconds}s without an alarm heartbeat.`;
  }

  protected historyTimeLabel(timestamp: string): string {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(timestamp));
  }

  protected severityDeltaLabel(): string {
    const delta = this.latestSeverityDelta();
    if (delta === null) {
      return 'Stabilizing';
    }
    if (delta === 0) {
      return 'No change';
    }
    if (delta > 0) {
      return `+${delta} rising`;
    }
    return `${delta} easing`;
  }

  protected severityDeltaTone(): string {
    const delta = this.latestSeverityDelta();
    if (delta === null || delta === 0) {
      return 'rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300';
    }
    if (delta > 0) {
      return 'rounded-full border border-orange-300/25 bg-orange-300/10 px-3 py-1 text-xs text-orange-50';
    }
    return 'rounded-full border border-emerald-300/25 bg-emerald-300/10 px-3 py-1 text-xs text-emerald-50';
  }

  protected packetBarTone(reading: SensorReadingSummary): string {
    if (reading.fire_logic.alarm) {
      return 'bg-gradient-to-t from-red-500 via-orange-400 to-amber-300';
    }
    if (reading.severity_score >= 65) {
      return 'bg-gradient-to-t from-orange-500 via-amber-400 to-yellow-200';
    }
    return 'bg-gradient-to-t from-emerald-400 via-sky-300 to-cyan-200';
  }

  protected packetBarHeight(reading: SensorReadingSummary): number {
    return Math.max(reading.severity_score, 10);
  }

  protected readingStatusTone(reading: SensorReadingSummary): string {
    if (reading.fire_logic.alarm) {
      return 'alert-chip status-chip';
    }
    if (reading.severity_score >= 65) {
      return 'rounded-full border border-orange-300/20 bg-orange-300/10 px-3 py-1 text-xs text-orange-50';
    }
    return 'status-chip';
  }

  protected activeSignals(reading: SensorReadingSummary): string[] {
    const signals: string[] = [];
    if (reading.gas_sensors.mq2.digital === 0) {
      signals.push('MQ2');
    }
    if (reading.gas_sensors.mq4.digital === 0) {
      signals.push('MQ4');
    }
    if (reading.gas_sensors.mq7.digital === 0) {
      signals.push('MQ7');
    }
    if (reading.gas_sensors.mq135.digital === 0) {
      signals.push('MQ135');
    }
    if (reading.flame_sensor.detected) {
      signals.push('Flame');
    }
    if (reading.ir_sensor.detected) {
      signals.push('IR');
    }
    return signals.slice(0, 4);
  }

  protected liveTransportLabel(): string {
    if (this.liveConnectionState() === 'connected') {
      return 'WebSocket Live';
    }
    if (this.liveConnectionState() === 'connecting') {
      return 'Connecting';
    }
    return 'Polling Fallback';
  }

  protected liveTransportTone(): string {
    if (this.liveConnectionState() === 'connected') {
      return 'status-chip';
    }
    if (this.liveConnectionState() === 'connecting') {
      return 'rounded-full border border-sky-300/20 bg-sky-300/10 px-3 py-1 text-xs text-sky-50';
    }
    return 'rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300';
  }

  protected observabilityTone(): string {
    if (this.observability()?.enabled) {
      return 'status-chip';
    }
    return 'rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300';
  }

  private applyLiveSensorEvent(event: LiveStreamEvent): void {
    const reading = event.reading;
    if (!reading) {
      return;
    }

    const alreadyPresent = this.history().some((item) => item.id === reading.id);

    this.history.update((items) => [reading, ...items.filter((item) => item.id !== reading.id)].slice(0, 14));

    this.summary.update((summary) => {
      if (!summary) {
        return summary;
      }

      const nextMetrics = {
        ...summary.metrics,
        total_readings: summary.metrics.total_readings + (alreadyPresent ? 0 : 1),
        readings_last_24h: summary.metrics.readings_last_24h + (alreadyPresent ? 0 : 1),
        alarm_readings_last_24h:
          summary.metrics.alarm_readings_last_24h + (!alreadyPresent && reading.fire_logic.alarm ? 1 : 0),
        max_severity_last_24h: Math.max(summary.metrics.max_severity_last_24h ?? 0, reading.severity_score),
        latest_alarm_at: reading.fire_logic.alarm ? reading.recorded_at : summary.metrics.latest_alarm_at,
      };

      return {
        ...summary,
        generated_at: event.timestamp,
        latest_reading: reading,
        device_status: event.device_status ?? summary.device_status,
        active_fire_event: event.fire_event?.status === 'active' ? event.fire_event : null,
        latest_fire_event: event.fire_event ?? summary.latest_fire_event,
        metrics: nextMetrics,
      };
    });
  }
}
