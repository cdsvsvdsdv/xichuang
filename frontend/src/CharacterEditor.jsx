import { useState } from 'react';

export default function CharacterEditor({ character, onClose, onSave }) {
  const [avatarUrl, setAvatarUrl] = useState(character.avatar_url || '');
  const [tagline, setTagline] = useState(character.tagline || '');
  const [tags, setTags] = useState((character.tags || []).join(', '));
  const [systemPrompt, setSystemPrompt] = useState(
    character.system_prompt || ''
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setBusy(true);
    setError('');
    try {
      await onSave(character.id, {
        avatar_url: avatarUrl.trim(),
        tagline: tagline.trim(),
        tags: tags
          .split(/[,，]/)
          .map((t) => t.trim())
          .filter(Boolean),
        system_prompt: systemPrompt.trim(),
      });
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <strong>编辑角色 · {character.name}</strong>
          <button onClick={onClose}>关闭</button>
        </div>

        <label className="field">
          头像图片 URL
          <input
            value={avatarUrl}
            onChange={(e) => setAvatarUrl(e.target.value)}
            placeholder="https://example.com/avatar.jpg"
          />
        </label>

        <label className="field">
          一句话简介
          <input
            value={tagline}
            onChange={(e) => setTagline(e.target.value)}
            maxLength={120}
          />
        </label>

        <label className="field">
          标签（用逗号分隔）
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="温柔, 图书馆, 日常"
          />
        </label>

        <label className="field">
          自定义系统提示词（留空使用默认规则）
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={5}
            maxLength={3000}
            placeholder="覆盖默认的「对话要求」，例如指定语气、篇幅、是否描写动作。角色设定会自动追加在后面。"
          />
        </label>

        {error && <p className="form-error">{error}</p>}

        <div className="modal-actions">
          <button className="primary-btn" onClick={save} disabled={busy}>
            {busy ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
