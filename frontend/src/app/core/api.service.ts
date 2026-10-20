import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import {
  AutomationStatus,
  DashboardSummary,
  FireAnalysisResponse,
  FireSimulationResponse,
  ForestCreateRequest,
  ForestDetailResponse,
  ForestGeoJsonValidationResponse,
  ObservabilityStatus,
  ReadingHistoryResponse,
  WeatherCurrentResponse,
} from './api.models';

function resolveApiBaseUrl(): string {
  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:8000/api/v1';
  }

  const protocol = window.location.protocol || 'http:';
  const hostname = window.location.hostname || '127.0.0.1';
  const apiHost = hostname === 'localhost' ? '127.0.0.1' : hostname;

  return `${protocol}//${apiHost}:8000/api/v1`;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = resolveApiBaseUrl();

  getDashboardSummary() {
    return this.http.get<DashboardSummary>(`${this.baseUrl}/dashboard/summary`);
  }

  getAutomationStatus() {
    return this.http.get<AutomationStatus>(`${this.baseUrl}/system/automation`);
  }

  getObservabilityStatus() {
    return this.http.get<ObservabilityStatus>(`${this.baseUrl}/system/observability`);
  }

  getReadingsHistory(limit = 24, alarmOnly = false) {
    return this.http.get<ReadingHistoryResponse>(`${this.baseUrl}/readings/history`, {
      params: {
        limit,
        alarm_only: alarmOnly,
      },
    });
  }

  getCurrentForest() {
    return this.http.get<ForestDetailResponse | null>(`${this.baseUrl}/forests/current`);
  }

  createForest(payload: ForestCreateRequest) {
    return this.http.post<ForestDetailResponse>(`${this.baseUrl}/forests/create`, payload);
  }

  uploadGeoJson(
    file: File,
    metadata: Partial<Omit<ForestCreateRequest, 'boundary_geojson' | 'sensor_location' | 'source_geojson'>>,
  ) {
    const formData = new FormData();
    formData.append('file', file);

    Object.entries(metadata).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        formData.append(key, String(value));
      }
    });

    return this.http.post<ForestDetailResponse>(`${this.baseUrl}/forests/upload-geojson`, formData);
  }

  validateGeoJson(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<ForestGeoJsonValidationResponse>(`${this.baseUrl}/forests/validate-geojson`, formData);
  }

  getCurrentWeather(forceRefresh = false) {
    return this.http.get<WeatherCurrentResponse | null>(`${this.baseUrl}/weather/current`, {
      params: {
        force_refresh: forceRefresh,
      },
    });
  }

  getLatestSimulation() {
    return this.http.get<FireSimulationResponse | null>(`${this.baseUrl}/simulations/latest`);
  }

  runSimulation(hours: number, cellSizeM: number, forceWeatherRefresh = false) {
    return this.http.post<FireSimulationResponse>(`${this.baseUrl}/simulations/run`, null, {
      params: {
        hours,
        cell_size_m: cellSizeM,
        force_weather_refresh: forceWeatherRefresh,
      },
    });
  }

  getLatestAnalysis() {
    return this.http.get<FireAnalysisResponse | null>(`${this.baseUrl}/analysis/latest`);
  }

  generateAnalysis() {
    return this.http.post<FireAnalysisResponse>(`${this.baseUrl}/analysis/generate`, null);
  }

  getLatestAnalysisReportUrl() {
    return `${this.baseUrl}/analysis/latest/report.pdf`;
  }
}
