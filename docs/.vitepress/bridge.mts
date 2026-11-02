/**
 * The bridge between the guides as docs/pdf/build.py reads them (Python-Markdown) and VitePress:
 * one source for the PDFs and the site.
 *
 * - `!!! warning "Title"` admonitions become VitePress containers, `{: .class}` attributes
 *   `{.class}`, `{{ parameter_reference }}` the tables of docs/pdf/parameters.py.
 * - A guide (several `#` chapters) gets its title as the page's `#` and its chapters one level
 *   down, a <GuideMeta> header (version, PDF, audience) and the numbering of the PDF.
 * - A page can mirror a file outside docs/ (`<!--@source: ../CHANGELOG.md-->`): the package
 *   READMEs and the changelog are on the site without a copy.
 * - Relative links resolve against the real source file: to a page of the site, to a PDF next
 *   to it, or to the file on GitHub.
 */

import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type MarkdownIt from 'markdown-it';
import type { Plugin } from 'vite';

export const REPO = 'https://github.com/DarmawanRobotics/HotDog';
export const DOCS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const ROOT = path.dirname(DOCS);

/** The guides with a PDF, by source (relative to docs/). */
export const GUIDES: Record<string, string> = {
  'manual/user-manual.md': 'HotDog-User-Manual.pdf',
  'technician/technician-guide.md': 'HotDog-Technician-Guide.pdf',
  'acceptance/acceptance-test.md': 'HotDog-Site-Acceptance-Test.pdf',
};

/** The packages, each mirrored at /packages/<name> from src/<name>/README.md. */
export const PACKAGES = [
  'hotdog',
  'hotdog_base',
  'hotdog_inspection',
  'hotdog_patrol',
  'hotdog_reports',
  'hotdog_alerts',
  'hotdog_interfaces',
];

/** Files next to the pages, served at the site's root: the PDFs and the logo. */
export const ASSETS = ['logo.png', ...Object.values(GUIDES)];

const ADMONITIONS: Record<string, string> = {
  note: 'info',
  info: 'info',
  abstract: 'info',
  tip: 'tip',
  hint: 'tip',
  success: 'tip',
  important: 'warning',
  warning: 'warning',
  caution: 'warning',
  attention: 'warning',
  danger: 'danger',
  error: 'danger',
};

const SOURCE = /^<!--@source:\s*(\S+)\s*-->\s*$/m;
const FENCE = /^\s*(```|~~~)/;

let parameters = '';

/** The parameter reference in Markdown, from the packages' config files. */
function parameterReference(): string {
  parameters ||= execFileSync('python3', [path.join(DOCS, 'pdf', 'parameters.py')], {
    encoding: 'utf8',
  });
  return `::: v-pre\n${parameters}\n:::`;
}

/** Split a source into its front matter (with the --- lines) and its body. */
function frontMatter(src: string): [string, string] {
  const match = /^---\n[\s\S]*?\n---\n/.exec(src);
  return match ? [match[0], src.slice(match[0].length)] : ['', src];
}

/** Python-Markdown admonitions (`!!! type "title"` and a 4-space body) as containers. */
function admonitions(lines: string[]): string[] {
  const out: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const head = /^!!!\s+(\w+)(?:\s+"([^"]*)")?\s*$/.exec(lines[i]);
    if (!head) {
      out.push(lines[i]);
      continue;
    }
    const body: string[] = [];
    while (i + 1 < lines.length && (lines[i + 1].startsWith('    ') || !lines[i + 1].trim())) {
      body.push(lines[++i].slice(4));
    }
    while (body.length && !body[body.length - 1].trim()) body.pop();
    out.push(`::: ${ADMONITIONS[head[1]] ?? 'info'} ${head[2] ?? ''}`.trimEnd(), ...body, ':::', '');
  }
  return out;
}

/** Each line outside fenced code, through fn. */
function outsideCode(lines: string[], fn: (line: string) => string): string[] {
  let fence = false;
  return lines.map((line) => {
    if (FENCE.test(line)) fence = !fence;
    return fence || FENCE.test(line) ? line : fn(line);
  });
}

/** A guide as a page: its title on top, chapters one level down, the GuideMeta header. */
function guidePage(body: string, title: string, pdf: string): string {
  const lines = outsideCode(body.split('\n'), (line) => (/^#{1,5} /.test(line) ? `#${line}` : line));
  return [`# ${title}`, '', `<GuideMeta pdf="${pdf}" />`, '', ...lines].join('\n');
}

/** Python-Markdown `{: .class}` attributes in the markdown-it-attrs form `{.class}`. */
function attributes(line: string): string {
  return line.replace(/\{:\s*/g, '{');
}

/** The source as VitePress reads it; env gets the real source path for links. */
export function transform(src: string, env: Record<string, any>): string {
  const page = String(env.relativePath ?? '').replace(/\\/g, '/');
  env.hotdogSource = `docs/${page}`;
  const mirrored = SOURCE.exec(src);
  if (mirrored) {
    const file = path.resolve(DOCS, path.dirname(page), mirrored[1]);
    env.hotdogSource = path.relative(ROOT, file).replace(/\\/g, '/');
    src = src.replace(SOURCE, () => fs.readFileSync(file, 'utf8'));
  }
  if (!page.startsWith('pdf/') && src.includes('{{ parameter_reference }}')) {
    src = src.replace('{{ parameter_reference }}', parameterReference);
  }
  const [front, rest] = frontMatter(src);
  let body = outsideCode(admonitions(rest.split('\n')), attributes).join('\n');
  if (GUIDES[page]) {
    // VitePress takes the front matter off before parsing (env.frontmatter); a mirror keeps it.
    const title = env.frontmatter?.title ?? /^title:\s*(.+)$/m.exec(front)?.[1]?.trim() ?? page;
    body = guidePage(body, title, GUIDES[page]);
  }
  return front + body;
}

/** Where a relative link of a source goes on the site: a page, an asset or GitHub. */
export function resolveLink(href: string, source: string): string {
  if (/^([a-z][a-z0-9+.-]*:|#|\/)/i.test(href)) return href;
  const [target, hash = ''] = href.split(/(?=#)/);
  const file = path.posix.normalize(path.posix.join(path.posix.dirname(source), target));
  const pkg = /^src\/(hotdog\w*)(?:\/README\.md|\/?)$/.exec(file);
  if (pkg && PACKAGES.includes(pkg[1])) return `/packages/${pkg[1]}${hash}`;
  if (file === 'CHANGELOG.md' || file === 'CONTRIBUTING.md') {
    return `/${file.replace('.md', '').toLowerCase()}${hash}`;
  }
  if (file.startsWith('docs/')) {
    const inDocs = file.slice('docs/'.length);
    if (inDocs === 'README.md') return `/${hash}`;
    if (inDocs.endsWith('.md') && !inDocs.startsWith('pdf/')) return `/${inDocs}${hash}`;
    if (ASSETS.includes(inDocs)) return `/${inDocs}`;
  }
  const full = path.join(ROOT, file);
  const isDir = fs.existsSync(full) && fs.statSync(full).isDirectory();
  return `${REPO}/${isDir ? 'tree' : 'blob'}/main/${file}${hash}`;
}

/** Markdown-it: read sources through transform, resolve relative links, number guides. */
export function bridge(md: MarkdownIt) {
  const parse = md.parse.bind(md);
  md.parse = (src, env) => {
    const tokens = parse(transform(src, env), env);
    const page = String(env.relativePath ?? '');
    const extra: Record<string, string> = {};
    if (GUIDES[page]) extra.pageClass = 'guide';
    if (env.hotdogSource !== `docs/${page}`) extra.source = env.hotdogSource;
    env.frontmatter = { ...env.frontmatter, ...extra };
    return tokens;
  };
  md.core.ruler.push('hotdog-links', (state) => {
    const source = state.env.hotdogSource ?? `docs/${state.env.relativePath}`;
    for (const token of state.tokens) {
      for (const child of token.children ?? []) {
        if (child.type !== 'link_open') continue;
        const href = child.attrGet('href');
        if (href) child.attrSet('href', resolveLink(href, source));
      }
    }
  });
}

/** Vite: serve the ASSETS from docs/ in dev and copy them next to the built site. */
export function assets(base: string): Plugin {
  return {
    name: 'hotdog-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const name = decodeURI((req.url ?? '').split('?')[0]).replace(base, '');
        if (!ASSETS.includes(name)) return next();
        res.setHeader('Content-Type', name.endsWith('.pdf') ? 'application/pdf' : 'image/png');
        fs.createReadStream(path.join(DOCS, name)).pipe(res);
      });
    },
  };
}

/** Copy the ASSETS into the built site (VitePress buildEnd). */
export function copyAssets(outDir: string) {
  for (const name of ASSETS) fs.copyFileSync(path.join(DOCS, name), path.join(outDir, name));
}
