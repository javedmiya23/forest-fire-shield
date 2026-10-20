import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/home-page.component').then((m) => m.HomePageComponent),
  },
  {
    path: 'forest/setup',
    loadComponent: () =>
      import('./pages/forest-setup-page.component').then((m) => m.ForestSetupPageComponent),
  },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./pages/dashboard-page.component').then((m) => m.DashboardPageComponent),
  },
  {
    path: 'simulation',
    loadComponent: () =>
      import('./pages/simulation-page.component').then((m) => m.SimulationPageComponent),
  },
  {
    path: 'analysis',
    loadComponent: () =>
      import('./pages/analysis-page.component').then((m) => m.AnalysisPageComponent),
  },
  {
    path: '**',
    redirectTo: '',
  },
];
