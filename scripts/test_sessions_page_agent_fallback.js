const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const sessionsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'sessions.js');
const source = fs.readFileSync(sessionsPath, 'utf8');

async function loadPageWithStore(storeImpl) {
  const context = {
    Alpine: {
      store: storeImpl,
    },
    OpenFangAPI: {
      async get(url) {
        assert.strictEqual(url, '/api/sessions');
        return {
          sessions: [
            { session_id: 'sess-1', agent_id: 'agent-1', message_count: 3 },
            { session_id: 'sess-2', agent_id: 'agent-2', message_count: 1 },
          ],
        };
      },
    },
    OpenFangToast: {
      success() {},
      error() {},
      confirm(_title, _body, fn) { fn(); },
    },
    location: { hash: '' },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: sessionsPath });
  assert.strictEqual(typeof context.sessionsPage, 'function', 'sessionsPage should be defined');
  const page = context.sessionsPage();
  await page.loadSessions();
  return page;
}

(async () => {
  let healthyStore;
  const pageWithAgents = await loadPageWithStore(function(name) {
    assert.strictEqual(name, 'app');
    healthyStore = {
      agents: [
        { id: 'agent-1', name: 'Alpha' },
      ],
      pendingAgent: null,
    };
    return healthyStore;
  });

  assert.strictEqual(pageWithAgents.loadError, '', 'loadSessions should succeed when the app store has agents');
  assert.strictEqual(pageWithAgents.loading, false, 'loadSessions should finish loading when agents are available');
  assert.strictEqual(pageWithAgents.sessions[0].agent_name, 'Alpha', 'loadSessions should map known agent IDs to agent names');
  assert.strictEqual(pageWithAgents.sessions[1].agent_name, '', 'loadSessions should leave unknown agent IDs unmapped');

  pageWithAgents.openInChat(pageWithAgents.sessions[0]);
  assert.strictEqual(healthyStore.pendingAgent.id, 'agent-1', 'openInChat should reuse the full known agent object when the app store is available');
  assert.strictEqual(healthyStore.pendingAgent.name, 'Alpha', 'openInChat should preserve the known agent name from the app store');

  let unavailableHash = '';
  const contextWithoutStore = {
    Alpine: {
      store() {
        throw new Error('app store unavailable');
      },
    },
    OpenFangAPI: {
      async get(url) {
        assert.strictEqual(url, '/api/sessions');
        return {
          sessions: [
            { session_id: 'sess-2', agent_id: 'agent-2', agent_name: '', message_count: 1 },
          ],
        };
      },
    },
    OpenFangToast: {
      success() {},
      error() {},
      confirm(_title, _body, fn) { fn(); },
    },
    location: {
      get hash() { return unavailableHash; },
      set hash(value) { unavailableHash = value; },
    },
    console,
  };
  vm.createContext(contextWithoutStore);
  vm.runInContext(source, contextWithoutStore, { filename: sessionsPath });
  const pageWithoutStore = contextWithoutStore.sessionsPage();
  await pageWithoutStore.loadSessions();

  assert.strictEqual(pageWithoutStore.loadError, '', 'loadSessions should not fail if the app store is temporarily unavailable');
  assert.strictEqual(pageWithoutStore.loading, false, 'loadSessions should finish loading even without the app store');
  assert.strictEqual(pageWithoutStore.sessions.length, 1, 'loadSessions should still populate sessions without the app store');
  assert.strictEqual(pageWithoutStore.sessions[0].agent_name, '', 'agent names should fall back to blank when the app store is unavailable');

  pageWithoutStore.openInChat(pageWithoutStore.sessions[0]);
  assert.strictEqual(unavailableHash, 'agents', 'openInChat should still navigate to the agents page when the app store is unavailable');

  let fallbackStore;
  const pageWithFallbackStore = await loadPageWithStore(function(name) {
    assert.strictEqual(name, 'app');
    fallbackStore = {
      agents: [],
      pendingAgent: null,
    };
    return fallbackStore;
  });
  pageWithFallbackStore.openInChat({ session_id: 'sess-9', agent_id: 'agent-9', agent_name: 'Recovered Agent' });
  assert.strictEqual(fallbackStore.pendingAgent.id, 'agent-9', 'openInChat should synthesize a pending agent when session metadata is all that is available');
  assert.strictEqual(fallbackStore.pendingAgent.name, 'Recovered Agent', 'openInChat should preserve the session-provided agent name in fallback mode');
  assert.strictEqual(fallbackStore.pendingAgent.model_provider, '?', 'openInChat fallback should mark unknown provider metadata explicitly');
})();
