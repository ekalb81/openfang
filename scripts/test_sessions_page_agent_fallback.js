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
  const pageWithAgents = await loadPageWithStore(function(name) {
    assert.strictEqual(name, 'app');
    return {
      agents: [
        { id: 'agent-1', name: 'Alpha' },
      ],
    };
  });

  assert.strictEqual(pageWithAgents.loadError, '', 'loadSessions should succeed when the app store has agents');
  assert.strictEqual(pageWithAgents.loading, false, 'loadSessions should finish loading when agents are available');
  assert.strictEqual(pageWithAgents.sessions[0].agent_name, 'Alpha', 'loadSessions should map known agent IDs to agent names');
  assert.strictEqual(pageWithAgents.sessions[1].agent_name, '', 'loadSessions should leave unknown agent IDs unmapped');

  const pageWithoutStore = await loadPageWithStore(function() {
    throw new Error('app store unavailable');
  });

  assert.strictEqual(pageWithoutStore.loadError, '', 'loadSessions should not fail if the app store is temporarily unavailable');
  assert.strictEqual(pageWithoutStore.loading, false, 'loadSessions should finish loading even without the app store');
  assert.strictEqual(pageWithoutStore.sessions.length, 2, 'loadSessions should still populate sessions without the app store');
  assert.strictEqual(pageWithoutStore.sessions[0].agent_name, '', 'agent names should fall back to blank when the app store is unavailable');
})();
