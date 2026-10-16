#!/usr/bin/env node
/**
 * E2E self-contained: sobe o preview do Vite, espera a porta, roda os YAML
 * via playwright-with-yaml, derruba o servidor e sai com o código do teste.
 * Evita servidores em background no shell (que recebem SIGTERM).
 *
 * Uso: node e2e/run-ci.js [arquivo.yaml ...]
 * Env: ORC_UI_PORT (default 5173), ORC_PWYAML_DIR, ORC_UI_BASE_URL,
 *      ORC_NO_SERVER=1 (não sobe server; usa base_url externo).
 */
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');

const PORT = process.env.ORC_UI_PORT || '5173';
const BASE = process.env.ORC_UI_BASE_URL || `http://localhost:${PORT}`;
const FW_DIR = process.env.ORC_PWYAML_DIR || path.resolve(process.env.HOME || '', 'git/playwright-with-yaml');
const { runTest, loadTestCases, loadConfig } = require(path.join(FW_DIR, 'src', 'executor.js'));

const e2eDir = __dirname;
const config = loadConfig(path.join(e2eDir, 'config.yaml'));
config.base_url = BASE;

const args = process.argv.slice(2);
const files = args.length
  ? args
  : fs.readdirSync(e2eDir).filter((f) => f.endsWith('.yaml') && f !== 'config.yaml').sort();

function waitForPort(url, tries = 60) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      http.get(url, (res) => { res.resume(); resolve(); }).on('error', () => {
        if (n <= 0) return reject(new Error(`servidor não subiu em ${url}`));
        setTimeout(() => attempt(n - 1), 500);
      });
    };
    attempt(tries);
  });
}

(async () => {
  let server = null;
  if (process.env.ORC_NO_SERVER !== '1') {
    server = spawn('npm', ['run', 'preview', '--', '--port', String(PORT), '--strictPort'], {
      cwd: path.resolve(e2eDir, '..'), stdio: 'ignore', detached: false,
    });
  }
  let failed = 0;
  try {
    await waitForPort(`${BASE}/login`);
    for (const file of files) {
      const full = path.isAbsolute(file) ? file : path.join(e2eDir, file);
      const tc = loadTestCases(full);
      process.stdout.write(`\n▶ ${tc.test_name || file}\n`);
      try { await runTest(tc, config); console.log(`✅ ${file}`); }
      catch (err) { console.error(`❌ ${file}: ${err.message}`); failed++; }
    }
  } catch (e) {
    console.error(`setup falhou: ${e.message}`); failed++;
  } finally {
    if (server) { try { server.kill('SIGTERM'); } catch {} }
  }
  console.log(`\n${failed === 0 ? 'ALL PASSED' : failed + ' FAILED'} (${files.length} file(s))`);
  process.exit(failed === 0 ? 0 : 1);
})();
