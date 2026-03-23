const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const schedulerPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'scheduler.js');
const source = fs.readFileSync(schedulerPath, 'utf8');

function loadPageWithStore(storeImpl) {
  const context = {
    Alpine: {
      store: storeImpl,
    },
    OpenFangAPI: {
      async get() {
        throw new Error('not used in this test');
      },
      async post() {
        throw new Error('not used in this test');
      },
      async put() {
        throw new Error('not used in this test');
      },
      async del() {
        throw new Error('not used in this test');
      },
    },
    OpenFangToast: {
      success() {},
      error() {},
      warn() {},
      confirm(_title, _body, fn) { fn(); },
    },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: schedulerPath });
  assert.strictEqual(typeof context.schedulerPage, 'function', 'schedulerPage should be defined');
  return context.schedulerPage();
}

(() => {
  const pageWithAgents = loadPageWithStore(function(name) {
    assert.strictEqual(name, 'app');
    return {
      agents: [
        { id: 'agent-1', name: 'Alpha' },
      ],
    };
  });

  assert.strictEqual(pageWithAgents.availableAgents.length, 1, 'availableAgents should expose store agents when the app store is healthy');
  assert.strictEqual(pageWithAgents.agentName('agent-1'), 'Alpha', 'agentName should resolve known agent names from the app store');
  assert.strictEqual(pageWithAgents.agentName('agent-2'), 'agent-2', 'agentName should preserve short unknown agent IDs');

  const pageWithoutStore = loadPageWithStore(function() {
    throw new Error('app store unavailable');
  });

  assert.strictEqual(Array.isArray(pageWithoutStore.availableAgents), true, 'availableAgents should still return an array when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.availableAgents.length, 0, 'availableAgents should fall back to an empty array when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.agentName('1234567890abcdef'), '12345678...', 'agentName should preserve the existing shortened-ID fallback when shared agent metadata is unavailable');
  assert.strictEqual(pageWithoutStore.agentName('agent-2'), 'agent-2', 'agentName should keep short raw IDs when the app store is unavailable');
})();
