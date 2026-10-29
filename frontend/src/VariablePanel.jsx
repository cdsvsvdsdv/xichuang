import { useEffect, useState } from 'react';
import { api } from './api';

export default function VariablePanel({ conversation, onClose }) {
  const [rows, setRows] = useState([]);
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setRows(await api(`/api/conversations/${conversation.id}/variables`));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, [conversation.id]);

  function reset() {
    setKey('');
    setValue('');
    setEditingId(null);
    setError('');
  }

  async function submit() {
    const k = key.trim();
    const v = value.trim();
    if (!k) {
      setError('状态名不能为空');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api(
        editingId
          ? `/api/variables/${editingId}`
          : `/api/conversations/${conversation.id}/variables`,
        {
          method: editingId ? 'PATCH' : 'POST',
          body: JSON.stringify({ key: k, value: v }),
        }
      );
      reset();
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    if (!window.confirm(`删除状态「${row.key}」？`)) return;
    await api(`/api/variables/${row.id}`, { method: 'DELETE' });
    if (editingId === row.id) reset();
    load();
  }

  function edit(row) {
    setEditingId(row.id);
    setKey(row.key);
    setValue(row.value);
    setError('');
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <strong>状态 · {conversation.title}</strong>
          <button onClick={onClose}>关闭</button>
        </div>

        <p className="world-hint">
          AI 在对话里会自动更新这里的状态（好感度、金钱、地点之类）。先手动加一条，它才会开始维护。
        </p>

        <div className="var-form">
          <input
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="状态名，例如 好感度"
            maxLength={50}
          />
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="当前值，例如 30"
            maxLength={200}
          />
          <button className="primary-btn" onClick={submit} disabled={busy}>
            {busy ? '保存中…' : editingId ? '保存' : '添加'}
          </button>
          {editingId && (
            <button className="ghost-btn" onClick={reset}>
              取消
            </button>
          )}
        </div>

        {error && <p className="world-error">{error}</p>}

        <div className="var-list">
          {rows.length === 0 && <p className="world-empty">还没有状态变量</p>}
          {rows.map((row) => (
            <div key={row.id} className="var-row">
              <span className="var-key">{row.key}</span>
              <span className="var-value">{row.value || '—'}</span>
              <span className="world-tools">
                <button onClick={() => edit(row)}>编辑</button>
                <button onClick={() => remove(row)}>删除</button>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
