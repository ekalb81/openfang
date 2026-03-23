const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const agentsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'agents.js');
const source = fs.readFileSync(agentsPath, 'utf8');

function loadPageWithStore(storeImpl) {
  const context = {
    Alpine: {
      store: storeImpl,
    },
    OpenFangAPI: {
      async get() {
        throw new Error('not used in this test');
      },
      wsDisconnect() {},
    },
    OpenFangToast: {
      confirm(_title, _body, fn) { fn(); },
      success() {},
      error() {},
    },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: agentsPath });
  assert.strictEqual(typeof context.agentsPage, 'function', 'agentsPage should be defined');
  return context.agentsPage();
}

(async () => {
  let refreshCount = 0;
  const pendingAgent = { id: 'agent-1', name: 'Alpha' };
  const healthyStore = {
    agents: [
      { id: 'agent-1', name: 'Alpha', state: 'Running' },
      { id: 'agent-2', name: 'Beta', state: 'Stopped' },
    ],
    pendingAgent,
    async refreshAgents() {
      refreshCount += 1;
    },
  };
  const pageWithStore = loadPageWithStore(function(name) {
    assert.strictEqual(name, 'app');
    return healthyStore;
  });
  let watchedPath = null;
  let watchedHandler = null;
  pageWithStore.$watch = function(path, handler) {
    watchedPath = path;
    watchedHandler = handler;
  };

  await pageWithStore.init();
  assert.strictEqual(refreshCount, 1, 'init should refresh agents through the app store when available');
  assert.strictEqual(pageWithStore.loadError, '', 'init should not report a load error when the store is healthy');
  assert.strictEqual(pageWithStore.agents.length, 2, 'agents getter should expose store agents when available');
  assert.strictEqual(pageWithStore.runningCount, 1, 'runningCount should use store-backed agents');
  assert.strictEqual(pageWithStore.stoppedCount, 1, 'stoppedCount should use store-backed agents');
  assert.strictEqual(pageWithStore.activeChatAgent, pendingAgent, 'init should restore a pending chat agent from the app store');
  assert.strictEqual(watchedPath, '$store.app.pendingAgent', 'init should watch pendingAgent updates when the store is healthy');
  const nextPendingAgent = { id: 'agent-3', name: 'Gamma' };
  watchedHandler(nextPendingAgent);
  assert.strictEqual(pageWithStore.activeChatAgent, nextPendingAgent, 'pendingAgent watcher should keep chat selection in sync');
  pageWithStore.chatWithAgent(healthyStore.agents[0]);
  assert.strictEqual(healthyStore.pendingAgent, healthyStore.agents[0], 'chatWithAgent should update pendingAgent when the app store is available');

  const pageWithoutStore = loadPageWithStore(function() {
    throw new Error('app store unavailable');
  });
  let unexpectedWatch = false;
  pageWithoutStore.$watch = function() {
    unexpectedWatch = true;
  };

  await pageWithoutStore.init();
  assert.strictEqual(pageWithoutStore.loading, false, 'init should always clear loading even when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.loadError, 'Could not load agents. App store unavailable.', 'init should expose a clear load error when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.agents.length, 0, 'agents getter should degrade to an empty list when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.runningCount, 0, 'runningCount should degrade to zero when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.stoppedCount, 0, 'stoppedCount should degrade to zero when the app store is unavailable');
  assert.strictEqual(unexpectedWatch, false, 'init should skip pendingAgent watchers when the app store is unavailable');
  pageWithoutStore.chatWithAgent({ id: 'agent-9', name: 'Recovered Agent' });
  assert.strictEqual(pageWithoutStore.activeChatAgent.id, 'agent-9', 'chatWithAgent should still activate inline chat without the app store');

  await pageWithoutStore.loadData();
  assert.strictEqual(pageWithoutStore.loadError, 'Could not load agents. App store unavailable.', 'loadData should preserve a clear load error when the app store is unavailable');
})();
