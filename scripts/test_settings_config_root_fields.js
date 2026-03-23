const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const settingsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'settings.js');
const source = fs.readFileSync(settingsPath, 'utf8');

const context = {
  console,
  window: { location: { origin: 'http://localhost:3000' }, open() {} },
  confirm() { return true; },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  OpenFangAPI: {
    async get() { return {}; },
    async post() { return {}; },
    async put() { return {}; },
    async del() { return {}; },
  },
  OpenFangToast: {
    success() {},
    error() {},
    warning() {},
  },
};

vm.createContext(context);
vm.runInContext(source, context, { filename: settingsPath });
assert.strictEqual(typeof context.settingsPage, 'function', 'settingsPage should be defined');

const page = context.settingsPage();
page.configSchema = {
  general: { root_level: true, fields: [{ name: 'api_listen', type: 'string' }] },
  browser: { fields: [{ name: 'headless', type: 'boolean' }] },
};
page.configValues = {
  api_listen: '127.0.0.1:3333',
  browser: { headless: true },
};

assert.strictEqual(page.configFieldValue('general', 'api_listen'), '127.0.0.1:3333', 'root-level config fields should read from the top-level config object');
assert.strictEqual(page.configFieldValue('browser', 'headless'), true, 'nested config fields should continue reading from section objects');

page.setConfigFieldValue('general', 'api_listen', '0.0.0.0:4444');
page.setConfigFieldValue('browser', 'headless', false);
page.setConfigFieldValue('web', 'timeout_secs', 30);

assert.strictEqual(page.configValues.api_listen, '0.0.0.0:4444', 'root-level config fields should write back to the top-level config object');
assert.strictEqual(page.configValues.browser.headless, false, 'nested config fields should write back inside their section object');
assert.strictEqual(page.configValues.web.timeout_secs, 30, 'missing nested sections should still be created on write');
