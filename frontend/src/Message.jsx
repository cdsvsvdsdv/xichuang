import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import HtmlFrame from './HtmlFrame';

function splitHtmlBlocks(content) {
  const parts = [];
  const pattern = /```([\s\S]*?)```/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(content)) !== null) {
    const body = match[1].trim();
    const isHtml = /^(<!doctype\s*html|<html|<style)/i.test(body);
    if (!isHtml) continue;
    if (match.index > cursor) {
      parts.push({ type: 'text', value: content.slice(cursor, match.index) });
    }
    parts.push({ type: 'html', value: body });
    cursor = pattern.lastIndex;
  }
  if (cursor < content.length) {
    parts.push({ type: 'text', value: content.slice(cursor) });
  }
  return parts.length ? parts : [{ type: 'text', value: content }];
}

function MessageBody({ content }) {
  const parts = useMemo(() => splitHtmlBlocks(content), [content]);
  const hasHtml = parts.some((part) => part.type === 'html');
  if (!hasHtml) {
    return (
      <div className="markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
          {content}
        </ReactMarkdown>
      </div>
    );
  }
  return (
    <div className="msg-rich">
      {parts.map((part, index) =>
        part.type === 'html' ? (
          <HtmlFrame key={index} html={part.value} />
        ) : (
          part.value.trim() && (
            <div className="markdown" key={index}>
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {part.value}
              </ReactMarkdown>
            </div>
          )
        )
      )}
    </div>
  );
}

export default function Message({
  message,
  character,
  hue,
  isLast,
  streaming,
  onRegenerate,
  onSwipe,
  onCopy,
  onEdit,
  onDelete,
  onIllustrate,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [saving, setSaving] = useState(false);
  const isAssistant = message.role === 'assistant';
  const variants = message.variants || [];
  const variantTotal = variants.length;
  const variantIndex = message.active_variant ?? 0;

  async function save() {
    const text = draft.trim();
    if (!text) return;
    if (text === message.content) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onEdit(message.id, text);
      setEditing(false);
    } catch {
      /* keep editing on failure */
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`msg ${message.role}`}>
      {isAssistant && (
        <span
          className={`msg-avatar ${
            character?.avatar_url ? 'with-img' : `hue-${hue}`
          }`}
        >
          {character?.avatar_url ? (
            <img src={character.avatar_url} alt="" />
          ) : (
            character?.name.slice(0, 1)
          )}
        </span>
      )}

      <div className="msg-main">
        {editing ? (
          <div className="edit-box">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={Math.min(10, Math.max(3, draft.split('\n').length))}
            />
            <div className="edit-actions">
              <button onClick={save} disabled={saving}>
                {saving ? '保存中…' : '保存'}
              </button>
              <button
                onClick={() => {
                  setDraft(message.content);
                  setEditing(false);
                }}
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          <div className={`bubble ${message.role}`}>
            {isAssistant ? (
              message.content ? (
                <MessageBody content={message.content} />
              ) : (
                <span className="typing">
                  <i />
                  <i />
                  <i />
                </span>
              )
            ) : (
              message.content
            )}
          </div>
        )}

        {!editing && !streaming && isAssistant && variantTotal > 1 && (
          <div className="swipe-bar">
            <button
              type="button"
              disabled={variantIndex <= 0}
              onClick={() => onSwipe(message.id, -1)}
              aria-label="上一个版本"
            >
              ‹
            </button>
            <span>
              {variantIndex + 1} / {variantTotal}
            </span>
            <button
              type="button"
              disabled={variantIndex >= variantTotal - 1}
              onClick={() => onSwipe(message.id, 1)}
              aria-label="下一个版本"
            >
              ›
            </button>
          </div>
        )}

        {!editing && !streaming && (
          <div className="msg-actions">
            {isAssistant && isLast && (
              <button onClick={onRegenerate}>重新生成</button>
            )}
            {isAssistant && onIllustrate && (
              <button onClick={onIllustrate}>配图</button>
            )}
            <button onClick={() => onCopy(message.content)}>复制</button>
            <button
              onClick={() => {
                setDraft(message.content);
                setEditing(true);
              }}
            >
              编辑
            </button>
            <button onClick={() => onDelete(message.id)}>删除</button>
          </div>
        )}
      </div>
    </div>
  );
}
