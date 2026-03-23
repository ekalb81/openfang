const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync('crates/openfang-api/static/js/api.js', 'utf8');

function createDocumentStub() {
  return {
    body: {
      appendChild() {},
      removeChild() {}
    },
    createElement() {
      return {
        className: '',
        textContent: '',
        onclick: null,
        parentNode: null,
        classList: { contains() { return false; }, add() {} },
        setAttribute() {},
        appendChild() {},
        addEventListener() {},
        focus() {}
      };
    },
    getElementById() { return null; },
    addEventListener() {},
    removeEventListener() {}
  };
}

async function main() {
  const appStore = { showAuthPrompt: false };
  let removeCalls = 0;

  const context = {
    window: { location: { origin: 'http://localhost:8080' } },
    document: createDocumentStub(),
    console,
    setTimeout,
    clearTimeout,
    Alpine: {
      store(name) {
        assert.strictEqual(name, 'app', 'api client should request the shared app store');
        return appStore;
      }
    },
    localStorage: {
      removeItem() {
        removeCalls += 1;
        throw new Error('storage denied');
      }
    },
    fetch() {
      return Promise.resolve({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        text: () => Promise.resolve(JSON.stringify({ error: 'expired key' })),
        headers: { get: () => 'application/json' }
      });
    }
  };
  context.global = context;
  context.globalThis = context;

  vm.runInNewContext(source, context, { filename: 'api.js' });

  context.OpenFangAPI.setAuthToken('stale-token');

  await assert.rejects(
    context.OpenFangAPI.get('/api/test'),
    /Not authorized — check your API key/,
    '401 responses should still surface the friendly auth error'
  );

  assert.strictEqual(removeCalls, 1, '401 handling should still attempt to clear the stored API key');
  assert.strictEqual(context.OpenFangAPI.getToken(), '', '401 handling should clear the in-memory auth token');
  assert.strictEqual(appStore.showAuthPrompt, true, '401 handling should still show the auth prompt when storage removal throws');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
