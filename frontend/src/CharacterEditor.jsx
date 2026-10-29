import { useState } from 'react';

export default function CharacterEditor({ character, onClose, onSave }) {
  const creating = !character;
  const [name, setName] = useState(character?.name || '');
  const [avatarUrl, setAvatarUrl] = useState(character?.avatar_url || '');
  const [tagline, setTagline] = useState(character?.tagline || '');
  const [persona, setPersona] = useState(character?.persona || '');
  const [greeting, setGreeting] = useState(character?.greeting || '');
  const [alternates, setAlternates] = useState(
    (character?.alternates || []).join('\n')
  );
  const [tags, setTags] = useState((character?.tags || []).join(', '));
  const [systemPrompt, setSystemPrompt] = useState(
    character?.system_prompt || ''
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    if (!name.trim() || !greeting.trim()) {
      setError('角色名和开场白不能为空');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await onSave(creating ? null : character.id, {
        name: name.trim(),
        avatar_url: avatarUrl.trim(),
        tagline: tagline.trim(),
        persona: persona.trim(),
        greeting: greeting.trim(),
        alternates: alternates
          .split('\n')
          .map((t) => t.trim())
          .filter(Boolean),
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
      <div
        className="modal settings-modal detail-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <strong>{creating ? '新建角色' : `编辑角色 · ${character.name}`}</strong>
          <button onClick={onClose}>关闭</button>
        </div>

        <label className="field">
          角色名
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={50}
            placeholder="例如 林见夏"
          />
        </label>

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
          角色人设
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            rows={6}
            maxLength={6000}
            placeholder="外貌、身份、性格、说话方式……会整体注入系统提示词。"
          />
        </label>

        <label className="field">
          开场白
          <textarea
            value={greeting}
            onChange={(e) => setGreeting(e.target.value)}
            rows={4}
            maxLength={6000}
          />
        </label>

        <label className="field">
          备选开场（一行一条，可选）
          <textarea
            value={alternates}
            onChange={(e) => setAlternates(e.target.value)}
            rows={3}
            maxLength={6000}
            placeholder="第一行是一个开场白，第二行是另一个……"
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
            rows={4}
            maxLength={3000}
            placeholder="覆盖默认的「对话要求」，角色设定会自动追加在后面。"
          />
        </label>

        {error && <p className="form-error">{error}</p>}

        <div className="modal-actions">
          <button className="primary-btn" onClick={save} disabled={busy}>
            {busy ? '保存中…' : creating ? '创建角色' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
