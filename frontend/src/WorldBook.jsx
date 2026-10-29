import { useEffect, useState } from 'react';
import { api } from './api';

const EMPTY = {
  id: null,
  keywords: '',
  keywords_secondary: '',
  logic: 'and_any',
  depth: '',
  sticky: '',
  content: '',
  constant: false,
};

const LOGIC_LABELS = {
  and_any: '副键任一命中',
  and_all: '副键全部命中',
  not_any: '副键都不出现',
  not_all: '副键非全部出现',
};

export default function WorldBook({ character, onClose, embedded = false }) {
  const [entries, setEntries] = useState([]);
  const [scope, setScope] = useState('character');
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const listUrl =
    scope === 'global'
      ? '/api/world/global'
      : `/api/characters/${character.id}/world`;

  async function load() {
    try {
      setEntries(await api(listUrl));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    setForm(EMPTY);
    setError('');
    load();
  }, [character.id, scope]);

  function parseKeywords(text) {
    return text
      .split(/[,，\s]+/)
      .map((k) => k.trim())
      .filter(Boolean);
  }

  async function save() {
    const content = form.content.trim();
    const keywords = parseKeywords(form.keywords);
    if (!content) {
      setError('设定内容不能为空');
      return;
    }
    if (!keywords.length && !form.constant) {
      setError('普通条目至少写一个关键词（或用「常驻」）');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body = JSON.stringify({
        keywords,
        keywords_secondary: parseKeywords(form.keywords_secondary),
        logic: form.logic,
        depth: form.depth === '' ? -1 : Number(form.depth),
        sticky: form.sticky === '' ? 0 : Number(form.sticky),
        content,
        constant: form.constant,
      });
      await api(form.id ? `/api/world/${form.id}` : listUrl, {
        method: form.id ? 'PATCH' : 'POST',
        body,
      });
      setForm(EMPTY);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(entry) {
    await api(`/api/world/${entry.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !entry.enabled }),
    });
    load();
  }

  async function remove(entry) {
    if (!window.confirm('删除这条设定？')) return;
    await api(`/api/world/${entry.id}`, { method: 'DELETE' });
    if (form.id === entry.id) setForm(EMPTY);
    load();
  }

  function edit(entry) {
    setForm({
      id: entry.id,
      keywords: entry.keywords.join('，'),
      keywords_secondary: (entry.keywords_secondary || []).join('，'),
      logic: entry.logic || 'and_any',
      depth: entry.depth === null ? '' : String(entry.depth),
      sticky: entry.sticky ? String(entry.sticky) : '',
      content: entry.content,
      constant: entry.constant,
    });
    setError('');
  }

  const panel = (
      <div
        className={embedded ? 'panel-embed world-embed' : 'modal detail-modal'}
        onClick={embedded ? undefined : (e) => e.stopPropagation()}
      >
        <div className="world-head">
          <h2>世界书 · {character.name}</h2>
          <div className="world-scope">
            <button
              className={scope === 'character' ? 'active' : ''}
              onClick={() => setScope('character')}
            >
              本角色
            </button>
            <button
              className={scope === 'global' ? 'active' : ''}
              onClick={() => setScope('global')}
            >
              全局
            </button>
          </div>
          <p className="world-hint">
            {scope === 'global'
              ? '全局条目对所有角色生效，命中时会一起注入。'
              : '对话里出现关键词时，对应设定会自动注入；「常驻」条目每次都带上。'}
          </p>
        </div>

        <div className="world-form">
          <input
            value={form.keywords}
            onChange={(e) => setForm({ ...form, keywords: e.target.value })}
            placeholder="主关键词，用逗号分隔：图书馆，旧书，地下室"
          />
          <input
            value={form.keywords_secondary}
            onChange={(e) =>
              setForm({ ...form, keywords_secondary: e.target.value })
            }
            placeholder="副关键词（可选）：需额外满足的条件"
          />
          <div className="world-row">
            <select
              value={form.logic}
              onChange={(e) => setForm({ ...form, logic: e.target.value })}
              title="副关键词的匹配逻辑"
            >
              {Object.entries(LOGIC_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="0"
              value={form.depth}
              onChange={(e) => setForm({ ...form, depth: e.target.value })}
              placeholder="深度"
              title="留空=注入系统提示词；填 0=插在最后一条之后"
            />
            <input
              type="number"
              min="0"
              value={form.sticky}
              onChange={(e) => setForm({ ...form, sticky: e.target.value })}
              placeholder="粘性轮数"
              title="命中后继续生效的轮数"
            />
          </div>
          <textarea
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            rows={3}
            placeholder="命中后注入的设定内容"
          />
          <div className="world-form-foot">
            <label>
              <input
                type="checkbox"
                checked={form.constant}
                onChange={(e) =>
                  setForm({ ...form, constant: e.target.checked })
                }
              />
              常驻
            </label>
            <div className="world-form-actions">
              {form.id && (
                <button className="ghost-btn" onClick={() => setForm(EMPTY)}>
                  取消编辑
                </button>
              )}
              <button className="primary-btn" onClick={save} disabled={busy}>
                {busy ? '保存中…' : form.id ? '保存修改' : '添加条目'}
              </button>
            </div>
          </div>
        </div>

        {error && <p className="world-error">{error}</p>}

        <div className="world-list">
          {entries.length === 0 && (
            <p className="world-empty">还没有设定条目</p>
          )}
          {entries.map((entry) => (
            <div
              key={entry.id}
              className={`world-entry ${entry.enabled ? '' : 'off'}`}
            >
              <div className="world-entry-head">
                <span className="tag-row">
                  {entry.constant && <em>常驻</em>}
                  {entry.keywords.map((k) => (
                    <em key={k}>{k}</em>
                  ))}
                  {entry.keywords_secondary?.length > 0 && (
                    <em className="muted-tag">
                      +{entry.keywords_secondary.join('/')}（
                      {LOGIC_LABELS[entry.logic] || entry.logic}）
                    </em>
                  )}
                  {entry.depth != null && <em>深度 {entry.depth}</em>}
                  {entry.sticky > 0 && <em>粘性 {entry.sticky}</em>}
                </span>
                <span className="world-tools">
                  <button onClick={() => toggle(entry)}>
                    {entry.enabled ? '停用' : '启用'}
                  </button>
                  <button onClick={() => edit(entry)}>编辑</button>
                  <button onClick={() => remove(entry)}>删除</button>
                </span>
              </div>
              <p className="world-content">{entry.content}</p>
            </div>
          ))}
        </div>

        {!embedded && (
          <div className="modal-actions detail-actions">
            <button className="ghost-btn" onClick={onClose}>
              关闭
            </button>
          </div>
        )}
      </div>
  );

  if (embedded) return panel;

  return (
    <div className="modal-overlay" onClick={onClose}>
      {panel}
    </div>
  );
}
