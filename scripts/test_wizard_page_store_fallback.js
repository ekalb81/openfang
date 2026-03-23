const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const wizardPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'wizard.js');
const source = fs.readFileSync(wizardPath, 'utf8');

function createLocation() {
  let hash = '';
  return {
    get hash() { return hash; },
    set hash(value) { hash = value; },
  };
}

function buildPage(storeImpl, apiPost, toastSink, options = {}) {
  const location = createLocation();
  const localStorageData = {};
  const storageThrows = !!options.storageThrows;
  const context = {
    Alpine: { store: storeImpl },
    OpenFangAPI: { post: apiPost },
    OpenFangToast: {
      success(message) { toastSink.success.push(message); },
      error(message) { toastSink.error.push(message); },
    },
    localStorage: {
      setItem(key, value) {
        if (storageThrows) throw new Error('storage denied');
        localStorageData[key] = String(value);
      },
      getItem(key) {
        if (storageThrows) throw new Error('storage denied');
        return Object.prototype.hasOwnProperty.call(localStorageData, key) ? localStorageData[key] : null;
      },
    },
    window: { location },
    location,
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: wizardPath });
  assert.strictEqual(typeof context.wizardPage, 'function', 'wizardPage should be defined');
  return {
    page: context.wizardPage(),
    location,
    localStorageData,
  };
}

(async () => {
  let healthyStore;
  const healthyToasts = { success: [], error: [] };
  const healthy = buildPage(
    function(name) {
      assert.strictEqual(name, 'app');
      healthyStore = healthyStore || {
        refreshCount: 0,
        refreshAgents() {
          this.refreshCount += 1;
          return Promise.resolve();
        },
        showOnboarding: true,
        pendingAgent: null,
      };
      return healthyStore;
    },
    async function(url) {
      assert.strictEqual(url, '/api/agents');
      return { agent_id: 'agent-123', name: 'Wizard Agent' };
    },
    healthyToasts,
  );

  await healthy.page.createAgent();
  assert.strictEqual(healthy.page.createdAgent.id, 'agent-123', 'createAgent should record the new agent id');
  assert.strictEqual(healthyStore.refreshCount, 1, 'createAgent should refresh shared agents when the app store is healthy');
  assert.deepStrictEqual(healthyToasts.error, [], 'healthy createAgent should not emit error toasts');

  healthy.page.finish();
  assert.strictEqual(healthy.localStorageData['openfang-onboarded'], 'true', 'finish should persist onboarding completion');
  assert.strictEqual(healthyStore.showOnboarding, false, 'finish should hide onboarding when the app store is healthy');
  assert.strictEqual(healthyStore.pendingAgent.id, 'agent-123', 'finish should queue the created agent for chat handoff');
  assert.strictEqual(healthy.location.hash, 'agents', 'finish should navigate to agents after creating an agent');

  const unavailableToasts = { success: [], error: [] };
  const unavailable = buildPage(
    function() {
      throw new Error('app store unavailable');
    },
    async function() {
      return { agent_id: 'agent-999', name: 'Recovered Wizard Agent' };
    },
    unavailableToasts,
  );

  await unavailable.page.createAgent();
  assert.strictEqual(unavailable.page.createdAgent.id, 'agent-999', 'createAgent should still succeed when the app store is unavailable');
  assert.deepStrictEqual(unavailableToasts.error, [], 'store-unavailable createAgent should not emit a false failure toast after success');
  assert.strictEqual(unavailableToasts.success.length, 1, 'store-unavailable createAgent should still emit the success toast');

  unavailable.page.finish();
  assert.strictEqual(unavailable.localStorageData['openfang-onboarded'], 'true', 'finish should still persist onboarding completion without the app store');
  assert.strictEqual(unavailable.location.hash, 'agents', 'finish should still navigate to agents without the app store');

  unavailable.page.createdAgent = null;
  unavailable.page.finishAndDismiss();
  assert.strictEqual(unavailable.location.hash, 'overview', 'finishAndDismiss should still navigate to overview without the app store');

  const storageDeniedToasts = { success: [], error: [] };
  const storageDenied = buildPage(
    function() {
      throw new Error('app store unavailable');
    },
    async function(url, payload) {
      if (url === '/api/agents/agent-storage/message') {
        assert.ok(payload && typeof payload === 'object', 'sendTryItMessage should send an object payload');
        assert.strictEqual(payload.message, 'Hello wizard', 'sendTryItMessage should post the user message payload');
        return { response: 'Still works' };
      }
      throw new Error('unexpected API call: ' + url);
    },
    storageDeniedToasts,
    { storageThrows: true },
  );

  storageDenied.page.createdAgent = { id: 'agent-storage', name: 'Storage Denied Agent' };
  await storageDenied.page.sendTryItMessage('Hello wizard');
  assert.strictEqual(storageDenied.page.tryItMessages.length, 2, 'sendTryItMessage should still append user and agent messages when storage is denied');
  assert.strictEqual(storageDenied.page.tryItMessages[1].text, 'Still works', 'sendTryItMessage should keep the API response when storage is denied');
  assert.strictEqual(storageDenied.page.tryItSending, false, 'sendTryItMessage should clear the sending flag after a storage-denied success');
  assert.deepStrictEqual(storageDeniedToasts.error, [], 'storage-denied sendTryItMessage should not emit a false error toast after success');
  assert.deepStrictEqual(storageDenied.localStorageData, {}, 'storage-denied flows should degrade without persisting browser flags');

  storageDenied.page.finish();
  assert.strictEqual(storageDenied.location.hash, 'agents', 'finish should still navigate to agents when storage is denied');

  storageDenied.page.createdAgent = null;
  storageDenied.page.finishAndDismiss();
  assert.strictEqual(storageDenied.location.hash, 'overview', 'finishAndDismiss should still navigate to overview when storage is denied');
})();
