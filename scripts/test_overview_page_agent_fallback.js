const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const overviewPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'overview.js');
const source = fs.readFileSync(overviewPath, 'utf8');

function loadPageWithStore(storeImpl) {
  const context = {
    Alpine: {
      store: storeImpl,
    },
    OpenFangAPI: {
      async get() {
        throw new Error('not used in this test');
      },
    },
    OpenFangToast: {
      success() {},
      error() {},
    },
    localStorage: {
      getItem() {
        return null;
      },
      setItem() {},
    },
    setInterval() {
      throw new Error('not used in this test');
    },
    clearInterval() {},
    Date,
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: overviewPath });
  assert.strictEqual(typeof context.overviewPage, 'function', 'overviewPage should be defined');
  return context.overviewPage();
}

const pageWithAgents = loadPageWithStore(function(name) {
  assert.strictEqual(name, 'app');
  return {
    agents: [
      { id: 'agent-1', name: 'Alpha' },
    ],
  };
});
pageWithAgents.configuredProviders = [];
pageWithAgents.channels = [];
assert.strictEqual(pageWithAgents.setupChecklist.find(function(item) { return item.key === 'agent'; }).done, true, 'setup checklist should mark the agent step done when the shared app store has agents');
assert.strictEqual(pageWithAgents.agentName('agent-1'), 'Alpha', 'agentName should resolve known agents from the app store');
assert.strictEqual(pageWithAgents.agentName('agent-2-long-id'), 'agent-2-…', 'agentName should fall back to a shortened ID for unknown agents');
assert.strictEqual(pageWithAgents.agentName(''), '-', 'agentName should return a placeholder for empty IDs');

const pageWithoutStore = loadPageWithStore(function() {
  throw new Error('app store unavailable');
});
pageWithoutStore.configuredProviders = [];
pageWithoutStore.channels = [];
assert.strictEqual(pageWithoutStore.setupChecklist.find(function(item) { return item.key === 'agent'; }).done, false, 'setup checklist should degrade to not-done when the app store is unavailable');
assert.strictEqual(pageWithoutStore.agentName('agent-1-long-id'), 'agent-1-…', 'agentName should fall back to a shortened ID when the app store is unavailable');
