export type BasemapMode = 'hybrid' | 'street';

const MAPTILER_API_KEY = 'xoUV9pcfNKlsZKg54cDC';

export function defaultBasemapMode(): BasemapMode {
  return MAPTILER_API_KEY ? 'hybrid' : 'street';
}

export function hasPremiumBasemap(): boolean {
  return MAPTILER_API_KEY.trim().length > 0;
}

export function resolveBasemapStyle(mode: BasemapMode): string {
  if (!hasPremiumBasemap()) {
    return 'https://demotiles.maplibre.org/style.json';
  }

  if (mode === 'hybrid') {
    return `https://api.maptiler.com/maps/hybrid/style.json?key=${MAPTILER_API_KEY}`;
  }

  return `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_API_KEY}`;
}

