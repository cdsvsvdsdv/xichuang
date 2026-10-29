import { useEffect, useState } from 'react';
import { api } from './api';

const SIZES = [
  { label: '1:1', value: '1024x1024' },
  { label: '3:4', value: '768x1024' },
  { label: '16:9', value: '1024x576' },
];

export default function ImagePanel({ conversation, onClose }) {
  const [prompt, setPrompt] = useState('');
  const [size, setSize] = useState('1024x1024');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [images, setImages] = useState([]);
  const [current, setCurrent] = useState(null);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    api('/api/images/status')
      .then(setStatus)
      .catch(() => {});
  }, []);

  useEffect(() => {
    let alive = true;
    api(`/api/conversations/${conversation.id}/images`)
      .then((list) => {
        if (!alive) return;
        setImages(list);
        if (list.length) setCurrent(list[0]);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [conversation.id]);

  async function generate() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const data = await api('/api/images/generate', {
        method: 'POST',
        body: JSON.stringify({
          conversation_id: conversation.id,
          prompt: prompt.trim() || null,
          size,
        }),
      });
      setCurrent(data);
      setImages((prev) => [data, ...prev]);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!window.confirm('删除这张图？')) return;
    try {
      await api(`/api/images/${id}`, { method: 'DELETE' });
      setImages((prev) => prev.filter((item) => item.id !== id));
      setCurrent((prev) => (prev?.id === id ? null : prev));
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal image-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <strong>场景配图</strong>
          <button onClick={onClose}>关闭</button>
        </div>

        {status?.provider === 'pollinations' && (
          <p className="image-note">
            当前使用免密钥生图服务，额度有限、可能随时限流。建议在
            backend/.env 配置 ZHIPU_API_KEY（智谱，有免费额度）或
            SILICONFLOW_API_KEY。
          </p>
        )}

        {current && (
          <div className="image-current">
            <img src={current.url} alt={current.prompt} />
            <p className="image-prompt">{current.prompt}</p>
            <div className="image-actions">
              <a
                className="ghost-btn"
                href={current.url}
                download
                target="_blank"
                rel="noreferrer"
              >
                下载
              </a>
              <button className="ghost-btn" onClick={generate} disabled={busy}>
                重新生成
              </button>
            </div>
          </div>
        )}

        {busy && (
          <div className="image-loading">正在生成，约 10–30 秒…</div>
        )}

        {!current && !busy && (
          <p className="empty-hint">
            还没有图片。提示词留空时，会根据最近对话自动生成场景。
          </p>
        )}

        <label className="field">
          提示词（可留空）
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            placeholder="例如：雨夜图书馆，暖色台灯，少女靠在书架旁看书，动漫风格"
          />
        </label>

        <div className="image-options">
          <div className="theme-pills">
            {SIZES.map((item) => (
              <button
                key={item.value}
                className={`theme-pill ${size === item.value ? 'active' : ''}`}
                onClick={() => setSize(item.value)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <button className="primary-btn" onClick={generate} disabled={busy}>
            {busy ? '生成中…' : '生成图片'}
          </button>
        </div>

        {error && <p className="form-error">{error}</p>}

        {images.length > 0 && (
          <div>
            <h4>本会话的图（{images.length}）</h4>
            <div className="image-grid">
              {images.map((img) => (
                <div
                  key={img.id}
                  className={`image-thumb ${
                    current?.id === img.id ? 'active' : ''
                  }`}
                  onClick={() => setCurrent(img)}
                >
                  <img src={img.url} alt="" />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      remove(img.id);
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
