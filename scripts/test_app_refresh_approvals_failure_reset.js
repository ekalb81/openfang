const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const appPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'app.js');
const source = fs.readFileSync(appPath, 'utf8');

let alpineInit = null;
const stores = Object.create(null);
let apiResponse = {
  approvals: [
    { id: 'b', status: 'approved' },
    { id: 'c', status: 'pending' },
    { id: 'a', status: 'pending' },
  ],
};
const warnings = [];

const context = {
  document: {
    createElement() {
      return {
        textContent: '',
        innerHTML: '',
      };
    },
    addEventListener(event, handler) {
      if (event === 'alpine:init') {
        alpineInit = handler;
      }
    },
  },
  navigator: {
    clipboard: {
      writeText() {
        return Promise.resolve();
      },
    },
  },
  localStorage: {
    getItem() { return null; },
    setItem() {},
    removeItem() {},
  },
  window: {
    location: { hash: '' },
    addEventListener() {},
    removeEventListener() {},
  },
  OpenFangAPI: {
    setAuthToken() {},
    async get(url) {
      assert.strictEqual(url, '/api/approvals');
      if (apiResponse instanceof Error) {
        throw apiResponse;
      }
      return apiResponse;
    },
  },
  OpenFangToast: {
    warn(message) {
      warnings.push(message);
    },
  },
  Alpine: {
    store(name, value) {
      if (arguments.length === 2) {
        stores[name] = value;
        return value;
      }
      return stores[name];
    },
  },
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
};

vm.createContext(context);
vm.runInContext(source, context, { filename: appPath });
assert.strictEqual(typeof alpineInit, 'function', 'app bootstrap should register an alpine:init handler');
alpineInit();

const appStore = stores.app;
assert.ok(appStore, 'alpine:init should register the app store');

(async () => {
  await appStore.refreshApprovals();

  assert.strictEqual(appStore.pendingApprovalCount, 2, 'refreshApprovals should sync the pending approval count');
  assert.strictEqual(appStore.lastPendingApprovalSignature, 'a,c', 'refreshApprovals should normalize the pending approval signature');
  assert.deepStrictEqual(warnings, ['An agent is waiting for approval. Open Approvals to review.'], 'new pending approvals should raise one warning');

  apiResponse = new Error('approvals fetch failed');
  await appStore.refreshApprovals();

  assert.strictEqual(appStore.pendingApprovalCount, 0, 'fetch failures should clear stale pending approval counts');
  assert.strictEqual(appStore.lastPendingApprovalSignature, '', 'fetch failures should clear stale pending approval signatures');
  assert.deepStrictEqual(warnings, ['An agent is waiting for approval. Open Approvals to review.'], 'fetch failures should not emit additional warning toasts');
})();
