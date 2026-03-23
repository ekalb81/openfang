const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const approvalsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'approvals.js');
const source = fs.readFileSync(approvalsPath, 'utf8');

const appStore = {
  pendingApprovalCount: 99,
  lastPendingApprovalSignature: 'stale',
};

let throwOnStore = false;
const context = {
  Alpine: {
    store(name) {
      assert.strictEqual(name, 'app');
      if (throwOnStore) {
        throw new Error('store unavailable');
      }
      return appStore;
    },
  },
  OpenFangAPI: {
    async get(url) {
      assert.strictEqual(url, '/api/approvals');
      return {
        approvals: [
          { id: 'b', status: 'approved' },
          { id: 'c', status: 'pending' },
          { id: 'a', status: 'pending' },
        ],
      };
    },
  },
  OpenFangToast: {
    success() {},
    error() {},
    confirm(_title, _body, fn) { fn(); },
  },
  console,
  setInterval,
  clearInterval,
};

vm.createContext(context);
vm.runInContext(source, context, { filename: approvalsPath });
assert.strictEqual(typeof context.approvalsPage, 'function', 'approvalsPage should be defined');

(async () => {
  const page = context.approvalsPage();
  await page.loadData();

  assert.strictEqual(page.approvals.length, 3, 'loadData should populate approvals');
  assert.strictEqual(appStore.pendingApprovalCount, 2, 'pending approval badge count should sync immediately');
  assert.strictEqual(appStore.lastPendingApprovalSignature, 'a,c', 'pending approval signature should be normalized');
  assert.strictEqual(page.loading, false, 'loadData should finish loading');
  assert.strictEqual(page.loadError, '', 'loadData should clear prior load errors on success');

  throwOnStore = true;
  const pageWithoutStore = context.approvalsPage();
  await pageWithoutStore.loadData();

  assert.strictEqual(pageWithoutStore.approvals.length, 3, 'loadData should still populate approvals when the shared app store throws');
  assert.strictEqual(pageWithoutStore.loading, false, 'loadData should still finish when the shared app store is unavailable');
  assert.strictEqual(pageWithoutStore.loadError, '', 'store lookup failures should not surface as load errors');
  assert.strictEqual(appStore.pendingApprovalCount, 2, 'store lookup failures should leave the last synced badge count untouched');
})();
