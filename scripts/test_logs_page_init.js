const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const logsPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'logs.js');
const source = fs.readFileSync(logsPath, 'utf8');

function loadPage() {
  const context = {
    Alpine: {
      store() {
        return { agents: [] };
      },
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
        return { click() {} };
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

(async () => {
  const page = loadPage();
  const calls = [];
  page.loadData = async function() {
    calls.push('loadData');
  };
  page.startStreaming = function() {
    calls.push('startStreaming');
  };

  await page.init();
  assert.deepStrictEqual(calls, ['loadData', 'startStreaming'], 'init should preload logs before starting the live stream');

  const failingPage = loadPage();
  failingPage.loadData = async function() {
    throw new Error('boom');
  };
  let startedAfterFailure = false;
  failingPage.startStreaming = function() {
    startedAfterFailure = true;
  };

  try {
    await failingPage.init();
    assert.fail('init should propagate unexpected loadData failures from an overridden loadData implementation');
  } catch (error) {
    assert.strictEqual(error.message, 'boom');
    assert.strictEqual(startedAfterFailure, false, 'init should not start streaming when loadData throws before completion');
  }
})();
