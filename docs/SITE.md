# Site — orc-hestrator.dev

One-page institutional site. No build step: HTML + CSS + two PNG assets, served
statically by nginx.

## What's here

```
site/
├── index.html          single page (one inline <script> for the mobile menu and copy button)
├── styles.css          brand tokens (from frontend/tailwind.config.js) + layout
└── assets/
    ├── orc-logo-256.png    header mark (pngquant-optimized)
    └── orc-board.png       hero screenshot, from frontend/screenshots/ (pngquant-optimized)
deploy/nginx/orc-hestrator.dev.conf   server block for the domain
```

Content rule: the site *presents*; the README and docs *explain*. Copy only
statements that exist in the repo (README, PRD, CHANGELOG). No invented
metrics, no testimonials.

## 1. DNS

Point `orc-hestrator.dev` at the VPS IP (the same box that serves cfnarede.dev).

- **Apex (`orc-hestrator.dev`)**: use an **A record** → VPS IP. A CNAME at the
  apex is not universally supported — some providers allow it, others do not
  (it is not allowed at the zone root per RFC 1034, though several registrars
  flatten it). If your provider has an alias facility (Route 53 **Alias**,
  Cloudflare **CNAME flattening**, OVH **ALIAS**), that also works.
- **`www.orc-hestrator.dev`**: a normal **CNAME** → `orc-hestrator.dev` is fine.

## 2. First deploy

On the VPS:

```bash
sudo mkdir -p /var/www/orc-hestrator
# copy site/ to /var/www/orc-hestrator/ (see "Updating" below), then:
sudo chown -R www-data:www-data /var/www/orc-hestrator
sudo find /var/www/orc-hestrator -type d -exec chmod 755 {} \;
sudo find /var/www/orc-hestrator -type f -exec chmod 644 {} \;
```

nginx runs its worker as `www-data`; 755/644 under it is sufficient. The site
files themselves are owned by your deploy user in most setups — `chown` above
is only needed if you copy as a non-www-data user and nginx still can't read
the files (it can read 644 root-owned files too; the ownership change is
optional, the permissions are not).

Install the server block:

```bash
sudo cp deploy/nginx/orc-hestrator.dev.conf /etc/nginx/sites-available/orc-hestrator.dev.conf
sudo ln -s /etc/nginx/sites-available/orc-hestrator.dev.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Note: this VPS also serves cfnarede.dev (and the app UI at `/orc/ui/`). That
uses different `server_name`s, so the new block doesn't collide — but make
sure no default/catch-all `server` block claims port 80 without a
`server_name` before yours is in place.

## 3. TLS (certbot)

With the :80 block live:

```bash
sudo certbot --nginx -d orc-hestrator.dev -d www.orc-hestrator.dev --redirect
```

certbot fills in the `ssl_certificate`/`ssl_certificate_key` paths in the :443
block and the 301 redirect in the :80 block (the conf already ships with the
post-certbot shape, so certbot only needs to rewrite the paths). Renewal is
automatic via the existing certbot timer on the box; verify once with
`sudo certbot certificates`.

Optional: `www` can be dropped from `-d` if you'd rather not serve it.

## 4. Deploy realizado (18/out/2026)

Publicado em `https://orc-hestrator.dev`: A record no apex para o VPS, certificado Let's Encrypt
(ECDSA, renovação pelo `certbot.timer`), HTTP 301 para HTTPS, 30 dias de cache em `/assets/`,
7 dias em `styles.css`, `index.html` com `no-cache`. Verificado de fora: 200 no HTML, no CSS e nos
assets; headers de segurança presentes nos três.

Três aprendizados do ato, válidos para a próxima publicação:

- **Não há `rsync` no VPS.** O envio foi por `tar` sobre SSH:
  `tar czf - -C site . | ssh cfnarede.dev 'rm -rf /var/www/orc-hestrator/* && tar xzf - -C /var/www/orc-hestrator'`.
- **A ordem importa.** Instalar o conf completo antes do certificado faz `nginx -t` falhar por
  `ssl_certificate` inexistente. Instale só o bloco `:80`, rode
  `certbot --nginx -d orc-hestrator.dev --redirect`, e depois copie o conf do repositório — ele já
  está no formato pós-certbot.
- **`add_header` não é herdado.** Quando um `location` declara o próprio `add_header`, os do nível
  `server` desaparecem. Daí `nosniff` e `Referrer-Policy` repetidos em `/assets/`, `styles.css` e
  `index.html`.

O site não foi anunciado: ensina `uvx orc-hestrator` e `orc`, que só existem depois da F7, e os
links apontam para o repositório com o nome antigo.

## 5. Updating the site


From a machine with an SSH key set up for the VPS (no interactive password):

```bash
rsync -avz --delete site/ claudio@<vps>:/tmp/orc-site && \
ssh claudio@<vps> 'sudo rsync -a --delete /tmp/orc-site/ /var/www/orc-hestrator/ && sudo find /var/www/orc-hestrator -type f -exec chmod 644 {} \;'
```

No nginx reload is needed for static file changes. After pushing, reload the
page with a cache-buster or wait out the 7-day CSS / 30-day asset caches
(HTML is served `no-cache`).

If you regenerate screenshots: re-copy from `frontend/screenshots/` and
re-run pngquant:

```bash
pngquant --quality 75-90 --force --output site/assets/orc-board.png frontend/screenshots/orc-board.png
pngquant --quality 70-92 --force --output site/assets/orc-logo-256.png docs/assets/orc-logo-256.png
```

## 5. Verify

```bash
curl -sI https://orc-hestrator.dev/                     # 200
curl -sI https://orc-hestrator.dev/styles.css           # 200
curl -sI https://orc-hestrator.dev/assets/orc-board.png # 200
curl -sI https://orc-hestrator.dev/assets/orc-logo-256.png  # 200
```

## Brand tokens (must stay in sync with frontend/tailwind.config.js)

- canvas `#031427`, raised `#0a2036`, border `#1c3c5a`
- text `#e6eef6`, muted `#9fb3c8`, subtle `#6f8399`
  (site-local bump of the product's `#64788f` subtle so 13px hint text
  reaches WCAG AA on the canvas; keep in sync if the product token changes)
- single accent (amber) `#ffc174`
- type: Plus Jakarta Sans (headings), Inter (body), JetBrains Mono (code/ids)
- no gradients, no glassmorphism, no decorative icons
