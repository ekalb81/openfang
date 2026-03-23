const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const appPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'app.js');
const source = fs.readFileSync(appPath, 'utf8');

function loadApp(options) {
  options = options || {};
  const documentListeners = [];
  const intervalCalls = [];
  const apiGets = [];
  const authTokens = [];
  let storeObject = null;

  const context = {
    marked: undefined,
    hljs: undefined,
    console,
    localStorage: {
      _data: Object.assign(Object.create(null), options.initialStorage || {}),
      getItem(key) {
        if (options.storageThrows) throw new Error('storage unavailable');
        return Object.prototype.hasOwnProperty.call(this._data, key) ? this._data[key] : null;
      },
      setItem(key, value) {
        if (options.storageThrows) throw new Error('storage unavailable');
        this._data[key] = String(value);
      },
      removeItem(key) {
        if (options.storageThrows) throw new Error('storage unavailable');
        delete this._data[key];
      },
    },
    document: {
      createElement() {
        return { textContent: '', innerHTML: '' };
      },
      addEventListener(type, handler) {
        documentListeners.push({ type, handler });
      },
    },
    navigator: {
      clipboard: {
        writeText() { return Promise.resolve(); },
      },
    },
    window: {
      location: { hash: options.hash || '', origin: 'http://localhost:8080' },
      matchMedia() {
        return {
          matches: !!options.prefersDark,
          addEventListener() {},
        };
      },
      addEventListener() {},
      dispatchEvent() {},
      CustomEvent: function CustomEvent(type, init) { this.type = type; this.detail = init && init.detail; },
    },
    location: { hash: options.hash || '' },
    CustomEvent: function CustomEvent(type, init) { this.type = type; this.detail = init && init.detail; },
    setTimeout() { return 1; },
    clearTimeout() {},
    setInterval(fn, ms) {
      intervalCalls.push(ms);
      return { fn, ms };
    },
    clearInterval() {},
    Alpine: {
      store(name, value) {
        assert.strictEqual(name, 'app');
        if (arguments.length === 2) {
          storeObject = value;
          return value;
        }
        return storeObject;
      },
    },
    OpenFangAPI: {
      setAuthToken(token) {
        authTokens.push(token);
      },
      get(url) {
        apiGets.push(url);
        if (url === '/api/config') return Promise.resolve({ api_key: '' });
        if (url === '/api/auth/check') return Promise.reject(new Error('no auth route'));
        if (url === '/api/tools') return Promise.resolve({});
        if (url === '/api/status') return Promise.resolve({ version: '9.9.9', agent_count: 0 });
        if (url === '/api/agents') return Promise.resolve([]);
        if (url === '/api/approvals') return Promise.resolve([]);
        return Promise.resolve({});
      },
      post() { return Promise.resolve({ status: 'ok', username: 'demo' }); },
      onConnectionChange() {},
      isWsConnected() { return false; },
    },
    OpenFangToast: {
      warn() {},
      error() {},
    },
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: appPath });

  const alpineInit = documentListeners.find((entry) => entry.type === 'alpine:init');
  assert.ok(alpineInit, 'app.js should register an alpine:init listener');

  return {
    context,
    triggerAlpineInit() {
      alpineInit.handler();
      return storeObject;
    },
    getStore() {
      return storeObject;
    },
    authTokens,
    apiGets,
    intervalCalls,
  };
}

(async () => {
  const healthy = loadApp({
    initialStorage: {
      'openfang-api-key': 'saved-token',
      'openfang-focus': 'true',
      'openfang-theme-mode': 'dark',
      'openfang-sidebar': 'collapsed',
      'openfang-onboarded': 'true',
    },
  });
  const healthyStore = healthy.triggerAlpineInit();
  assert.strictEqual(healthy.authTokens[0], 'saved-token', 'alpine init should restore a saved API key when storage is healthy');
  assert.strictEqual(healthyStore.focusMode, true, 'focusMode should restore from persisted storage');
  healthyStore.toggleFocusMode();
  assert.strictEqual(healthy.context.localStorage._data['openfang-focus'], 'false', 'toggleFocusMode should persist the updated value');
  healthyStore.submitApiKey('  fresh-token  ');
  assert.strictEqual(healthy.context.localStorage._data['openfang-api-key'], 'fresh-token', 'submitApiKey should trim and persist the API key');
  healthyStore.clearApiKey();
  assert.ok(!Object.prototype.hasOwnProperty.call(healthy.context.localStorage._data, 'openfang-api-key'), 'clearApiKey should remove the saved API key');

  const shell = healthy.context.app();
  assert.strictEqual(shell.themeMode, 'dark', 'app shell should restore themeMode from storage');
  assert.strictEqual(shell.theme, 'dark', 'app shell should resolve theme from persisted mode');
  assert.strictEqual(shell.sidebarCollapsed, true, 'app shell should restore sidebar collapse state');
  shell.toggleSidebar();
  assert.strictEqual(healthy.context.localStorage._data['openfang-sidebar'], 'expanded', 'toggleSidebar should persist updated sidebar state');
  shell.setTheme('light');
  assert.strictEqual(healthy.context.localStorage._data['openfang-theme-mode'], 'light', 'setTheme should persist updated theme mode');

  const denied = loadApp({ storageThrows: true, prefersDark: true });
  const deniedStore = denied.triggerAlpineInit();
  assert.deepStrictEqual(denied.authTokens, [], 'storage-denied alpine init should not crash or restore a bogus API key');
  assert.strictEqual(deniedStore.focusMode, false, 'focusMode should fall back to false when storage is unavailable');
  assert.doesNotThrow(() => deniedStore.toggleFocusMode(), 'toggleFocusMode should tolerate storage write failures');
  assert.doesNotThrow(() => deniedStore.submitApiKey('token'), 'submitApiKey should tolerate storage write failures');
  assert.doesNotThrow(() => deniedStore.clearApiKey(), 'clearApiKey should tolerate storage remove failures');
  deniedStore.agentCount = 0;
  await deniedStore.checkOnboarding();
  assert.strictEqual(deniedStore.showOnboarding, true, 'checkOnboarding should still show onboarding when storage reads fail and setup is incomplete');

  const deniedShell = denied.context.app();
  assert.strictEqual(deniedShell.themeMode, 'system', 'app shell should fall back to system theme when storage is unavailable');
  assert.strictEqual(deniedShell.theme, 'dark', 'system theme fallback should still respect OS preference');
  assert.strictEqual(deniedShell.sidebarCollapsed, false, 'sidebar should default to expanded when storage is unavailable');
  assert.doesNotThrow(() => deniedShell.toggleSidebar(), 'toggleSidebar should tolerate storage write failures');
  assert.doesNotThrow(() => deniedShell.setTheme('light'), 'setTheme should tolerate storage write failures');
})();
