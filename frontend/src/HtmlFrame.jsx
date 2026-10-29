import { useEffect, useMemo, useRef, useState } from 'react';

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
  try {
    window.requestAnimationFrame = function (cb) {
      return setTimeout(function () { cb(performance.now()); }, 50);
    };
    var rawInterval = window.setInterval;
    window.setInterval = function (fn, ms) {
      return rawInterval(fn, Math.max(Number(ms) || 0, 120));
    };
  } catch (e) {}
  var pending = {};
  var seq = 0;
  function bridge(method, args) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      pending[id] = { resolve: resolve, reject: reject };
      parent.postMessage({ __xc: 1, id: id, method: method, args: args || [] }, '*');
    });
  }
  window.addEventListener('message', function (event) {
    var data = event.data;
    if (!data || data.__xc !== 1 || data.id == null) return;
    var item = pending[data.id];
    if (!item) return;
    delete pending[data.id];
    if (data.ok) item.resolve(data.result);
    else item.reject(new Error(data.error || 'bridge error'));
  });

  var listeners = {};
  var noop = function () {};
  window.eventOn = function (name, cb) {
    (listeners[name] = listeners[name] || []).push(cb);
    return { stop: function () { window.eventRemoveListener(name, cb); } };
  };
  window.eventOnce = function (name, cb) {
    var handle = window.eventOn(name, function (payload) {
      window.eventRemoveListener(name, cb);
      cb(payload);
    });
    return handle;
  };
  window.eventRemoveListener = function (name, cb) {
    var list = listeners[name] || [];
    var index = list.indexOf(cb);
    if (index >= 0) list.splice(index, 1);
  };
  window.eventEmit = function (name, payload) {
    (listeners[name] || []).slice().forEach(function (cb) { cb(payload); });
  };

  window.alert = function (message) { console.log('[card alert]', message); };
  window.confirm = function (message) { console.log('[card confirm]', message); return true; };
  window.prompt = function (message, fallback) { console.log('[card prompt]', message); return fallback || ''; };

  window.getChatMessages = function (range) { return bridge('getChatMessages', [range]); };
  window.setChatMessages = function (messages, options) { return bridge('setChatMessages', [messages, options]); };
  window.getCurrentMessageId = function () { return 0; };
  window.getLastMessageId = function () { return 0; };
  window.getVariables = function () { return bridge('getVariables', []); };
  window.setVariables = function (vars) { return bridge('setVariables', [vars]); };
  window.formatAsTavernRegexedString = function (s) { return s; };

  window.TavernHelper = window.TavernHelper || {
    generate: function (config) { return bridge('generate', [config]); },
    generateRaw: function (config) { return bridge('generateRaw', [config]); },
    getChatMessages: window.getChatMessages,
    setChatMessages: window.setChatMessages,
    getCurrentMessageId: window.getCurrentMessageId,
    eventOn: window.eventOn,
    eventOnce: window.eventOnce,
    eventEmit: window.eventEmit,
    getVariables: window.getVariables,
    setVariables: window.setVariables,
    replaceVariables: function (s) { return s; },
    getCharData: function () { return {}; },
    getLorebookEntries: function (name) { return bridge('getLorebookEntries', [name]); },
    setLorebookEntries: function (name, entries) { return bridge('setLorebookEntries', [name, entries]); }
  };
})();
</script>`;

function buildDoc(html) {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${CSP}">`;
  let doc = (html || '').replace(/\blocalStorage\b/g, '__xcStorage');
  if (/<head[^>]*>/i.test(doc)) {
    doc = doc.replace(/<head([^>]*)>/i, `<head$1>${meta}${STUB}`);
  } else {
    doc = `<!DOCTYPE html><html><head>${meta}${STUB}</head><body>${doc}</body></html>`;
  }
  return doc;
}

export default function HtmlFrame({ html, label = 'HTML 界面', onRequest }) {
  const [showSource, setShowSource] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [paused, setPaused] = useState(false);
  const srcdoc = useMemo(() => buildDoc(html), [html]);
  const iframeRef = useRef(null);
  const handlerRef = useRef(onRequest);

  useEffect(() => {
    handlerRef.current = onRequest;
  }, [onRequest]);

  useEffect(() => {
    function onMessage(event) {
      const frame = iframeRef.current;
      if (!frame || event.source !== frame.contentWindow) return;
      const data = event.data;
      if (!data || data.__xc !== 1 || data.id == null) return;
      const reply = (ok, result, error) => {
        frame.contentWindow?.postMessage(
          { __xc: 1, id: data.id, ok, result, error },
          '*'
        );
      };
      const task = handlerRef.current
        ? Promise.resolve(handlerRef.current(data.method, data.args || []))
        : Promise.reject(new Error('interface bridge disabled'));
      task
        .then((result) => reply(true, result))
        .catch((error) => reply(false, null, error?.message || 'bridge error'));
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  return (
    <div className={`html-frame ${expanded ? 'expanded' : ''}`}>
      <div className="html-frame-bar">
        <span>{label}（预览）</span>
        <div>
          {!showSource && (
            <button type="button" onClick={() => setPaused((v) => !v)}>
              {paused ? '加载界面' : '停止界面'}
            </button>
          )}
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
      ) : paused ? (
        <div className="html-frame-paused">
          <span>界面已停止（防止动画卡顿）</span>
          <button type="button" onClick={() => setPaused(false)}>
            重新加载
          </button>
        </div>
      ) : (
        <iframe
          ref={iframeRef}
          title={label}
          sandbox="allow-scripts allow-modals"
          srcDoc={srcdoc}
          referrerPolicy="no-referrer"
        />
      )}
    </div>
  );
}
