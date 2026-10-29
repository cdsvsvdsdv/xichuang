import { useMemo, useState } from 'react';

const CSP =
  "default-src 'none'; " +
  "script-src 'unsafe-inline'; " +
  "style-src 'unsafe-inline' https:; " +
  "font-src https: data:; " +
  "img-src https: data:; " +
  "media-src https: data:;";

const STUB = `<script>
(function () {
  var mem = {};
  var storage = {
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; },
    setItem: function (k, v) { mem[k] = String(v); },
    removeItem: function (k) { delete mem[k]; },
    clear: function () { mem = {}; },
    key: function (i) { return Object.keys(mem)[i] || null; },
    get length() { return Object.keys(mem).length; }
  };
  window.__xcStorage = storage;
  try { Object.defineProperty(window, 'localStorage', { configurable: true, value: storage }); } catch (e) {}
  var noop = function () {};
  var asyncNoop = function () { return Promise.resolve(''); };
  window.eventEmit = window.eventEmit || noop;
  window.eventOn = window.eventOn || noop;
  window.eventOnce = window.eventOnce || noop;
  window.eventRemoveListener = window.eventRemoveListener || noop;
  window.getChatMessages = window.getChatMessages || function () { return []; };
  window.getCurrentMessageId = window.getCurrentMessageId || function () { return 0; };
  window.getLastMessageId = window.getLastMessageId || function () { return 0; };
  window.getVariables = window.getVariables || function () { return {}; };
  window.setVariables = window.setVariables || noop;
  window.formatAsTavernRegexedString = window.formatAsTavernRegexedString || function (s) { return s; };
  window.TavernHelper = window.TavernHelper || {
    generate: asyncNoop,
    generateRaw: asyncNoop,
    getChatMessages: window.getChatMessages,
    getCurrentMessageId: window.getCurrentMessageId,
    eventOn: noop,
    eventOnce: noop,
    eventEmit: noop,
    getVariables: window.getVariables,
    setVariables: noop,
    replaceVariables: function (s) { return s; },
    getCharData: function () { return {}; }
  };
})();
</script>`;

function buildDoc(html) {
  const meta = "";
  let doc = (html || '').replace(/\blocalStorage\b/g, '__xcStorage');
  if (/<head[^>]*>/i.test(doc)) {
    doc = doc.replace(/<head([^>]*)>/i, `<head$1>${meta}${STUB}`);
  } else {
    doc = `<!DOCTYPE html><html><head>${meta}${STUB}</head><body>${doc}</body></html>`;
  }
  return doc;
}

export default function HtmlFrame({ html, label = 'HTML 界面' }) {
  const [showSource, setShowSource] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const srcdoc = useMemo(() => buildDoc(html), [html]);

  return (
    <div className={`html-frame ${expanded ? 'expanded' : ''}`}>
      <div className="html-frame-bar">
        <span>{label}（预览）</span>
        <div>
          <button type="button" onClick={() => setShowSource((v) => !v)}>
            {showSource ? '看界面' : '看源码'}
          </button>
          <button type="button" onClick={() => setExpanded((v) => !v)}>
            {expanded ? '收起' : '展开'}
          </button>
        </div>
      </div>
      {showSource ? (
        <pre className="html-frame-source">{html}</pre>
      ) : (
        <iframe
          title={label}
          sandbox="allow-scripts"
          srcDoc={srcdoc}
          referrerPolicy="no-referrer"
        />
      )}
    </div>
  );
}
