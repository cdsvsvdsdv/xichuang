import { useEffect, useState } from 'react';
import RegexEditor from './RegexEditor';
import VariablePanel from './VariablePanel';
import WorldBook from './WorldBook';

function splitTags(text) {
  return text
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function CharacterPanel({
  character,
  conversation,
  canManage,
  onSave,
  onApply,
  onAdapt,
}) {
  const [name, setName] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [tagline, setTagline] = useState('');
  const [persona, setPersona] = useState('');
  const [tags, setTags] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [greeting, setGreeting] = useState('');
  const [alternates, setAlternates] = useState([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [section, setSection] = useState('card');

  useEffect(() => {
    if (!character) return;
    setName(character.name || '');
    setAvatarUrl(character.avatar_url || '');
    setTagline(character.tagline || '');
    setPersona(character.persona || '');
    setTags((character.tags || []).join(', '));
    setSystemPrompt(character.system_prompt || '');
    setGreeting(character.greeting || '');
    setAlternates(character.alternates || []);
    setError('');
  }, [character?.id]);

  if (!character) {
    return <p className="empty-hint">先从画廊选一个角色</p>;
  }

  function draft() {
    return {
      name: name.trim(),
      avatar_url: avatarUrl.trim(),
      tagline: tagline.trim(),
      persona: persona.trim(),
      tags: splitTags(tags),
      system_prompt: systemPrompt.trim(),
      greeting: greeting.trim(),
      alternates: alternates.map((item) => item.trim()).filter(Boolean),
    };
  }

  async function handleSave() {
    setBusy('save');
    setError('');
    try {
      await onSave(draft());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  async function handleApply() {
    setBusy('apply');
    setError('');
    try {
      await onApply(draft());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  async function handleAdapt() {
    if (
      !window.confirm(
        '用 AI 把这张卡改写成纯文本版？会覆盖当前人设、开场白和简介，建议先保存备份。'
      )
    ) {
      return;
    }
    setBusy('adapt');
    setError('');
    try {
      await onAdapt();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="char-panel">
      <div className="char-panel-tabs">
        <button
          className={section === 'card' ? 'active' : ''}
          onClick={() => setSection('card')}
        >
          角色卡
        </button>
        <button
          className={section === 'greetings' ? 'active' : ''}
          onClick={() => setSection('greetings')}
        >
          开场白
        </button>
        <button
          className={section === 'world' ? 'active' : ''}
          onClick={() => setSection('world')}
        >
          世界书
        </button>
        <button
          className={section === 'vars' ? 'active' : ''}
          onClick={() => setSection('vars')}
        >
          状态
        </button>
        <button
          className={section === 'preset' ? 'active' : ''}
          onClick={() => setSection('preset')}
        >
          预设
        </button>
        <button
          className={section === 'regex' ? 'active' : ''}
          onClick={() => setSection('regex')}
        >
          正则
        </button>
      </div>

      <div className="char-panel-body">
        {!canManage && (
          <p className="panel-hint">
            这是共享角色，只有创建者或管理员可以修改；你可以直接开始对话。
          </p>
        )}

        {section === 'card' && (
          <>
            {canManage && (
              <div className="adapt-row">
                <button
                  className="ghost-btn"
                  onClick={handleAdapt}
                  disabled={Boolean(busy)}
                  type="button"
                >
                  {busy === 'adapt'
                    ? 'AI 适配中…'
                    : character.html_greeting
                      ? 'AI 适配（纯文本备用）'
                      : 'AI 适配这张卡'}
                </button>
                <span className="panel-hint">
                  {character.html_greeting
                    ? '这张卡有原版前端界面，会优先展示；适配只用于备用'
                    : '把酒馆前端卡改写成纯文本人设和开场白'}
                </span>
              </div>
            )}

            <label className="field">
              角色名
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={50}
                disabled={!canManage}
              />
            </label>
            <label className="field">
              头像 URL
              <input
                value={avatarUrl}
                onChange={(e) => setAvatarUrl(e.target.value)}
                placeholder="https://example.com/avatar.jpg"
                disabled={!canManage}
              />
            </label>
            <label className="field">
              一句话简介
              <input
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                maxLength={120}
                disabled={!canManage}
              />
            </label>
            <label className="field">
              角色人设
              <textarea
                value={persona}
                onChange={(e) => setPersona(e.target.value)}
                rows={7}
                maxLength={6000}
                disabled={!canManage}
              />
            </label>
            <label className="field">
              标签（逗号分隔）
              <input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="温柔, 图书馆, 日常"
                disabled={!canManage}
              />
            </label>
            <label className="field">
              自定义系统提示词（留空用默认规则）
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={4}
                maxLength={3000}
                disabled={!canManage}
              />
            </label>
          </>
        )}

        {section === 'greetings' && (
          <>
            <label className="field">
              主开场白
              <textarea
                value={greeting}
                onChange={(e) => setGreeting(e.target.value)}
                rows={5}
                maxLength={6000}
                disabled={!canManage}
              />
            </label>

            <div className="greeting-list">
              <div className="greeting-head">
                <span>备选开场白（{alternates.length}）</span>
                <button
                  className="ghost-btn"
                  onClick={() => setAlternates([...alternates, ''])}
                  disabled={!canManage || alternates.length >= 10}
                >
                  添加一条
                </button>
              </div>
              {alternates.map((item, index) => (
                <div className="greeting-item" key={index}>
                  <textarea
                    value={item}
                    onChange={(e) => {
                      const next = [...alternates];
                      next[index] = e.target.value;
                      setAlternates(next);
                    }}
                    rows={3}
                    maxLength={6000}
                    disabled={!canManage}
                    placeholder={`备选开场 ${index + 1}`}
                  />
                  <button
                    className="ghost-btn"
                    onClick={() =>
                      setAlternates(alternates.filter((_, i) => i !== index))
                    }
                    disabled={!canManage}
                  >
                    删除
                  </button>
                </div>
              ))}
              <p className="panel-hint">
                保存后，新建对话时可以切换使用这些开场白。
              </p>
            </div>
          </>
        )}

        {section === 'world' && (
          <WorldBook character={character} embedded />
        )}

        {section === 'vars' && (
          conversation ? (
            <VariablePanel conversation={conversation} embedded />
          ) : (
            <p className="empty-hint">开始一段对话后，这里可以编辑当前会话的状态变量。</p>
          )
        )}

        {section === 'preset' && (
          <p className="empty-hint">预设功能在第二批开发中（温度、回复长度等模型参数）。</p>
        )}

        {section === 'regex' && (
          <RegexEditor character={character} canManage={canManage} />
        )}

        {error && <p className="form-error">{error}</p>}
      </div>

      <div className="char-panel-actions">
        {canManage && (
          <button
            className="ghost-btn"
            onClick={handleSave}
            disabled={Boolean(busy)}
          >
            {busy === 'save' ? '保存中…' : '保存'}
          </button>
        )}
        <button
          className="primary-btn"
          onClick={handleApply}
          disabled={Boolean(busy)}
          title="用这份设定开一段新对话"
        >
          {busy === 'apply' ? '创建中…' : '应用并开始新对话'}
        </button>
      </div>
    </div>
  );
}
