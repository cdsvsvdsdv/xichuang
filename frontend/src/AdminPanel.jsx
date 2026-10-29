import { useEffect, useState } from 'react';
import { api } from './api';

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AdminPanel({ onClose }) {
  const [invites, setInvites] = useState([]);
  const [userCount, setUserCount] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState('');

  async function load() {
    setError('');
    try {
      const [list, status] = await Promise.all([
        api('/api/auth/invites'),
        api('/api/auth/status'),
      ]);
      setInvites(list);
      setUserCount(status.users);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createInvite() {
    setBusy(true);
    setError('');
    try {
      await api('/api/auth/invites', { method: 'POST' });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function copy(code) {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(code);
      setTimeout(() => setCopied(''), 1500);
    } catch {
      setError('复制失败，请手动选择文本');
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal settings-modal admin-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <strong>邀请码管理</strong>
          <button onClick={onClose}>关闭</button>
        </div>

        <div className="admin-summary">
          <span>已注册用户：{userCount === null ? '…' : userCount}</span>
          <button className="primary-btn" onClick={createInvite} disabled={busy}>
            {busy ? '生成中…' : '生成新邀请码'}
          </button>
        </div>

        <p className="admin-hint">
          把邀请码发给朋友，注册页填写后即可创建账号。每个邀请码只能使用一次。
        </p>

        {error && <p className="form-error">{error}</p>}

        <div className="admin-list">
          {!invites.length && <p className="empty-hint">还没有邀请码</p>}
          {invites.map((invite) => (
            <div key={invite.id} className="admin-invite">
              <div className="admin-invite-main">
                <code>{invite.code}</code>
                <small>
                  {formatDate(invite.created_at)} ·{' '}
                  {invite.used ? '已使用' : '未使用'}
                </small>
              </div>
              <button onClick={() => copy(invite.code)}>
                {copied === invite.code ? '已复制' : '复制'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
