const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const schedulerPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'pages', 'scheduler.js');
const source = fs.readFileSync(schedulerPath, 'utf8');

function loadPageWithStore(storeImpl) {
  const context = {
    Alpine: {
      store: storeImpl,
    },
    OpenFangAPI: {
      async get() {
        throw new Error('not used in this test');
      },
      async post() {
        throw new Error('not used in this test');
      },
      async put() {
        throw new Error('not used in this test');
      },
      async del() {
        throw new Error('not used in this test');
      },
    },
    OpenFangToast: {
      success() {},
      error() {},
      warn() {},
      confirm(_title, _body, fn) { fn(); },
    },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: schedulerPath });
  assert.strictEqual(typeof context.schedulerPage, 'function', 'schedulerPage should be defined');
  return context.schedulerPage();
}

(() => {
  const pageWithAgents = loadPageWithStore(function(name) {
    assert.strictEqual(name, 'app');
    return {
      agents: [
        { id: 'agent-1', name: 'Alpha' },
      ],
    };
  });

  assert.strictEqual(pageWithAgents.availableAgents.length, 1, 'availableAgents should expose store agents when the app store is healthy');
  assert.strictEqual(pageWithAgents.agentName('agent-1'), 'Alpha', 'agentName should resolve known agent names from the app store');
  assert.strictEqual(pageWithAgents.agentName('agent-2'), 'agent-2', 'agentName should preserve short unknown agent IDs');

  const pageWithoutStore = loadPageWithStore(function() {
    throw new Error('app store unavailable');
  });

  assert.strictEqual(Array.isArray(pageWithoutStore.availableAgents), true, 'availableAgents should still return an array when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.availableAgents.length, 0, 'availableAgents should fall back to an empty array when the app store is unavailable');
  assert.strictEqual(pageWithoutStore.agentName('1234567890abcdef'), '12345678...', 'agentName should preserve the existing shortened-ID fallback when shared agent metadata is unavailable');
  assert.strictEqual(pageWithoutStore.agentName('agent-2'), 'agent-2', 'agentName should keep short raw IDs when the app store is unavailable');
})();

(async () => {
  const context = {
    Alpine: {
      store() {
        return { agents: [] };
      },
    },
    OpenFangAPI: {
      async get(url) {
        assert.strictEqual(url, '/api/cron/jobs');
        return {
          jobs: [
            {
              id: 'job-turn',
              name: 'Turn job',
              agent_id: 'agent-1',
              enabled: true,
              schedule: { kind: 'cron', expr: '0 9 * * *' },
              action: { kind: 'agent_turn', message: 'Say hello' },
              delivery: { kind: 'last_channel' },
              created_at: '2026-03-23T07:00:00Z',
            },
            {
              id: 'job-event',
              name: 'Event job',
              agent_id: 'agent-1',
              enabled: true,
              schedule: { kind: 'every', every_secs: 300 },
              action: { kind: 'system_event', text: 'Reminder fired' },
              delivery: { kind: 'none' },
              created_at: '2026-03-23T07:00:00Z',
            },
            {
              id: 'job-workflow',
              name: 'Workflow job',
              agent_id: 'agent-1',
              enabled: false,
              schedule: { kind: 'at', at: '2026-03-24T07:00:00Z' },
              action: { kind: 'workflow_run', workflow_id: 'daily-review', input: 'summarize blockers' },
              delivery: { kind: 'webhook' },
              created_at: '2026-03-23T07:00:00Z',
            },
          ],
        };
      },
      async post() {
        throw new Error('not used in this test');
      },
      async put() {
        throw new Error('not used in this test');
      },
      async del() {
        throw new Error('not used in this test');
      },
    },
    OpenFangToast: {
      success() {},
      error() {},
      warn() {},
      confirm(_title, _body, fn) { fn(); },
    },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: schedulerPath });
  const page = context.schedulerPage();

  await page.loadJobs();

  assert.strictEqual(page.jobs.length, 3, 'loadJobs should normalize all returned cron jobs');
  assert.strictEqual(page.jobs[0].message, 'Say hello', 'agent-turn jobs should keep their message text');
  assert.strictEqual(page.jobs[1].message, 'Reminder fired', 'system-event jobs should surface their event text in the dashboard');
  assert.strictEqual(page.jobs[2].message, 'Workflow daily-review: summarize blockers', 'workflow jobs should surface a readable workflow summary in the dashboard');
  assert.strictEqual(page.jobs[1].cron, 'every 300s', 'interval schedules should still normalize cron labels');
  assert.strictEqual(page.jobs[2].cron, 'at 2026-03-24T07:00:00Z', 'one-shot schedules should still normalize cron labels');
})();

(async () => {
  let postCalled = false;
  let errorMessage = '';
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
      async post() {
        postCalled = true;
        throw new Error('run-now should not call the legacy schedules endpoint');
      },
      async put() {
        throw new Error('not used in this test');
      },
      async del() {
        throw new Error('not used in this test');
      },
    },
    OpenFangToast: {
      success() {},
      error(message) {
        errorMessage = message;
      },
      warn() {},
      confirm(_title, _body, fn) { fn(); },
    },
    console,
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: schedulerPath });
  const page = context.schedulerPage();

  await page.runNow({ id: 'job-1', name: 'Nightly review' });

  assert.strictEqual(postCalled, false, 'runNow should not call the legacy schedules run endpoint for cron-backed jobs');
  assert.strictEqual(errorMessage, 'Run Now is not yet available for cron jobs', 'runNow should report the cron-job limitation directly');
  assert.strictEqual(page.runningJobId, '', 'runNow should clear the in-progress marker after surfacing the limitation');
})();
