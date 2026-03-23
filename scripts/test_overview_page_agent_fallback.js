const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const overviewPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'overview.js');
const source = fs.readFileSync(overviewPath, 'utf8');

function loadPageWithStore(storeImpl, localStorageImpl) {
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
    localStorage: localStorageImpl || {
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

const storageReads = {
  'of-checklist-dismissed': 'true',
  'of-first-msg': 'true',
  'of-skill-browsed': 'true',
};
const storageWrites = [];
const pageWithAgents = loadPageWithStore(function(name) {
  assert.strictEqual(name, 'app');
  return {
    agents: [
      { id: 'agent-1', name: 'Alpha' },
    ],
  };
}, {
  getItem(key) {
    return Object.prototype.hasOwnProperty.call(storageReads, key) ? storageReads[key] : null;
  },
  setItem(key, value) {
    storageWrites.push([key, value]);
  },
});
pageWithAgents.configuredProviders = [];
pageWithAgents.channels = [];
assert.strictEqual(pageWithAgents.localFlag('of-first-msg'), true, 'localFlag should read persisted true values');
assert.strictEqual(pageWithAgents.localFlag('missing-flag'), false, 'localFlag should treat missing values as false');
assert.strictEqual(pageWithAgents.setupChecklist.find(function(item) { return item.key === 'agent'; }).done, true, 'setup checklist should mark the agent step done when the shared app store has agents');
assert.strictEqual(pageWithAgents.setupChecklist.find(function(item) { return item.key === 'chat'; }).done, true, 'setup checklist should honor persisted chat progress');
assert.strictEqual(pageWithAgents.setupChecklist.find(function(item) { return item.key === 'skill'; }).done, true, 'setup checklist should honor persisted skill progress');
assert.strictEqual(pageWithAgents.agentName('agent-1'), 'Alpha', 'agentName should resolve known agents from the app store');
assert.strictEqual(pageWithAgents.agentName('agent-2-long-id'), 'agent-2-…', 'agentName should fall back to a shortened ID for unknown agents');
assert.strictEqual(pageWithAgents.agentName(''), '-', 'agentName should return a placeholder for empty IDs');

pageWithAgents.dismissChecklist();
assert.strictEqual(pageWithAgents.checklistDismissed, true, 'dismissChecklist should update the in-memory flag');
assert.deepStrictEqual(storageWrites, [['of-checklist-dismissed', 'true']], 'dismissChecklist should persist the checklist dismissal flag');

const pageWithoutStore = loadPageWithStore(function() {
  throw new Error('app store unavailable');
}, {
  getItem() {
    throw new Error('storage unavailable');
  },
  setItem() {
    throw new Error('storage unavailable');
  },
});
pageWithoutStore.configuredProviders = [];
pageWithoutStore.channels = [];
assert.strictEqual(pageWithoutStore.localFlag('of-first-msg'), false, 'localFlag should degrade to false when storage access throws');
assert.strictEqual(pageWithoutStore.setupChecklist.find(function(item) { return item.key === 'agent'; }).done, false, 'setup checklist should degrade to not-done when the shared app store is unavailable');
assert.strictEqual(pageWithoutStore.setupChecklist.find(function(item) { return item.key === 'chat'; }).done, false, 'setup checklist should degrade to not-done when storage access is denied');
assert.strictEqual(pageWithoutStore.agentName('agent-1-long-id'), 'agent-1-…', 'agentName should fall back to a shortened ID when the app store is unavailable');
pageWithoutStore.dismissChecklist();
assert.strictEqual(pageWithoutStore.checklistDismissed, true, 'dismissChecklist should still update in-memory state when storage writes fail');
