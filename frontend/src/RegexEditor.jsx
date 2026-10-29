import { useEffect, useState } from 'react';
import { api } from './api';

const EMPTY = {
  id: null,
  name: '',
  pattern: '',
  replacement: '',
  scope: 'assistant',
  enabled: true,
};

const SCOPE_LABELS = {
  assistant: 'AI 回复',
  user: '用户输入',
  both: '两者',
};

export default function RegexEditor({ character, canManage }) {
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    try {
      setRules(await api(`/api/characters/${character.id}/regex`));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    setForm(EMPTY);
    setError('');
    load();
  }, [character.id]);

  function edit(rule) {
    setForm({ ...rule });
    setError('');
  }

  async function save() {
    if (!form.pattern.trim()) {
      setError('正则表达式不能为空');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body = JSON.stringify({
        name: form.name.trim(),
        pattern: form.pattern,
        replacement: form.replacement,
        scope: form.scope,
        enabled: form.enabled,
      });
      if (form.id) {
        await api(`/api/regex/${form.id}`, { method: 'PATCH', body });
      } else {
        await api(`/api/characters/${character.id}/regex`, {
          method: 'POST',
          body,
        });
      }
      setForm(EMPTY);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(rule) {
    try {
      await api(`/api/regex/${rule.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(rule) {
    if (!window.confirm(`删除正则「${rule.name || rule.pattern}」？`)) return;
    try {
      await api(`/api/regex/${rule.id}`, { method: 'DELETE' });
      if (form.id === rule.id) setForm(EMPTY);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="regex-embed">
      <p className="panel-hint">
        查找替换规则：AI 回复或用户输入会按顺序执行。模式支持 Python 正则，例如
        <code> （.*?）</code> 可以匹配括号里的动作。
      </p>

      <div className="regex-form">
        <input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="规则名（可选）"
          maxLength={80}
          disabled={!canManage}
        />
        <input
          className="regex-mono"
          value={form.pattern}
          onChange={(e) => setForm({ ...form, pattern: e.target.value })}
          placeholder="查找：正则表达式，例如 \\*\\*(.+?)\\*\\*"
          maxLength={500}
          disabled={!canManage}
        />
        <input
          className="regex-mono"
          value={form.replacement}
          onChange={(e) => setForm({ ...form, replacement: e.target.value })}
          placeholder="替换为：可用 \\1 引用分组，留空表示删除"
          maxLength={2000}
          disabled={!canManage}
        />
        <div className="regex-form-row">
          <select
            value={form.scope}
            onChange={(e) => setForm({ ...form, scope: e.target.value })}
            disabled={!canManage}
          >
            {Object.entries(SCOPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <label className="regex-check">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              disabled={!canManage}
            />
            启用
          </label>
          <button
            className="primary-btn"
            onClick={save}
            disabled={!canManage || busy}
            type="button"
          >
            {busy ? '保存中…' : form.id ? '保存修改' : '添加规则'}
          </button>
          {form.id && (
            <button
              className="ghost-btn"
              onClick={() => setForm(EMPTY)}
              type="button"
            >
              取消
            </button>
          )}
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="regex-list">
        {!rules.length && <p className="empty-hint">还没有正则规则</p>}
        {rules.map((rule) => (
          <div key={rule.id} className={`regex-item ${rule.enabled ? '' : 'off'}`}>
            <div className="regex-item-main">
              <div className="regex-item-head">
                <strong>{rule.name || '未命名规则'}</strong>
                <em>{SCOPE_LABELS[rule.scope] || rule.scope}</em>
              </div>
              <code className="regex-mono">{rule.pattern}</code>
              <span className="regex-arrow">
                → {rule.replacement || '（删除）'}
              </span>
            </div>
            {canManage && (
              <div className="regex-tools">
                <button onClick={() => toggle(rule)}>
                  {rule.enabled ? '停用' : '启用'}
                </button>
                <button onClick={() => edit(rule)}>编辑</button>
                <button onClick={() => remove(rule)}>删除</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
