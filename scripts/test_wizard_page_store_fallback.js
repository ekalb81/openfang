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

function buildPage(storeImpl, apiPost, toastSink) {
  const location = createLocation();
  const localStorageData = {};
  const context = {
    Alpine: { store: storeImpl },
    OpenFangAPI: { post: apiPost },
    OpenFangToast: {
      success(message) { toastSink.success.push(message); },
      error(message) { toastSink.error.push(message); },
    },
    localStorage: {
      setItem(key, value) { localStorageData[key] = String(value); },
      getItem(key) { return Object.prototype.hasOwnProperty.call(localStorageData, key) ? localStorageData[key] : null; },
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
})();
