/* Model Playwright's function cache under CSP: initial protocol evaluation is
 * permitted, subsequent animation-frame eval is forbidden. No browser claim. */
const fs = require('node:fs');
const vm = require('node:vm');
const {expression, advance = true} = JSON.parse(fs.readFileSync(0, 'utf8'));
const table = {scrollLeft: 0}, toggle = {};
const document = {activeElement: null, querySelector: s => s === '#filter-toggle' ? toggle : table};
const context = vm.createContext({document, expression}, {codeGeneration: {strings: false, wasm: false}});
const initial = vm.runInContext(expression, context);
context.cached = typeof initial === 'function' ? initial : undefined;
const first = context.cached ? context.cached() : initial;
if (advance) { table.scrollLeft = 10; document.activeElement = toggle; }
try {
  const second = vm.runInContext('cached ? cached() : eval(expression)', context);
  process.stdout.write(JSON.stringify({first, second}));
} catch (error) {
  process.stdout.write(JSON.stringify({first, error: error.name}));
  process.exitCode = 1;
}
