const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const settingsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'settings.js');
const indexBodyPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'index_body.html');
const source = fs.readFileSync(settingsPath, 'utf8');
const indexBody = fs.readFileSync(indexBodyPath, 'utf8');

const context = {
  console,
  window: { location: { origin: 'http://127.0.0.1:4200' } },
  location: { hash: '' },
  document: {},
  OpenFangAPI: {
    async get() { return {}; },
    async post() { return {}; },
    async del() { return {}; },
  },
  OpenFangToast: {
    success() {},
    error() {},
    confirm(_title, _body, fn) { fn(); },
  },
  Alpine: {
    store() {
      return {};
    },
  },
};

vm.createContext(context);
vm.runInContext(source, context, { filename: settingsPath });
assert.strictEqual(typeof context.settingsPage, 'function', 'settingsPage should be defined');

const page = context.settingsPage();
assert.strictEqual(
  page.providerSummaryText(),
  'OpenFang supports 41 LLM providers out of the box. Configure API keys to unlock models from each provider. Set environment variables and restart, or use the form below to save keys directly.',
  'providerSummaryText should default to the documented provider count before providers finish loading'
);

page.providers = [{ id: 'openai' }, { id: 'anthropic' }, { id: 'gemini' }];
assert.strictEqual(
  page.providerSummaryText(),
  'OpenFang supports 3 LLM providers out of the box. Configure API keys to unlock models from each provider. Set environment variables and restart, or use the form below to save keys directly.',
  'providerSummaryText should follow the live provider list once providers are loaded'
);

assert.strictEqual(
  JSON.stringify(page.configSectionFields([{ name: 'api_key' }, { name: 'log_level' }])),
  JSON.stringify([{ name: 'api_key' }, { name: 'log_level' }]),
  'configSectionFields should preserve legacy flat-array section payloads'
);
assert.strictEqual(
  JSON.stringify(page.configSectionFields({ fields: [{ name: 'provider' }, { name: 'model' }] })),
  JSON.stringify([{ name: 'provider' }, { name: 'model' }]),
  'configSectionFields should extract field arrays from section metadata objects'
);
assert.strictEqual(
  JSON.stringify(page.configSectionFields({ root_level: true })),
  JSON.stringify([]),
  'configSectionFields should fail closed for malformed section metadata'
);

assert.match(
  indexBody,
  /<p\s+x-text="providerSummaryText\(\)"><\/p>/,
  'Settings provider intro should render the shared providerSummaryText helper'
);
assert.ok(
  indexBody.includes('<template x-for="field in configSectionFields(fields)" :key="section + \'\.\' + field.name">'),
  'Settings config tab should render config rows through the shared configSectionFields compatibility helper'
);
