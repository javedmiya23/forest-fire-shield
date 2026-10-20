import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import gsap from 'gsap';

@Component({
  selector: 'app-home-page',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section #heroSection class="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
      <div class="space-y-8">
        <div class="inline-flex items-center gap-3 rounded-full border border-orange-300/20 bg-orange-300/8 px-4 py-2 text-sm text-orange-100/90 shadow-lg shadow-orange-900/10">
          <span class="h-2.5 w-2.5 rounded-full bg-orange-300 shadow-[0_0_20px_rgba(253,186,116,0.8)]"></span>
          Advanced Forest Fire Intelligence for Real-World ESP32 Deployments
        </div>

        <div class="space-y-6">
          <p class="hero-item max-w-2xl font-display text-5xl leading-[0.95] tracking-tight text-white sm:text-6xl xl:text-7xl">
            See your forest as a living system, not just a sensor feed.
          </p>
          <p class="hero-item max-w-2xl text-lg leading-8 text-stone-300">
            Forest Fire Shield combines ESP32 telemetry, map-based forest context, live weather enrichment, and a control-room interface designed for high-stakes monitoring.
          </p>
        </div>

        <div class="hero-item flex flex-col gap-4 sm:flex-row">
          <a
            routerLink="/forest/setup"
            class="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-orange-400 via-amber-300 to-emerald-300 px-6 py-3 text-sm font-semibold text-slate-950 shadow-xl shadow-orange-900/30 transition hover:-translate-y-0.5"
          >
            Create Your Forest Map
          </a>
          <a
            routerLink="/dashboard"
            class="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/5 px-6 py-3 text-sm font-semibold text-stone-100 transition hover:border-orange-300/30 hover:bg-white/10"
          >
            Open Control Room
          </a>
        </div>

        <div class="hero-item grid gap-4 sm:grid-cols-3">
          <article class="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-md">
            <p class="text-xs uppercase tracking-[0.28em] text-emerald-200/60">Detection</p>
            <p class="mt-3 font-display text-3xl text-white">6</p>
            <p class="mt-2 text-sm text-stone-300">Smoke, gas, flame, and IR streams aligned into one event pipeline.</p>
          </article>
          <article class="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-md">
            <p class="text-xs uppercase tracking-[0.28em] text-orange-200/60">Context</p>
            <p class="mt-3 font-display text-3xl text-white">Geo</p>
            <p class="mt-2 text-sm text-stone-300">Forest boundaries, vegetation, and sensor location anchored on the map.</p>
          </article>
          <article class="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-md">
            <p class="text-xs uppercase tracking-[0.28em] text-sky-200/60">Weather</p>
            <p class="mt-3 font-display text-3xl text-white">Live</p>
            <p class="mt-2 text-sm text-stone-300">Temperature, humidity, wind speed, and direction tied to the forest site.</p>
          </article>
        </div>
      </div>

      <div class="hero-preview space-y-5">
        <div class="rounded-[2rem] border border-white/10 bg-[#08151d]/80 p-5 shadow-2xl shadow-black/30 backdrop-blur-xl">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs uppercase tracking-[0.28em] text-stone-400">Operations Snapshot</p>
              <h2 class="mt-2 font-display text-2xl text-white">Control Room Layout</h2>
            </div>
            <span class="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-xs text-emerald-100">System Ready</span>
          </div>

          <div class="mt-6 grid gap-4">
            <div class="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
              <div class="rounded-[1.6rem] border border-white/10 bg-[linear-gradient(135deg,rgba(14,116,144,0.2),rgba(6,78,59,0.2))] p-4">
                <div class="flex items-center justify-between">
                  <p class="text-sm text-stone-200">Forest Map Intelligence</p>
                  <span class="rounded-full bg-white/10 px-3 py-1 text-xs text-stone-300">GeoJSON + Sensor Point</span>
                </div>
                <div class="mt-4 h-48 overflow-hidden rounded-[1.2rem] border border-white/10 bg-[radial-gradient(circle_at_center,_rgba(16,185,129,0.35),_transparent_38%),linear-gradient(180deg,_rgba(15,23,42,0.2),_rgba(2,6,23,0.85))]">
                  <div class="relative h-full">
                    <div class="absolute inset-x-10 top-8 h-24 rounded-[40%] border border-orange-300/40 bg-orange-300/10"></div>
                    <div class="absolute left-[46%] top-[40%] h-5 w-5 rounded-full bg-orange-300 shadow-[0_0_30px_rgba(251,146,60,0.8)]"></div>
                    <div class="absolute right-6 top-6 text-right text-xs uppercase tracking-[0.22em] text-stone-300/70">
                      Wind-aware boundary preview
                    </div>
                  </div>
                </div>
              </div>

              <div class="space-y-4">
                <div class="rounded-[1.6rem] border border-white/10 bg-white/5 p-4">
                  <p class="text-xs uppercase tracking-[0.26em] text-sky-200/60">Weather Feed</p>
                  <div class="mt-4 grid gap-3 sm:grid-cols-2">
                    <div class="rounded-2xl bg-white/5 p-3">
                      <p class="text-2xl font-semibold text-white">22.6°</p>
                      <p class="text-xs text-stone-400">Temperature</p>
                    </div>
                    <div class="rounded-2xl bg-white/5 p-3">
                      <p class="text-2xl font-semibold text-white">18 km/h</p>
                      <p class="text-xs text-stone-400">Wind Speed</p>
                    </div>
                    <div class="rounded-2xl bg-white/5 p-3">
                      <p class="text-2xl font-semibold text-white">56%</p>
                      <p class="text-xs text-stone-400">Humidity</p>
                    </div>
                    <div class="rounded-2xl bg-white/5 p-3">
                      <p class="text-2xl font-semibold text-white">NW</p>
                      <p class="text-xs text-stone-400">Direction</p>
                    </div>
                  </div>
                </div>

                <div class="rounded-[1.6rem] border border-white/10 bg-gradient-to-br from-orange-400/15 to-red-500/10 p-4">
                  <p class="text-xs uppercase tracking-[0.26em] text-orange-200/70">Simulation Track</p>
                  <div class="mt-4 space-y-3">
                    <div class="flex items-center justify-between text-sm text-stone-200">
                      <span>Hour 1</span>
                      <span>Ignition zone mapped</span>
                    </div>
                    <div class="flex items-center justify-between text-sm text-stone-200">
                      <span>Hour 3</span>
                      <span>Wind-biased expansion</span>
                    </div>
                    <div class="flex items-center justify-between text-sm text-stone-200">
                      <span>Hour 6</span>
                      <span>Impact corridor estimate</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="mt-14 grid gap-6 lg:grid-cols-3">
      <article class="rounded-[2rem] border border-white/10 bg-white/5 p-6">
        <p class="text-xs uppercase tracking-[0.28em] text-emerald-200/60">Step 1</p>
        <h3 class="mt-4 font-display text-2xl text-white">Build the forest context</h3>
        <p class="mt-4 text-sm leading-7 text-stone-300">
          Upload GeoJSON or create a forest model from latitude, longitude, vegetation, density, and fuel characteristics.
        </p>
      </article>
      <article class="rounded-[2rem] border border-white/10 bg-white/5 p-6">
        <p class="text-xs uppercase tracking-[0.28em] text-orange-200/60">Step 2</p>
        <h3 class="mt-4 font-display text-2xl text-white">Watch the live control room</h3>
        <p class="mt-4 text-sm leading-7 text-stone-300">
          See the latest sensor reading, connectivity, alarm state, and weather context with a responsive dashboard.
        </p>
      </article>
      <article class="rounded-[2rem] border border-white/10 bg-white/5 p-6">
        <p class="text-xs uppercase tracking-[0.28em] text-sky-200/60">Step 3</p>
        <h3 class="mt-4 font-display text-2xl text-white">Extend to prediction and analysis</h3>
        <p class="mt-4 text-sm leading-7 text-stone-300">
          Plug in fire spread simulation, post-event reports, and admin alerting as the backend evolves.
        </p>
      </article>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomePageComponent implements AfterViewInit {
  @ViewChild('heroSection', { static: true }) private readonly heroSection?: ElementRef<HTMLElement>;

  ngAfterViewInit(): void {
    if (!this.heroSection) {
      return;
    }

    const hero = this.heroSection.nativeElement;
    gsap.from(hero.querySelectorAll('.hero-item'), {
      y: 28,
      opacity: 0,
      duration: 0.9,
      ease: 'power3.out',
      stagger: 0.12,
    });

    gsap.from(hero.querySelector('.hero-preview'), {
      x: 36,
      opacity: 0,
      duration: 1.1,
      ease: 'power3.out',
      delay: 0.2,
    });
  }
}
