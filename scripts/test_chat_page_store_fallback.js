const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const chatPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'chat.js');
const source = fs.readFileSync(chatPath, 'utf8');

function loadPageWithStore(storeImpl, options) {
  options = options || {};
  const documentEvents = [];
  const wsConnections = [];
  const apiDeletes = [];
  const successMessages = [];
  const confirmPromises = [];

  const context = {
    Alpine: {
      store: storeImpl,
    },
    OpenFangAPI: {
      get() {
        return Promise.resolve({ commands: [] });
      },
      post() {
        return Promise.resolve({});
      },
      put() {
        return Promise.resolve({});
      },
      del(url) {
        apiDeletes.push(url);
        return Promise.resolve({});
      },
      upload() {
        return Promise.resolve({});
      },
      wsConnect(agentId, handlers) {
        wsConnections.push({ agentId, handlers });
      },
      wsDisconnect() {},
      wsSend() { return false; },
      isWsConnected() { return false; },
    },
    OpenFangToast: {
      confirm(_title, _body, fn) {
        const result = fn();
        if (result && typeof result.then === 'function') {
          confirmPromises.push(result);
        }
      },
      success(message) { successMessages.push(message); },
      error() {},
      info() {},
      warn() {},
    },
    renderLatex() {},
    renderMarkdown(text) { return text; },
    escapeHtml(text) { return text; },
    window: {
      dispatchEvent() {},
    },
    Event: function Event(type) { this.type = type; },
    document: {
      addEventListener(type) { documentEvents.push(['add', type]); },
      removeEventListener(type) { documentEvents.push(['remove', type]); },
      getElementById() { return null; },
    },
    localStorage: {
      _data: Object.create(null),
      getItem(key) {
        if (options.storageThrows) {
          throw new Error('storage unavailable');
        }
        return Object.prototype.hasOwnProperty.call(this._data, key) ? this._data[key] : null;
      },
      setItem(key, value) {
        if (options.storageThrows) {
          throw new Error('storage unavailable');
        }
        this._data[key] = String(value);
      },
    },
    location: { hash: '' },
    navigator: { clipboard: { writeText() { return Promise.resolve(); } } },
    setInterval() { return 1; },
    clearInterval() {},
    setTimeout(fn) { return fn, 1; },
    clearTimeout() {},
    URL: { createObjectURL() { return 'blob:test'; }, revokeObjectURL() {} },
    prompt() { return null; },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: chatPath });
  assert.strictEqual(typeof context.chatPage, 'function', 'chatPage should be defined');
  const page = context.chatPage();
  page.$nextTick = function(fn) { if (fn) fn(); };

  return { page, wsConnections, apiDeletes, successMessages, documentEvents, confirmPromises };
}

(async () => {
  const pendingAgent = { id: 'agent-1', name: 'Alpha' };
  let refreshCount = 0;
  const healthyStore = {
    pendingAgent,
    wsConnected: false,
    agents: [],
    agentCount: 0,
    refreshAgents() {
      refreshCount += 1;
    },
  };

  const healthy = loadPageWithStore(function(name) {
    assert.strictEqual(name, 'app');
    return healthyStore;
  });
  let healthyWatched = [];
  let selectedAgent = null;
  healthy.page.$watch = function(path, handler) {
    healthyWatched.push({ path, handler });
  };
  healthy.page.selectAgent = function(agent) {
    selectedAgent = agent;
  };

  healthy.page.init();
  assert.strictEqual(selectedAgent, pendingAgent, 'init should restore pendingAgent when the app store is healthy');
  assert.strictEqual(healthyStore.pendingAgent, null, 'init should clear restored pendingAgent from the app store');
  assert.deepStrictEqual(
    healthyWatched.map(function(entry) { return entry.path; }),
    ['currentAgent', '$store.app.pendingAgent', 'inputText'],
    'init should keep currentAgent, pendingAgent, and inputText watchers when the store is healthy'
  );

  const futurePendingAgent = { id: 'agent-2', name: 'Beta' };
  healthyStore.pendingAgent = futurePendingAgent;
  healthyWatched[1].handler(futurePendingAgent);
  assert.strictEqual(selectedAgent, futurePendingAgent, 'pendingAgent watcher should keep chat selection in sync');
  assert.strictEqual(healthyStore.pendingAgent, null, 'pendingAgent watcher should clear the app-store handoff after selecting');

  healthy.page.connectWs('agent-2');
  assert.strictEqual(healthy.wsConnections.length, 1, 'connectWs should attach one websocket session');
  healthy.wsConnections[0].handlers.onOpen();
  assert.strictEqual(healthyStore.wsConnected, true, 'websocket open should set wsConnected when the store is available');
  healthy.wsConnections[0].handlers.onClose();
  assert.strictEqual(healthyStore.wsConnected, false, 'websocket close should clear wsConnected when the store is available');

  healthy.page.handleWsMessage({ type: 'agents_updated', agents: [{ id: 'agent-9' }, { id: 'agent-10' }] });
  assert.strictEqual(healthyStore.agents.length, 2, 'agents_updated should keep the shared app store agent list in sync');
  assert.strictEqual(healthyStore.agentCount, 2, 'agents_updated should keep the shared app store agent count in sync');

  healthy.page.currentAgent = { id: 'agent-2', name: 'Beta' };
  healthy.page.killAgent();
  await Promise.all(healthy.confirmPromises);
  assert.strictEqual(refreshCount, 1, 'killAgent should refresh the shared store when available');
  assert.strictEqual(healthy.page.currentAgent, null, 'killAgent should clear the current agent after a successful stop');
  assert.deepStrictEqual(healthy.apiDeletes, ['/api/agents/agent-2'], 'killAgent should call the delete endpoint for the active agent');
  assert.strictEqual(healthy.successMessages.length, 1, 'killAgent should still report success when the store is healthy');

  const unavailable = loadPageWithStore(function() {
    throw new Error('app store unavailable');
  });
  let unavailableWatched = [];
  let unavailableSelected = null;
  unavailable.page.$watch = function(path, handler) {
    unavailableWatched.push({ path, handler });
  };
  unavailable.page.selectAgent = function(agent) {
    unavailableSelected = agent;
  };

  unavailable.page.init();
  assert.strictEqual(unavailableSelected, null, 'init should skip pendingAgent restore when the app store is unavailable');
  assert.deepStrictEqual(
    unavailableWatched.map(function(entry) { return entry.path; }),
    ['currentAgent', 'inputText'],
    'init should skip the $store.app.pendingAgent watcher when the app store is unavailable'
  );

  unavailable.page.connectWs('agent-3');
  assert.strictEqual(unavailable.wsConnections.length, 1, 'connectWs should still connect without the app store');
  unavailable.wsConnections[0].handlers.onOpen();
  unavailable.wsConnections[0].handlers.onError();
  assert.strictEqual(unavailable.page._wsAgent, null, 'websocket lifecycle handlers should still reset local state without the app store');

  unavailable.page.handleWsMessage({ type: 'agents_updated', agents: [{ id: 'agent-11' }] });
  assert.strictEqual(unavailable.page.messages.length, 0, 'agents_updated should be ignored cleanly when the app store is unavailable');

  unavailable.page.currentAgent = { id: 'agent-3', name: 'Gamma' };
  unavailable.page.killAgent();
  await Promise.all(unavailable.confirmPromises);
  assert.strictEqual(unavailable.page.currentAgent, null, 'killAgent should still clear the current agent when the store is unavailable');
  assert.deepStrictEqual(unavailable.apiDeletes, ['/api/agents/agent-3'], 'killAgent should still stop the agent when the store is unavailable');
  assert.strictEqual(unavailable.successMessages.length, 1, 'killAgent should still report success when the store is unavailable');

  const storageDenied = loadPageWithStore(function() {
    throw new Error('app store unavailable');
  }, { storageThrows: true });
  storageDenied.page.connectWs = function() {};
  storageDenied.page.localFlag = storageDenied.page.localFlag.bind(storageDenied.page);
  storageDenied.page.setLocalFlag = storageDenied.page.setLocalFlag.bind(storageDenied.page);
  storageDenied.page.currentAgent = { id: 'agent-4', name: 'Delta' };
  storageDenied.page.localFlag('of-chat-tips-seen');
  assert.strictEqual(storageDenied.page.currentTip, 'Type / for commands', 'currentTip should fall back cleanly when localStorage reads throw');

  storageDenied.page.dismissTips();
  storageDenied.page.selectAgent(storageDenied.page.currentAgent);
  assert.strictEqual(storageDenied.page.messages.length, 1, 'selectAgent should still inject the welcome message when localStorage is unavailable');

  storageDenied.page.inputText = 'hello';
  storageDenied.page.attachments = [];
  storageDenied.page.scrollToBottom = function() {};
  await storageDenied.page.sendMessage();
  assert.ok(
    storageDenied.page.messages.some(function(message) { return message.role === 'user' && message.text === 'hello'; }),
    'sendMessage should still append the user message when localStorage writes throw'
  );
})();
