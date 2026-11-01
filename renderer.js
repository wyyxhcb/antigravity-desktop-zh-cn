/* Antigravity Desktop 简体中文语言包 — local DOM translation, no network. */
(() => {
  'use strict';
  if (window.top !== window || location.protocol !== 'https:' || location.hostname !== '127.0.0.1') return;
  if (window.__antigravityZhCnInstalled) return;
  window.__antigravityZhCnInstalled = true;

  const protectedSelector = [
    'script', 'style', 'noscript', 'pre', 'code', 'kbd', 'samp', 'textarea',
    '[contenteditable]:not([contenteditable="false"])', '[data-lexical-editor]',
    '[role="log"]', '[id^="user-content-"]',
    '.markdown', '.markdown-body', '.prose', '.monaco-editor', '.cm-editor', '.xterm',
    '[data-message-id]', '[data-message-author-role]', '[data-language]',
    '[data-no-translate]', '[translate="no"]', '[data-zh-cn="off"]',
    'a[href^="/c/"]', 'a[href*="/c/"]', 'a[href^="/project/"]', 'a[href^="/p/"]',
    '[data-testid^="conversation-row-"] .truncate',
    '[aria-label="Artifact Viewer"]', '[aria-label="产物查看器"]'
  ].join(',');
  const uiSelector = [
    'button', 'a', '[role="button"]', '[role="menu"]', '[role="menuitem"]',
    '[role="menuitemcheckbox"]', '[role="menuitemradio"]', '[role="dialog"]',
    '[role="alertdialog"]', '[role="tooltip"]', '[role="tab"]', '[role="option"]',
    '[role="listbox"]', '[role="combobox"]', '[role="switch"]', '[role="checkbox"]',
    'nav', '[role="navigation"]', 'a[href="/"]', 'a[href$="/customizations"]',
    'label', 'h1', 'h2', 'h3', '[role="heading"]', '[role="status"]',
    '[aria-label="Artifact Viewer header"]', '[aria-label="产物查看器标题栏"]',
    '[data-zh-cn="ui"]'
  ].join(',');
  // The composer renders this static hint outside its editable surface.
  const staticHints = new Set(/*__ZH_CN_SOURCE_TEXT__*/ []);
  staticHints.add('Featured');
  const attributes = ['title', 'aria-label', 'placeholder', 'data-placeholder'];
  const translate = agZh.translate;
  const actionControls = new WeakSet();
  function protectedElement(element) {
    return !element || !!element.closest(protectedSelector);
  }
  function articleContent(element) {
    if (!element.closest('article,[role="article"]')) return false;
    // Translate explicit app action controls, but never prose or file/attachment names.
    const control=element.closest('button,[role="button"]');
    if (!control) return true;
    if (actionControls.has(control)) return false;
    const label=control.getAttribute('aria-label') || '';
    if (/^(?:Copy(?: Message)?|Undo to (?:Here|this point)|Good response|Bad response|Stop generating|Proceed with Plan|Accept(?: All)?|Reject(?: All)?|Allow Once|Always Allow|Worked for \d|Thought for \d)/i.test(label)) { actionControls.add(control); return false; }
    return true;
  }
  function text(node) {
    const parent = node.parentElement;
    if (protectedElement(parent) || articleContent(parent) || (!parent.closest(uiSelector) && !staticHints.has(node.data.trim()) && !agZh.knownStatic(node.data))) return;
    const translated = translate(node.data);
    if (translated !== node.data) node.data = translated;
  }
  function element(node) {
    const editable=node.matches('input,textarea,[contenteditable]:not([contenteditable="false"]),[data-lexical-editor]');
    if ((!editable && protectedElement(node)) || articleContent(node)) return;
    for (const name of attributes) {
      if (!node.hasAttribute(name)) continue;
      const before = node.getAttribute(name);
      const after = translate(before);
      if (after !== before) node.setAttribute(name, after);
    }
  }
  function scan(root) {
    if (root.nodeType === Node.TEXT_NODE) { text(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    element(root);
    if (protectedElement(root)) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (node.nodeType === Node.ELEMENT_NODE && protectedElement(node)) { element(node); return NodeFilter.FILTER_REJECT; }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.nodeType === Node.TEXT_NODE) text(node);
      else element(node);
    }
  }
  function start() {
    // Only a main application window has this root. Never traverse embedded pages.
    if (!document.getElementById('root') || !document.body) return;
    document.documentElement.lang = 'zh-CN';
    scan(document.body);
    const pending = new Set();
    let timer = null;
    const observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'childList') {
          for (const child of record.addedNodes) pending.add(child);
        } else pending.add(record.target);
      }
      if (timer !== null) return;
      timer = setTimeout(() => {
        timer = null;
        const nodes = [...pending]; pending.clear();
        for (const node of nodes) if (node.isConnected) scan(node);
      }, 40);
    });
    observer.observe(document.body, {
      childList: true, characterData: true, subtree: true,
      attributes: true, attributeFilter: attributes
    });
    window.addEventListener('pagehide', () => {
      observer.disconnect(); if (timer !== null) clearTimeout(timer); pending.clear();
    }, { once: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
