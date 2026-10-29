import { useMemo, useRef, useState } from 'react';

export function charHue(character) {
  const text = `${character?.id || ''}${character?.name || ''}`;
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) % 360;
  }
  return hash;
}

function CardAvatar({ character, index }) {
  if (character.avatar_url) {
    return (
      <span className="gallery-avatar with-img">
        <img src={character.avatar_url} alt="" />
      </span>
    );
  }
  return (
    <span className={`gallery-avatar hue-${index % 4}`}>
      {character.name.slice(0, 1)}
    </span>
  );
}

export default function Gallery({
  characters,
  user,
  onStart,
  onFavorite,
  onEdit,
  onExport,
  onDelete,
  onImport,
  onCreate,
  onOpenInvites,
  onLogout,
}) {
  const [query, setQuery] = useState('');
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [menuId, setMenuId] = useState(null);
  const fileRef = useRef(null);

  const visible = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return characters.filter((c) => {
      if (onlyFavorites && !c.favorite) return false;
      if (!keyword) return true;
      const haystack = `${c.name} ${c.tagline} ${c.persona} ${(
        c.tags || []
      ).join(' ')}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [characters, query, onlyFavorites]);

  function canManage(character) {
    return Boolean(user?.is_admin) || character.created_by === user?.id;
  }

  return (
    <div className="gallery-page">
      <header className="gallery-header">
        <div className="gallery-brand">
          <h1>
            西窗<span>.</span>
          </h1>
          <p>挑一个角色，开始今天的对话</p>
        </div>
        <div className="gallery-user">
          <a
            className="ghost-btn"
            href="https://tavern.pangyifan.cn"
            target="_blank"
            rel="noreferrer"
          >
            酒馆
          </a>
          {user?.is_admin && (
            <button className="ghost-btn" onClick={onOpenInvites}>
              邀请码
            </button>
          )}
          <span className="gallery-user-name">{user?.username}</span>
          <button className="ghost-btn" onClick={onLogout}>
            退出
          </button>
        </div>
      </header>

      <div className="gallery-toolbar">
        <input
          className="search-input gallery-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索角色名、标签或简介…"
        />
        <button
          className={`ghost-btn ${onlyFavorites ? 'active' : ''}`}
          onClick={() => setOnlyFavorites((v) => !v)}
        >
          {onlyFavorites ? '★ 只看收藏' : '☆ 收藏'}
        </button>
        <button className="ghost-btn" onClick={() => fileRef.current?.click()}>
          导入角色卡
        </button>
        <button className="primary-btn" onClick={onCreate}>
          新建角色
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".json,.png,application/json,image/png"
          hidden
          onChange={(e) => {
            onImport(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
      </div>

      {visible.length === 0 ? (
        <div className="gallery-empty">
          <p>
            {characters.length
              ? '没有匹配的角色，换个关键词试试'
              : '还没有角色卡，新建一个或导入一张吧'}
          </p>
        </div>
      ) : (
        <div className="gallery-grid">
          {visible.map((character, index) => (
            <article
              key={character.id}
              className="char-card"
              style={{ '--hue': charHue(character) }}
            >
              <div className="char-card-top">
                <CardAvatar character={character} index={index} />
                <button
                  className={`char-card-fav ${character.favorite ? 'on' : ''}`}
                  onClick={() => onFavorite(character)}
                  title={character.favorite ? '取消收藏' : '收藏'}
                >
                  {character.favorite ? '★' : '☆'}
                </button>
                <div className="char-card-menu">
                  <button
                    className="char-card-more"
                    onClick={() =>
                      setMenuId(menuId === character.id ? null : character.id)
                    }
                    aria-label="更多操作"
                  >
                    ⋯
                  </button>
                  {menuId === character.id && (
                    <div className="char-card-dropdown">
                      {canManage(character) && (
                        <button
                          onClick={() => {
                            setMenuId(null);
                            onEdit(character);
                          }}
                        >
                          编辑
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setMenuId(null);
                          onExport(character);
                        }}
                      >
                        导出角色卡
                      </button>
                      {canManage(character) && (
                        <button
                          className="danger"
                          onClick={() => {
                            setMenuId(null);
                            onDelete(character);
                          }}
                        >
                          删除
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <h2>{character.name}</h2>
              <p className="char-card-tagline">{character.tagline}</p>
              {character.tags?.length > 0 && (
                <div className="tag-row">
                  {character.tags.slice(0, 3).map((tag) => (
                    <em key={tag}>{tag}</em>
                  ))}
                </div>
              )}

              <button
                className="primary-btn char-card-start"
                onClick={() => onStart(character)}
              >
                开始对话
              </button>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
