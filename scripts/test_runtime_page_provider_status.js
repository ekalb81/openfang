const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const runtimePath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'runtime.js');
const indexBodyPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'index_body.html');
const source = fs.readFileSync(runtimePath, 'utf8');
const indexBody = fs.readFileSync(indexBodyPath, 'utf8');

let runtimeFactory = null;
const documentStub = {
  addEventListener(event, callback) {
    if (event === 'alpine:init') callback();
  },
};

const context = {
  console,
  document: documentStub,
  Alpine: {
    data(name, factory) {
      if (name === 'runtimePage') runtimeFactory = factory;
    },
  },
  OpenFangAPI: {
    async get(url) {
      if (url === '/api/status') {
        return {
          uptime_seconds: 65,
          default_model: 'gpt-test',
          api_listen: '127.0.0.1:3000',
          home_dir: '/tmp/openfang',
          log_level: 'info',
          network_enabled: false,
        };
      }
      if (url === '/api/version') {
        return { version: '0.0.0-test', platform: 'linux', arch: 'x64' };
      }
      if (url === '/api/providers') {
        return {
          providers: [
            { id: 'openai', display_name: 'OpenAI', auth_status: 'configured', reachable: false, is_local: false, model_count: 12 },
            { id: 'ollama', display_name: 'Ollama', auth_status: 'missing', reachable: false, is_local: true, model_count: 3 },
            { id: 'anthropic', display_name: 'Anthropic', auth_status: 'missing', reachable: false, is_local: false, model_count: 5 },
          ],
        };
      }
      if (url === '/api/agents') {
        return [];
      }
      throw new Error('Unexpected URL: ' + url);
    },
  },
};

vm.createContext(context);
vm.runInContext(source, context, { filename: runtimePath });
assert.strictEqual(typeof runtimeFactory, 'function', 'runtimePage should register through Alpine.data');

(async () => {
  const page = runtimeFactory();
  await page.loadData();

  assert.deepStrictEqual(
    page.providers.map((provider) => provider.id),
    ['openai', 'ollama'],
    'Runtime page should keep lowercase configured providers and local providers while excluding unconfigured remote ones'
  );

  assert.match(
    indexBody,
    /p\.auth_status === 'configured' \? 'badge-success' : 'badge-dim'/,
    'Runtime providers badge should treat lowercase configured auth status as ready'
  );

  assert.match(
    indexBody,
    /p\.auth_status === 'configured' \? 'Ready' : 'Not configured'/,
    'Runtime providers label should treat lowercase configured auth status as ready'
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
