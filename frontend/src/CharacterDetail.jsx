export default function CharacterDetail({
  character,
  hue = 0,
  onClose,
  onEdit,
  onFavorite,
  onExport,
  onWorld,
  onStart,
}) {
  const greetings = [
    character.greeting,
    ...(character.alternates || []).filter(Boolean),
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal detail-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="detail-head">
          {character.avatar_url ? (
            <span className="avatar big with-img">
              <img src={character.avatar_url} alt="" />
            </span>
          ) : (
            <span className={`avatar big hue-${hue}`}>
              {character.name.slice(0, 1)}
            </span>
          )}
          <div>
            <h2>{character.name}</h2>
            <p>{character.tagline}</p>
            <div className="tag-row">
              {(character.tags || []).map((tag) => (
                <em key={tag}>{tag}</em>
              ))}
            </div>
          </div>
        </div>

        <div>
          <h4>角色设定</h4>
          <p className="detail-text">{character.persona || '暂无设定'}</p>
        </div>

        <div>
          <h4>开场白（{greetings.length}）</h4>
          <ol className="greeting-list">
            {greetings.map((text, i) => (
              <li key={i}>
                <span className="greeting-index">{i + 1}</span>
                <span>{text}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="modal-actions detail-actions">
          <button className="ghost-btn" onClick={onFavorite}>
            {character.favorite ? '取消收藏' : '收藏'}
          </button>
          <button className="ghost-btn" onClick={onEdit}>
            编辑资料
          </button>
          {onExport && (
            <button className="ghost-btn" onClick={onExport}>
              导出角色卡
            </button>
          )}
          {onWorld && (
            <button className="ghost-btn" onClick={onWorld}>
              世界书
            </button>
          )}
          <button className="primary-btn" onClick={onStart}>
            开始新对话
          </button>
        </div>
      </div>
    </div>
  );
}
