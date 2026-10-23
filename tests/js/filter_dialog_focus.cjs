/* Run the real enhancement with a small DOM double; browser acceptance covers native behavior. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../app/static/interface.js'), 'utf8');

function fixture() {
  let document;
  class Element {
    constructor() {
      this.attrs = {}; this.listeners = {}; this.tabIndex = 0; this.hidden = false;
      this.visibility = 'visible'; this.style = {setProperty() {}};
      this.classList = {add() {}, remove() {}, toggle() {}};
    }
    // Neither focus logic nor diagnostics may inspect user-entered values or text.
    get value() { throw new Error('Sensitive value accessed'); }
    get textContent() { throw new Error('Sensitive text accessed'); }
    get outerHTML() { throw new Error('Sensitive markup accessed'); }
    setAttribute(k, v) { this.attrs[k] = v; }
    getAttribute(k) { return this.attrs[k] ?? null; }
    addEventListener(k, fn) { this.listeners[k] = fn; }
    focus() { document.activeElement = this; }
    querySelector() { return null; }
    querySelectorAll() { return []; }
    getClientRects() { return this.rendered === false ? [] : [{}]; }
    getBoundingClientRect() { return {bottom: 80, right: 300}; }
    closest() { return this.hidden || this.inert ? this : null; }
    matches(selector) { return selector === ':disabled' ? !!this.disabled : false; }
    append() {}
    replaceWith() {}
  }
  class Dialog extends Element {
    showModal() { this.open = true; }
    close() { this.open = false; this.listeners.close(); }
    contains(e) { return this.items.includes(e); }
    matches(selector) { return selector === ':modal' && !!this.open; }
    querySelectorAll() { return this.items; }
  }
  const toggle = new Element(), close = new Element(), search = new Element(), reset = new Element();
  const panel = new Element(), form = new Element(), dialog = new Dialog();
  dialog.items = [close, search, reset];
  panel.querySelector = s => s === '[data-filter-close]' ? close : null;
  form.querySelector = s => s === '#q' ? search : null;
  const selectors = {
    '#filter-toggle': toggle, '#advanced-filter-disclosure': new Element(),
    '#advanced-filter-panel': panel, '#contract-filter-form': form,
    '.contract-filter-dialog': dialog, '.contract-filter-dialog [data-filter-close]': close,
    '#q': search, '#contract-filter-form .advanced-filter-actions a': reset,
  };
  document = {
    body: new Element(), documentElement: new Element(), activeElement: null,
    querySelector: s => selectors[s] ?? null, querySelectorAll: () => [],
    createElement: () => dialog, hasFocus: () => true,
  };
  const context = vm.createContext({document, HTMLDialogElement: Dialog,
    matchMedia: () => ({matches: false}), getComputedStyle: e => ({visibility: e.visibility}),
    window: {innerWidth: 390, innerHeight: 1000, addEventListener() {}}, location: {hash: ''}});
  vm.runInContext(source, context);
  function tab(active, options = {}) {
    active.focus();
    const event = {key: 'Tab', prevented: false, preventDefault() {this.prevented = true;}, ...options};
    dialog.listeners.keydown(event);
    return event.prevented;
  }
  return {context, document, dialog, toggle, close, search, reset, tab, Element};
}

if (process.argv[2] === 'diagnostics') {
  const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
  const f = fixture(); f.toggle.listeners.click();
  const active = {close: f.close, reset: f.reset, search: f.search, toggle: f.toggle,
    body: f.document.body, outside: new f.Element(), inside: new f.Element()}[payload.active];
  if (payload.active === 'inside') f.dialog.items.push(active);
  active.focus();
  const read = vm.runInContext('(' + payload.expression + ')', f.context);
  process.stdout.write(JSON.stringify(read(payload.arguments)));
} else {
  const {test} = require('node:test');
  test('modal semantics, initial focus, close restoration and reopening', () => {
    const f = fixture(); f.toggle.listeners.click();
    assert.equal(f.document.activeElement, f.search);
    assert.equal(f.dialog.getAttribute('aria-modal'), 'true');
    assert.equal(f.toggle.getAttribute('aria-controls'), f.dialog.id);
    assert.equal(f.toggle.getAttribute('aria-expanded'), 'true');
    f.close.listeners.click();
    assert.equal(f.document.activeElement, f.toggle);
    assert.equal(f.toggle.getAttribute('aria-expanded'), 'false');
    f.toggle.listeners.click(); assert.equal(f.document.activeElement, f.search);
  });
  test('forward and reverse boundary traversal cycle through the real handler', () => {
    const f = fixture(); f.toggle.listeners.click();
    assert.equal(f.tab(f.reset), true); assert.equal(f.document.activeElement, f.close);
    assert.equal(f.tab(f.close, {shiftKey: true}), true); assert.equal(f.document.activeElement, f.reset);
    assert.equal(f.tab(f.dialog), true); assert.equal(f.document.activeElement, f.close);
    assert.equal(f.tab(f.dialog, {shiftKey: true}), true); assert.equal(f.document.activeElement, f.reset);
  });
  for (const [property, value] of Object.entries({disabled: true, hidden: true, inert: true,
    tabIndex: -1, rendered: false, visibility: 'hidden'})) {
    test('recompute eligible controls when ' + property + ' changes', () => {
      const f = fixture(); f.toggle.listeners.click();
      f.close[property] = value;
      assert.equal(f.tab(f.reset), true); assert.equal(f.document.activeElement, f.search);
      f.reset[property] = value;
      assert.equal(f.tab(f.search, {shiftKey: true}), true);
      assert.equal(f.document.activeElement, f.search);
    });
  }
  test('internal traversal, modifiers, handled events and closed dialog are untouched', () => {
    const f = fixture(); f.toggle.listeners.click();
    assert.equal(f.tab(f.search), false);
    assert.equal(f.tab(f.search, {shiftKey: true}), false);
    for (const options of [{ctrlKey: true}, {altKey: true}, {metaKey: true},
      {defaultPrevented: true}, {key: 'Escape'}, {key: 'Enter'}]) {
      assert.equal(f.tab(f.reset, options), false); assert.equal(f.document.activeElement, f.reset);
    }
    f.dialog.close(); assert.equal(f.tab(f.reset), false);
  });
  test('empty eligible set does not tab into the background', () => {
    const f = fixture(); f.toggle.listeners.click(); f.dialog.items = [];
    assert.equal(f.tab(f.dialog), true); assert.equal(f.document.activeElement, f.dialog);
  });
}
