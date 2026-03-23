const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const agentsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'agents.js');
const source = fs.readFileSync(agentsPath, 'utf8');

function loadPageWithStore(storeImpl, apiOverrides = {}) {
  const successMessages = [];
  const errorMessages = [];
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
      async patch() {
        throw new Error('not used in this test');
      },
      async put() {
        throw new Error('not used in this test');
      },
      async del() {
        throw new Error('not used in this test');
      },
      wsDisconnect() {},
      ...apiOverrides,
    },
    OpenFangToast: {
      confirm(_title, _body, fn) { fn(); },
      success(message) { successMessages.push(message); },
      error(message) { errorMessages.push(message); },
      warn() {},
    },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: agentsPath });
  assert.strictEqual(typeof context.agentsPage, 'function', 'agentsPage should be defined');
  const page = context.agentsPage();
  return { page, successMessages, errorMessages };
}

function flushAsyncWork() {
  return new Promise(function(resolve) {
    setTimeout(resolve, 0);
  });
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
  const { page: pageWithStore } = loadPageWithStore(function(name) {
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

  const { page: pageWithoutStore } = loadPageWithStore(function() {
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

  const apiCalls = [];
  const { page: actionPage, successMessages, errorMessages } = loadPageWithStore(
    function() {
      throw new Error('app store unavailable');
    },
    {
      async del(url) {
        apiCalls.push(['del', url]);
      },
      async post(url) {
        apiCalls.push(['post', url]);
        return { agent_id: 'agent-new', name: 'Spawned Agent' };
      },
      async patch(url, body) {
        apiCalls.push(['patch', url, body]);
        return {};
      },
      async put(url, body) {
        apiCalls.push(['put', url, body]);
        return { provider: 'openai' };
      },
    }
  );

  actionPage.showDetailModal = true;
  actionPage.killAgent({ id: 'agent-stop', name: 'Stop Me' });
  await flushAsyncWork();
  assert.strictEqual(actionPage.showDetailModal, false, 'killAgent should still close the detail modal when the store is unavailable');

  actionPage.filterState = 'all';
  Object.defineProperty(actionPage, 'filteredAgents', {
    value: [
      { id: 'agent-a', name: 'Alpha' },
      { id: 'agent-b', name: 'Beta' },
    ],
    configurable: true,
  });
  actionPage.killAllAgents();
  await flushAsyncWork();

  actionPage.spawnForm.name = 'Spawned Agent';
  actionPage.spawnForm.provider = 'openai';
  actionPage.spawnForm.model = 'gpt-4.1-mini';
  actionPage.spawnForm.systemPrompt = 'hi';
  actionPage.spawnIdentity = { emoji: '', color: '#FF5C00', archetype: '' };
  actionPage.selectedPreset = '';
  actionPage.soulContent = '';
  await actionPage.spawnAgent();
  assert.strictEqual(actionPage.activeChatAgent.id, 'agent-new', 'spawnAgent should still open chat with the new agent when the store is unavailable');

  actionPage.detailAgent = { id: 'agent-model', model_name: 'gpt-4.1-mini' };
  actionPage.newModelValue = 'gpt-4.1';
  await actionPage.changeModel();
  assert.strictEqual(actionPage.detailAgent.id, 'agent-model', 'changeModel should keep the current detail agent when the store is unavailable');
  actionPage.newProviderValue = 'anthropic';
  await actionPage.changeProvider();
  assert.strictEqual(actionPage.detailAgent.id, 'agent-model', 'changeProvider should keep the current detail agent when the store is unavailable');

  assert.deepStrictEqual(errorMessages, [], 'store-unavailable follow-up refreshes should not create false error toasts after successful actions');
  assert.ok(successMessages.includes('Agent "Stop Me" stopped'), 'killAgent should still report success');
  assert.ok(successMessages.includes('2 agent(s) stopped'), 'killAllAgents should still report success');
  assert.ok(successMessages.includes('Agent "Spawned Agent" spawned'), 'spawnAgent should still report success');
  assert.ok(successMessages.includes('Model changed (provider: openai) (memory reset)'), 'changeModel should still report success');
  assert.ok(successMessages.includes('Provider changed to openai'), 'changeProvider should still report success');
  assert.deepStrictEqual(
    apiCalls.map(function(call) { return call[0] + ' ' + call[1]; }),
    [
      'del /api/agents/agent-stop',
      'del /api/agents/agent-a',
      'del /api/agents/agent-b',
      'post /api/agents',
      'patch /api/agents/agent-new/config',
      'put /api/agents/agent-model/model',
      'put /api/agents/agent-model/model',
    ],
    'actions should still complete their API work when the store is unavailable'
  );
})();
