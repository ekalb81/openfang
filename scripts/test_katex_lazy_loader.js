const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const katexPath = path.join(__dirname, '..', 'crates', 'openfang-api', 'static', 'js', 'katex.js');
const source = fs.readFileSync(katexPath, 'utf8');

function createContext() {
  const appended = [];
  const elementsById = new Map();
  const document = {
    head: {
      appendChild(node) {
        appended.push(node);
        if (node.id) elementsById.set(node.id, node);
        if (node.tagName === 'SCRIPT') {
          setImmediate(() => {
            if (node.src && node.src.includes('/katex.min.js')) {
              context.katex = {};
            }
            if (node.src && node.src.includes('/auto-render.min.js')) {
              context.renderMathInElement = function(target, options) {
                context.__renderCalls.push({ target, options });
              };
            }
            if (typeof node.onload === 'function') node.onload();
          });
        }
        return node;
      },
    },
    createElement(tagName) {
      return {
        tagName: String(tagName).toUpperCase(),
        set rel(value) { this._rel = value; },
        get rel() { return this._rel; },
        set href(value) { this._href = value; },
        get href() { return this._href; },
        set src(value) { this._src = value; },
        get src() { return this._src; },
        onload: null,
        onerror: null,
        async: false,
        id: '',
      };
    },
    getElementById(id) {
      return elementsById.get(id) || null;
    },
  };

  const context = {
    console,
    document,
    Promise,
    setTimeout,
    clearTimeout,
    setImmediate,
    __appended: appended,
    __renderCalls: [],
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: katexPath });
  return context;
}

(async () => {
  const plainContext = createContext();
  assert.strictEqual(plainContext.hasLatexDelimiters('plain text only'), false, 'plain text should not trigger LaTeX loading');
  assert.strictEqual(plainContext.hasLatexDelimiters('Inline math $x^2$ appears here'), true, 'inline math should be detected');
  assert.strictEqual(plainContext.hasLatexDelimiters('Display math \\[x+y\\] appears here'), true, 'display math should be detected');

  const plainTarget = { textContent: 'nothing to render' };
  plainContext.renderLatex(plainTarget);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepStrictEqual(plainContext.__appended, [], 'renderLatex should not inject CSS or scripts when no LaTeX delimiters are present');
  assert.strictEqual(plainContext.__renderCalls.length, 0, 'renderLatex should not attempt KaTeX rendering without delimiters');

  const latexContext = createContext();
  const latexTarget = { textContent: 'Equation: $x^2 + y^2$' };
  const firstLoad = latexContext.ensureKatexLoaded();
  const secondLoad = latexContext.ensureKatexLoaded();
  assert.strictEqual(firstLoad, secondLoad, 'ensureKatexLoaded should reuse the in-flight loader promise');
  const initialScriptCount = latexContext.__appended.filter((node) => node.tagName === 'SCRIPT').length;
  assert.strictEqual(initialScriptCount, 1, 'ensureKatexLoaded should append only the KaTeX script before the first one resolves');

  const loaded = await firstLoad;
  assert.strictEqual(loaded, true, 'ensureKatexLoaded should resolve true once auto-render is available');
  const cssNodes = latexContext.__appended.filter((node) => node.tagName === 'LINK');
  const scriptNodes = latexContext.__appended.filter((node) => node.tagName === 'SCRIPT');
  assert.strictEqual(cssNodes.length, 1, 'ensureKatexLoaded should append the stylesheet once');
  assert.strictEqual(scriptNodes.length, 2, 'ensureKatexLoaded should append KaTeX core and auto-render scripts once each');

  latexContext.renderLatex(latexTarget);
  await new Promise((resolve) => setImmediate(resolve));
  assert.strictEqual(latexContext.__renderCalls.length, 1, 'renderLatex should invoke KaTeX auto-render after the loader succeeds');
  assert.strictEqual(latexContext.__renderCalls[0].target, latexTarget, 'renderLatex should render into the provided element');
  assert.strictEqual(latexContext.__renderCalls[0].options.throwOnError, false, 'renderLatex should preserve the non-throwing render mode');

  await latexContext.ensureKatexLoaded();
  assert.strictEqual(
    latexContext.__appended.filter((node) => node.tagName === 'LINK').length,
    1,
    'ensureKatexLoaded should not append duplicate stylesheets after KaTeX is loaded'
  );
  assert.strictEqual(
    latexContext.__appended.filter((node) => node.tagName === 'SCRIPT').length,
    2,
    'ensureKatexLoaded should not append duplicate scripts after KaTeX is loaded'
  );
})();
