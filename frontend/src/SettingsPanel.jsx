import { useState } from 'react';

const THEMES = [
  { id: 'default', label: '深空' },
  { id: 'warm', label: '暖夜' },
  { id: 'forest', label: '松间' },
  { id: 'ocean', label: '海盐' },
];

export default function SettingsPanel({ profile, onClose, onSave, embedded = false }) {
  const [name, setName] = useState(profile.name || '');
  const [persona, setPersona] = useState(profile.persona || '');
  const [theme, setTheme] = useState(profile.theme || 'default');
  const [backgroundUrl, setBackgroundUrl] = useState(
    profile.background_url || ''
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setBusy(true);
    setError('');
    try {
      await onSave({
        name: name.trim(),
        persona: persona.trim(),
        theme,
        background_url: backgroundUrl.trim(),
      });
      onClose?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const panel = (
      <div
        className={embedded ? 'panel-embed settings-embed' : 'modal settings-modal'}
        onClick={embedded ? undefined : (e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <strong>设置</strong>
          {!embedded && <button onClick={onClose}>关闭</button>}
        </div>

        <label className="field">
          你的称呼
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="角色会这样称呼你"
            maxLength={80}
          />
        </label>

        <label className="field">
          用户人设
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            rows={4}
            placeholder="例如：23 岁，喜欢在雨天写代码，说话随意，不太擅长表达情绪。"
            maxLength={2000}
          />
        </label>

        <div className="field">
          界面主题
          <div className="theme-pills">
            {THEMES.map((item) => (
              <button
                key={item.id}
                className={`theme-pill ${theme === item.id ? 'active' : ''}`}
                onClick={() => setTheme(item.id)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <label className="field">
          聊天背景图 URL（可选）
          <input
            value={backgroundUrl}
            onChange={(e) => setBackgroundUrl(e.target.value)}
            placeholder="https://example.com/bg.jpg"
          />
        </label>

        {error && <p className="form-error">{error}</p>}

        <div className="modal-actions">
          <button className="primary-btn" onClick={save} disabled={busy}>
            {busy ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
  );

  if (embedded) return panel;

  return (
    <div className="modal-overlay" onClick={onClose}>
      {panel}
    </div>
  );
}
