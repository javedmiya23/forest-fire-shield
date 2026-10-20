import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-placeholder-page',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="mx-auto max-w-4xl">
      <div class="rounded-[2.2rem] border border-white/10 bg-white/5 p-8 shadow-2xl shadow-black/20 backdrop-blur-xl sm:p-10">
        <p class="text-xs uppercase tracking-[0.34em] text-orange-200/70">{{ data.eyebrow }}</p>
        <h1 class="mt-4 font-display text-4xl text-white sm:text-5xl">{{ data.title }}</h1>
        <p class="mt-6 max-w-2xl text-base leading-8 text-stone-300">
          {{ data.description }}
        </p>

        <div class="mt-8 grid gap-4 sm:grid-cols-2">
          <a
            routerLink="/forest/setup"
            class="rounded-[1.6rem] border border-white/10 bg-[#08151d]/70 p-5 transition hover:border-emerald-300/20 hover:bg-white/8"
          >
            <p class="text-xs uppercase tracking-[0.26em] text-emerald-200/60">Prepare Data</p>
            <p class="mt-3 font-display text-2xl text-white">Forest Setup</p>
            <p class="mt-2 text-sm text-stone-300">Make sure the forest boundary, sensor point, and ecological metadata are in place first.</p>
          </a>
          <a
            routerLink="/dashboard"
            class="rounded-[1.6rem] border border-white/10 bg-[#08151d]/70 p-5 transition hover:border-orange-300/20 hover:bg-white/8"
          >
            <p class="text-xs uppercase tracking-[0.26em] text-orange-200/60">Monitor Live</p>
            <p class="mt-3 font-display text-2xl text-white">Control Room</p>
            <p class="mt-2 text-sm text-stone-300">Use the live dashboard to confirm sensor flow, weather sync, and event behavior.</p>
          </a>
        </div>
      </div>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlaceholderPageComponent {
  protected readonly data = inject(ActivatedRoute).snapshot.data as {
    eyebrow: string;
    title: string;
    description: string;
  };
}
