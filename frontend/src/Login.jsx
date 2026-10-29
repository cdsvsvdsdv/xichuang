import { useState } from 'react';
import { api, setToken } from './api';

export default function Login({ onLogin, firstRun }) {
  const [mode, setMode] = useState(firstRun ? 'register' : 'login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [invite, setInvite] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const payload =
        mode === 'register'
          ? { username, password, invite }
          : { username, password };
      const data = await api(`/api/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setToken(data.token);
      onLogin(data.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <h1 className="brand">
          西窗<span>.</span>
        </h1>
        <p className="brand-sub">和朋友一起玩角色对话</p>

        <div className="login-tabs">
          <button
            type="button"
            className={mode === 'login' ? 'active' : ''}
            onClick={() => {
              setMode('login');
              setError('');
            }}
          >
            登录
          </button>
          <button
            type="button"
            className={mode === 'register' ? 'active' : ''}
            onClick={() => {
              setMode('register');
              setError('');
            }}
          >
            注册
          </button>
        </div>

        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="用户名"
          autoComplete="username"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码（至少 6 位）"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        />
        {mode === 'register' && !firstRun && (
          <input
            value={invite}
            onChange={(e) => setInvite(e.target.value)}
            placeholder="邀请码"
          />
        )}

        {firstRun && mode === 'register' && (
          <p className="login-hint">首次使用：直接注册，你就是管理员。</p>
        )}

        {error && <p className="form-error">{error}</p>}

        <button className="primary-btn" type="submit" disabled={busy}>
          {busy ? '处理中…' : mode === 'login' ? '登录' : '注册并进入'}
        </button>
      </form>
    </div>
  );
}
