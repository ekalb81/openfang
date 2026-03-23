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

const context = {
  Alpine: {
    store(name) {
      assert.strictEqual(name, 'app');
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
})();
