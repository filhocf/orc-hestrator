#!/usr/bin/env node
/**
 * Runner E2E da UI Orc[hestrator] usando o framework playwright-with-yaml.
 *
 * Uso:
 *   node e2e/run.js [arquivo.yaml ...]   # roda os YAML indicados (padrão: todos de e2e/)
 *
 * Requer o framework em ~/git/playwright-with-yaml (ou env ORC_PWYAML_DIR).
 * base_url vem de e2e/config.yaml (sobrescrevível via ORC_UI_BASE_URL).
 *
 * Pré-condição: o Vite dev server deve estar no ar em base_url
 * (npm run dev), e o backend REST do Orc para as telas que consomem /api.
 */
const path = require('path');
const fs = require('fs');

const FW_DIR =
  process.env.ORC_PWYAML_DIR ||
  path.resolve(process.env.HOME || '', 'git/playwright-with-yaml');

const executorPath = path.join(FW_DIR, 'src', 'executor.js');
if (!fs.existsSync(executorPath)) {
  console.error(`playwright-with-yaml não encontrado em ${FW_DIR}. Defina ORC_PWYAML_DIR.`);
  process.exit(2);
}
const { runTest, loadTestCases, loadConfig } = require(executorPath);

const e2eDir = __dirname;
const config = loadConfig(path.join(e2eDir, 'config.yaml'));
if (process.env.ORC_UI_BASE_URL) config.base_url = process.env.ORC_UI_BASE_URL;

const args = process.argv.slice(2);
const files =
  args.length > 0
    ? args
    : fs
        .readdirSync(e2eDir)
        .filter((f) => f.endsWith('.yaml') && f !== 'config.yaml')
        .sort();

(async () => {
  let failed = 0;
  for (const file of files) {
    const full = path.isAbsolute(file) ? file : path.join(e2eDir, file);
    const testCase = loadTestCases(full);
    process.stdout.write(`\n▶ ${testCase.test_name || file}\n`);
    try {
      await runTest(testCase, config);
      console.log(`✅ ${file}`);
    } catch (err) {
      console.error(`❌ ${file}: ${err.message}`);
      failed++;
    }
  }
  console.log(`\n${failed === 0 ? 'ALL PASSED' : failed + ' FAILED'} (${files.length} file(s))`);
  process.exit(failed === 0 ? 0 : 1);
})();
