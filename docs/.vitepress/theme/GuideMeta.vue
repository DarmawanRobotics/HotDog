<script setup lang="ts">
// The head of a guide page: what the PDF's cover and front pages say (front matter of the
// guide), with the PDF to download.
import { computed } from 'vue';
import { useData, withBase } from 'vitepress';

const props = defineProps<{ pdf: string }>();
const { frontmatter } = useData();

// YAML dates reach the page as ISO timestamps: the day is enough.
const day = (value: unknown) => String(value ?? '').replace(/^(\d{4}-\d\d-\d\d)T.*$/, '$1');

// `code` in the front matter's prose, the rest as text.
const inline = (text: unknown) =>
  String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code>$1</code>');

const revisions = computed(() =>
  (frontmatter.value.revisions ?? []).map(([version, date, change]: unknown[]) => ({
    version: String(version),
    date: day(date),
    change: String(change),
  })),
);
</script>

<template>
  <div class="guide-meta">
    <p v-if="frontmatter.subtitle" class="guide-subtitle">{{ frontmatter.subtitle }}</p>
    <div class="guide-row">
      <span class="guide-version">Version {{ frontmatter.version }}</span>
      <span class="guide-date">{{ day(frontmatter.date) }}</span>
      <a class="guide-pdf" :href="withBase(`/${props.pdf}`)" target="_blank" rel="noopener">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3v12m0 0-5-5m5 5 5-5M4 19h16" />
        </svg>
        PDF (A5)
      </a>
    </div>
    <p v-if="frontmatter.audience" class="guide-audience" v-html="inline(frontmatter.audience)" />
    <details v-if="frontmatter.note || revisions.length" class="guide-about">
      <summary>About this guide</summary>
      <p v-if="frontmatter.note" v-html="inline(frontmatter.note)" />
      <table v-if="revisions.length">
        <thead>
          <tr><th>Version</th><th>Date</th><th>Changes</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in revisions" :key="r.version">
            <td>{{ r.version }}</td><td>{{ r.date }}</td><td>{{ r.change }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </div>
</template>
