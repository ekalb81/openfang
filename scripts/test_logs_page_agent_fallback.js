const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const logsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'logs.js');
const source = fs.readFileSync(logsPath, 'utf8');

function loadPageWithStore(storeImpl) {
  const context = {
    Alpine: {
      store: storeImpl,
    },
    OpenFangAPI: {
      async get() {
        throw new Error('not used in this test');
      },
      getToken() {
        return '';
      },
    },
    OpenFangToast: {
      success() {},
      error() {},
    },
    EventSource: function() {
      throw new Error('not used in this test');
    },
    document: {
      getElementById() { return null; },
      createElement() {
        return {
          click() {},
        };
      },
    },
    Blob: function(parts, opts) {
      this.parts = parts;
      this.opts = opts;
    },
    URL: {
      createObjectURL() { return 'blob:test'; },
      revokeObjectURL() {},
    },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: logsPath });
  assert.strictEqual(typeof context.logsPage, 'function', 'logsPage should be defined');
  return context.logsPage();
}

const pageWithAgents = loadPageWithStore(function(name) {
  assert.strictEqual(name, 'app');
  return {
    agents: [
      { id: 'agent-1', name: 'Alpha' },
    ],
  };
});
assert.strictEqual(pageWithAgents.auditAgentName('agent-1'), 'Alpha', 'auditAgentName should resolve known agent names from the app store');
assert.strictEqual(pageWithAgents.auditAgentName('agent-2-long-id'), 'agent-2-...', 'auditAgentName should fall back to a shortened ID when the agent is unknown');
assert.strictEqual(pageWithAgents.auditAgentName(''), '-', 'auditAgentName should use a placeholder for empty agent IDs');

const pageWithoutStore = loadPageWithStore(function() {
  throw new Error('app store unavailable');
});
assert.strictEqual(pageWithoutStore.auditAgentName('agent-1-long-id'), 'agent-1-...', 'auditAgentName should degrade to a shortened ID when the app store is unavailable');
