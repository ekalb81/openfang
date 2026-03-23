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
let apiResponse = {
  approvals: [
    { id: 'b', status: 'approved' },
    { id: 'c', status: 'pending' },
    { id: 'a', status: 'pending' },
  ],
};
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
      return apiResponse;
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

  apiResponse = [
    { id: 'x', status: 'pending' },
    { id: 'y', status: 'rejected' },
  ];
  const arrayPage = context.approvalsPage();
  await arrayPage.loadData();

  assert.strictEqual(arrayPage.approvals.length, 2, 'loadData should also accept array-shaped approvals responses');
  assert.strictEqual(appStore.pendingApprovalCount, 1, 'array-shaped responses should still sync pending counts');
  assert.strictEqual(appStore.lastPendingApprovalSignature, 'x', 'array-shaped responses should still normalize signatures');

  apiResponse = new Error('approvals fetch failed');
  context.OpenFangAPI.get = async function(url) {
    assert.strictEqual(url, '/api/approvals');
    if (apiResponse instanceof Error) {
      throw apiResponse;
    }
    return apiResponse;
  };
  const failedPage = context.approvalsPage();
  await failedPage.loadData();

  assert.strictEqual(failedPage.approvals.length, 0, 'loadData should clear stale approvals after fetch failures');
  assert.strictEqual(appStore.pendingApprovalCount, 0, 'fetch failures should clear stale pending badge counts');
  assert.strictEqual(appStore.lastPendingApprovalSignature, '', 'fetch failures should clear stale pending signatures');
  assert.strictEqual(failedPage.loadError, 'approvals fetch failed', 'fetch failures should surface the approval load error');

  throwOnStore = true;
  apiResponse = {
    approvals: [
      { id: 'b', status: 'approved' },
      { id: 'c', status: 'pending' },
      { id: 'a', status: 'pending' },
    ],
  };
  const pageWithoutStore = context.approvalsPage();
  await pageWithoutStore.loadData();

  assert.strictEqual(pageWithoutStore.approvals.length, 3, 'loadData should still populate approvals when the shared app store throws');
  assert.strictEqual(pageWithoutStore.loading, false, 'loadData should still finish when the shared app store is unavailable');
  assert.strictEqual(pageWithoutStore.loadError, '', 'store lookup failures should not surface as load errors');
  assert.strictEqual(appStore.pendingApprovalCount, 0, 'store lookup failures should leave the last synced badge count untouched');
})();
