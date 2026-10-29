import { useEffect, useRef, useState } from 'react';
import AdminPanel from './AdminPanel';
import CharacterEditor from './CharacterEditor';
import CharacterPanel from './CharacterPanel';
import Gallery from './Gallery';
import HtmlFrame from './HtmlFrame';
import ImagePanel from './ImagePanel';
import Login from './Login';
import Message from './Message';
import SettingsPanel from './SettingsPanel';
import { api, authHeaders, clearToken, getToken } from './api';

const DEFAULT_MODEL = 'deepseek-chat';

function stripWrappers(text) {
  return text
    .replace(/<(BGM|MP4|事件触发)[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/^\s*（补充说明）.*$/gm, '')
    .replace(/^\s*-{3,}\s*$/gm, '')
    .replace(/```[a-zA-Z]*/g, '')
    .replace(/<\/?(?:infoblock|gametxt|thinking)>/gi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function proseOnly(text) {
  return text
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => /[一-龥]{2,}/.test(line) && !/[{}]/.test(line))
    .join('\n')
    .trim();
}

function outsideText(content) {
  if (!content) return '';
  const lower = content.toLowerCase();
  const starts = [lower.indexOf('<!doctype'), lower.indexOf('<html')].filter(
    (index) => index >= 0
  );
  if (!starts.length) return '';
  const start = Math.min(...starts);
  const end = lower.lastIndexOf('</html>');
  if (end <= start) return '';
  return proseOnly(
    stripWrappers(`${content.slice(0, start)}\n${content.slice(end + 7)}`)
  );
}

function buildStageDocument(content) {
  if (!content) return '';
  const lower = content.toLowerCase();
  const starts = [lower.indexOf('<!doctype'), lower.indexOf('<html')].filter(
    (index) => index >= 0
  );
  if (!starts.length) return stripWrappers(content);
  const start = Math.min(...starts);
  const end = lower.lastIndexOf('</html>');
  if (end <= start) return stripWrappers(content.slice(start));
  return content.slice(start, end + 7);
}

function usableStageHtml(content) {
  if (!content || content.length < 400) return null;
  const doc = buildStageDocument(content);
  if (!/<html|<!doctype/i.test(doc)) return null;
  const text = `${doc} ${outsideText(content)}`
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, '')
    .replace(/&[a-z]+;/gi, ' ')
    .replace(/\s+/g, '');
  return text.length > 120 ? doc : null;
}

function extractHtmlDocument(content) {
  if (!content) return '';
  const lower = content.toLowerCase();
  const candidates = [lower.indexOf('<!doctype'), lower.indexOf('<html')].filter(
    (index) => index >= 0
  );
  if (!candidates.length) return content;
  const start = Math.min(...candidates);
  const end = lower.lastIndexOf('</html>');
  if (end > start) return content.slice(start, end + 7);
  return content.slice(start);
}

function hueOf(character) {
  const text = `${character?.id || ''}${character?.name || ''}`;
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) % 360;
  }
  return hash;
}

function Avatar({ character, index = 0, small = false, big = false }) {
  const cls = `avatar${small ? ' small' : ''}${big ? ' big' : ''}`;
  if (character?.avatar_url) {
    return (
      <span className={`${cls} with-img`} style={{ '--hue': hueOf(character) }}>
        <img src={character.avatar_url} alt="" />
      </span>
    );
  }
  return (
    <span
      className={`${cls} hue-${index % 4}`}
      style={{ '--hue': hueOf(character) }}
    >
      {character?.name.slice(0, 1)}
    </span>
  );
}

function formatTime(value) {
  if (!value) return '';
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  return date.toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  });
}

export default function App() {
  const [user, setUser] = useState(null);
  const [firstRun, setFirstRun] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [characters, setCharacters] = useState([]);
  const [models, setModels] = useState([]);
  const [activeCharacter, setActiveCharacter] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [memory, setMemory] = useState(null);
  const [editingCharacter, setEditingCharacter] = useState(null);
  const [search, setSearch] = useState('');
  const [toast, setToast] = useState('');
  const [profile, setProfile] = useState({
    name: '',
    persona: '',
    theme: 'default',
    background_url: '',
  });
  const [view, setView] = useState('gallery');
  const [leftTab, setLeftTab] = useState('chats');
  const [adminOpen, setAdminOpen] = useState(false);
  const [panelVersion, setPanelVersion] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sentNote, setSentNote] = useState('');
  const [exportOpen, setExportOpen] = useState(false);
  const [greetingIndex, setGreetingIndex] = useState(0);
  const [editingFactId, setEditingFactId] = useState(null);
  const [factDraft, setFactDraft] = useState('');
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [imageOpen, setImageOpen] = useState(false);
  const [nearBottom, setNearBottom] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const bottomRef = useRef(null);
  const messagesRef = useRef(null);
  const inputRef = useRef(null);
  const abortRef = useRef(null);
  const toastTimer = useRef(null);
  const sentTimer = useRef(null);
  const activeConvIdRef = useRef(null);
  const bridgeConvRef = useRef(null);
  const fileInputRef = useRef(null);

  async function loadData() {
    const [chars, mods, prof] = await Promise.all([
      api('/api/characters'),
      api('/api/models'),
      api('/api/profile'),
    ]);
    setCharacters(chars);
    setModels(mods);
    setProfile(prof);
    setView('gallery');
  }

  function handleAuthFailure(e) {
    if (e?.status === 401) {
      clearToken();
      setUser(null);
      return true;
    }
    return false;
  }

  useEffect(() => {
    (async () => {
      try {
        const status = await api('/api/auth/status');
        setFirstRun(!!status.first_run);
      } catch {
        /* 状态接口失败不阻塞登录页 */
      }

      if (!getToken()) {
        setAuthReady(true);
        return;
      }

      try {
        const me = await api('/api/auth/me');
        setUser(me);
        await loadData();
      } catch {
        clearToken();
      }
      setAuthReady(true);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!nearBottom) return;
    bottomRef.current?.scrollIntoView({
      behavior: streaming ? 'auto' : 'smooth',
    });
  }, [messages, streaming, nearBottom]);

  function onMessagesScroll() {
    const el = messagesRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setNearBottom(distance < 140);
  }

  function scrollToBottom() {
    setNearBottom(true);
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  function showToast(text) {
    setToast(text);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(''), 1600);
  }

  async function selectCharacter(character) {
    setActiveCharacter(character);
    setActiveConversation(null);
    activeConvIdRef.current = null;
    bridgeConvRef.current = null;
    setMessages([]);
    setModel(character.default_model || DEFAULT_MODEL);
    setView('chat');
    setLeftTab('editor');
    setSidebarOpen(false);
    setMemoryOpen(false);
    setMemory(null);
    setImageOpen(false);
    setSearch('');
    setGreetingIndex(0);
    setNearBottom(true);
    setLoadingMessages(true);
    try {
      const list = await api(`/api/conversations?character_id=${character.id}`);
      setConversations(list);
      if (list.length) {
        await openConversation(list[0]);
      } else {
        setLoadingMessages(false);
      }
    } catch (e) {
      setError(e.message);
      setLoadingMessages(false);
    }
  }

  async function openConversation(conversation) {
    setActiveConversation(conversation);
    activeConvIdRef.current = conversation.id;
    bridgeConvRef.current = conversation;
    setModel(conversation.model || DEFAULT_MODEL);
    setSidebarOpen(false);
    setMemoryOpen(false);
    setMemory(null);
    setImageOpen(false);
    setNearBottom(true);
    setLoadingMessages(true);
    try {
      const msgs = await api(`/api/conversations/${conversation.id}/messages`);
      setMessages(msgs);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingMessages(false);
    }
  }

  function startNewConversation() {
    setActiveConversation(null);
    activeConvIdRef.current = null;
    bridgeConvRef.current = null;
    setMessages([]);
    setInput('');
    setSidebarOpen(false);
    setMemoryOpen(false);
    setMemory(null);
    setImageOpen(false);
    inputRef.current?.focus();
  }

  async function refreshConversations(characterId = activeCharacter?.id) {
    if (!characterId) return;
    try {
      setConversations(
        await api(`/api/conversations?character_id=${characterId}`)
      );
    } catch {
      /* ignore */
    }
  }

  async function ensureConversation() {
    if (activeConversation) return activeConversation;
    const conv = await api('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({
        character_id: activeCharacter.id,
        model,
        greeting_index: greetingIndex,
      }),
    });
    setConversations((prev) => [conv, ...prev]);
    setActiveConversation(conv);
    activeConvIdRef.current = conv.id;
    const msgs = await api(`/api/conversations/${conv.id}/messages`);
    setMessages(msgs);
    return conv;
  }

  async function streamReply(url, body, assistantId) {
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);
    setError('');

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (res.status === 401) {
        clearToken();
        setUser(null);
        return;
      }
      if (!res.ok) throw new Error(await res.text());

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finished = false;

      while (!finished) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          const line = event.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;
          let data;
          try {
            data = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (data.type === 'delta') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + data.content }
                  : m
              )
            );
          } else if (data.type === 'error') {
            setError(data.message || '模型调用失败');
          } else if (data.type === 'done') {
            finished = true;
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message);
    } finally {
      abortRef.current = null;
      setStreaming(false);
      const conversationId = body.conversation_id;
      if (conversationId && activeConvIdRef.current === conversationId) {
        api(`/api/conversations/${conversationId}/messages`)
          .then((list) => {
            setMessages(list);
            const last = list[list.length - 1];
            if (
              activeCharacter?.html_greeting &&
              last?.role === 'assistant' &&
              !usableStageHtml(last.content)
            ) {
              setHistoryOpen(true);
            }
          })
          .catch(() => {});
      }
      refreshConversations();
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || streaming || !activeCharacter) return;

    setError('');
    setInput('');
    setSentNote(text);
    clearTimeout(sentTimer.current);
    sentTimer.current = setTimeout(() => setSentNote(''), 6000);

    let conv = activeConversation;
    try {
      if (!conv) conv = await ensureConversation();
    } catch (e) {
      setError(e.message);
      setInput(text);
      return;
    }

    const stamp = Date.now();
    const assistantId = `a-${stamp}`;
    setMessages((prev) => [
      ...prev,
      { id: `u-${stamp}`, role: 'user', content: text },
      { id: assistantId, role: 'assistant', content: '' },
    ]);

    await streamReply(
      '/api/chat',
      { conversation_id: conv.id, content: text, model },
      assistantId
    );
  }

  async function regenerate() {
    if (!activeConversation || streaming) return;
    const last = messages[messages.length - 1];
    if (!last || last.role !== 'assistant') return;
    setMessages((prev) =>
      prev.map((m) => (m.id === last.id ? { ...m, content: '' } : m))
    );
    await streamReply(
      '/api/chat/regenerate',
      { conversation_id: activeConversation.id, model },
      last.id
    );
  }

  async function swipeMessage(id, delta) {
    if (streaming) return;
    const current = messages.find((m) => m.id === id);
    if (!current) return;
    const total = (current.variants || []).length;
    const next = (current.active_variant ?? 0) + delta;
    if (next < 0 || next >= total) return;
    try {
      const updated = await api(`/api/messages/${id}/swipe`, {
        method: 'POST',
        body: JSON.stringify({ index: next }),
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id
            ? {
                ...m,
                content: updated.content,
                variants: updated.variants,
                active_variant: updated.active_variant,
              }
            : m
        )
      );
    } catch (e) {
      setError(e.message);
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
  }

  async function copyMessage(content) {
    try {
      await navigator.clipboard.writeText(content);
      showToast('已复制');
    } catch {
      setError('复制失败，请手动选择文本');
    }
  }

  async function editMessage(id, content) {
    const updated = await api(`/api/messages/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    });
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? {
              ...m,
              content: updated.content,
              variants: updated.variants,
              active_variant: updated.active_variant,
            }
          : m
      )
    );
    refreshConversations();
    showToast('已保存');
  }

  async function deleteMessage(id) {
    if (!window.confirm('删除这条消息？')) return;
    try {
      await api(`/api/messages/${id}`, { method: 'DELETE' });
      setMessages((prev) => prev.filter((m) => m.id !== id));
      refreshConversations();
      showToast('已删除');
    } catch (e) {
      setError(e.message);
    }
  }

  async function toggleFavorite(character) {
    try {
      const updated = await api(`/api/characters/${character.id}/favorite`, {
        method: 'POST',
        body: JSON.stringify({ favorite: !character.favorite }),
      });
      setCharacters((prev) => {
        const next = prev.map((c) => (c.id === updated.id ? updated : c));
        return [...next].sort(
          (a, b) => Number(b.favorite) - Number(a.favorite) || a.id - b.id
        );
      });
      if (activeCharacter?.id === updated.id) setActiveCharacter(updated);
      showToast(updated.favorite ? '已收藏' : '已取消收藏');
    } catch (e) {
      setError(e.message);
    }
  }

  async function saveCharacter(id, data) {
    const updated = id
      ? await api(`/api/characters/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(data),
        })
      : await api('/api/characters', {
          method: 'POST',
          body: JSON.stringify(data),
        });
    setCharacters((prev) =>
      id
        ? prev.map((c) => (c.id === updated.id ? updated : c))
        : [...prev, updated]
    );
    if (activeCharacter?.id === updated.id) setActiveCharacter(updated);
    showToast(id ? '角色已保存' : '角色已创建');
    return updated;
  }

  function canManageCharacter(character) {
    return (
      Boolean(user?.is_admin) ||
      (character?.created_by != null && character.created_by === user?.id)
    );
  }

  async function applyCharacter(data) {
    let character = activeCharacter;
    if (!character) return;
    if (canManageCharacter(character)) {
      character = await saveCharacter(character.id, data);
    }
    const conversation = await api('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({
        character_id: character.id,
        model,
        greeting_index: 0,
      }),
    });
    setConversations((prev) => [conversation, ...prev]);
    await openConversation(conversation);
    setLeftTab('chats');
    showToast('已开始新对话');
  }

  async function adaptCharacter() {
    if (!activeCharacter) return null;
    const updated = await api(
      `/api/characters/${activeCharacter.id}/adapt`,
      { method: 'POST' }
    );
    setCharacters((prev) =>
      prev.map((c) => (c.id === updated.id ? updated : c))
    );
    setActiveCharacter(updated);
    setPanelVersion((value) => value + 1);
    showToast('AI 适配完成，检查一下人设和开场白');
    return updated;
  }

  async function ensureBridgeConversation() {
    if (bridgeConvRef.current) return bridgeConvRef.current;
    if (activeConversation) {
      bridgeConvRef.current = activeConversation;
      return activeConversation;
    }
    if (!activeCharacter) return null;
    const conversation = await api('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({
        character_id: activeCharacter.id,
        skip_greeting: true,
      }),
    });
    setConversations((prev) => [conversation, ...prev]);
    setActiveConversation(conversation);
    activeConvIdRef.current = conversation.id;
    bridgeConvRef.current = conversation;
    return conversation;
  }

  function toTavernMessage(message, index) {
    return {
      message: message.content,
      name: message.role === 'user' ? 'User' : activeCharacter?.name || '',
      role: message.role,
      is_user: message.role === 'user',
      is_system: message.role === 'system',
      message_id: index,
      data: {},
      id: message.id,
    };
  }

  async function handleCardBridge(method, args) {
    if (method === 'generate' || method === 'generateRaw') {
      const config = args[0];
      let prompt = '';
      if (typeof config === 'string') {
        prompt = config;
      } else if (config && Array.isArray(config.injects)) {
        prompt = config.injects
          .map((item) => item?.content || '')
          .filter(Boolean)
          .join('\n\n');
      } else if (config && typeof config.prompt === 'string') {
        prompt = config.prompt;
      }
      if (!prompt.trim()) throw new Error('没有可用的生成提示');
      const result = await api('/api/cards/generate', {
        method: 'POST',
        body: JSON.stringify({
          prompt,
          conversation_id: bridgeConvRef.current?.id ?? null,
          character_id: activeCharacter?.id ?? null,
        }),
      });
      return result.text;
    }

    if (method === 'getChatMessages') {
      const conversation = await ensureBridgeConversation();
      if (!conversation) return [];
      const list = await api(
        `/api/conversations/${conversation.id}/messages`
      );
      if (activeConvIdRef.current === conversation.id) setMessages(list);
      if (!list.length) {
        return [toTavernMessage({ id: 0, role: 'assistant', content: '' }, 0)];
      }
      return list.map(toTavernMessage);
    }

    if (method === 'setChatMessages') {
      const list = args[0] || [];
      const conversation = await ensureBridgeConversation();
      if (!conversation || !list.length) return true;
      const current = await api(
        `/api/conversations/${conversation.id}/messages`
      );
      const content = String(list[0]?.message || '');
      if (current.length) {
        await api(`/api/messages/${current[0].id}`, {
          method: 'PATCH',
          body: JSON.stringify({ content }),
        });
      } else if (content.trim()) {
        await api(`/api/conversations/${conversation.id}/messages`, {
          method: 'POST',
          body: JSON.stringify({ role: 'assistant', content }),
        });
      }
      const fresh = await api(
        `/api/conversations/${conversation.id}/messages`
      );
      if (activeConvIdRef.current === conversation.id) setMessages(fresh);
      refreshConversations();
      return true;
    }

    if (method === 'getVariables') {
      if (!bridgeConvRef.current) return {};
      const rows = await api(
        `/api/conversations/${bridgeConvRef.current.id}/variables`
      );
      return Object.fromEntries(rows.map((row) => [row.key, row.value]));
    }

    if (method === 'setVariables') return true;
    if (method === 'getLorebookEntries') return [];
    if (method === 'setLorebookEntries') return true;

    throw new Error(`不支持的方法：${method}`);
  }

  async function deleteCharacter(character) {
    if (
      !window.confirm(
        `删除角色「${character.name}」？所有人与它的对话也会一起删除，且无法恢复。`
      )
    ) {
      return;
    }
    try {
      await api(`/api/characters/${character.id}`, { method: 'DELETE' });
      setCharacters((prev) => prev.filter((c) => c.id !== character.id));
      if (activeCharacter?.id === character.id) {
        setActiveCharacter(null);
        setActiveConversation(null);
        setMessages([]);
        setConversations([]);
        setView('gallery');
      }
      showToast('角色已删除');
    } catch (e) {
      setError(e.message);
    }
  }

  function logout() {
    clearToken();
    setUser(null);
    setActiveCharacter(null);
    setActiveConversation(null);
    setMessages([]);
    setConversations([]);
    setView('gallery');
  }

  function backToGallery() {
    setView('gallery');
    setSidebarOpen(false);
  }

  async function importCard(file) {
    if (!file) return;
    setError('');
    try {
      const isPng =
        file.type === 'image/png' || /\.png$/i.test(file.name || '');
      let created;

      if (isPng) {
        const res = await fetch('/api/characters/import-png', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'image/png' }),
          body: file,
        });
        if (!res.ok) {
          let message = `导入失败 (${res.status})`;
          try {
            message = (await res.json()).detail || message;
          } catch {
            /* keep default */
          }
          throw new Error(message);
        }
        created = await res.json();
      } else {
        const text = await file.text();
        const card = JSON.parse(text);
        created = await api('/api/characters/import', {
          method: 'POST',
          body: JSON.stringify(card),
        });
      }

      setCharacters((prev) => [...prev, created]);
      const meta = created.import_meta || {};
      let message = `已导入「${created.name}」`;
      if (meta.world_entries) message += ` · ${meta.world_entries} 条世界书`;
      if (created.html_greeting) message += ' · 已保留原版前端界面';
      showToast(message);
    } catch (e) {
      setError(e.message || '导入失败，请检查角色卡格式');
    }
  }

  async function exportCard(character) {
    try {
      const card = await api(`/api/characters/${character.id}/export`);
      const blob = new Blob([JSON.stringify(card, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${character.name}.json`;
      link.click();
      URL.revokeObjectURL(url);
      showToast('角色卡已导出');
    } catch (e) {
      setError(e.message);
    }
  }

  async function exportConversation(format) {
    setExportOpen(false);
    if (!activeConversation) return;
    try {
      const res = await fetch(
        `/api/conversations/${activeConversation.id}/export?format=${format}`,
        { headers: authHeaders() }
      );
      if (!res.ok) throw new Error('导出失败');

      let body = await res.text();
      if (format === 'json') {
        body = JSON.stringify(JSON.parse(body), null, 2);
      }

      const safe = (text) => (text || '').replace(/[\\/:*?"<>|]/g, '_');
      const name = `${safe(activeCharacter?.name || '角色')}_${safe(
        activeConversation.title
      )}.${format === 'json' ? 'json' : 'md'}`;

      const blob = new Blob([body], {
        type: format === 'json' ? 'application/json' : 'text/markdown',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = name;
      link.click();
      URL.revokeObjectURL(url);
      showToast('已导出');
    } catch (e) {
      setError(e.message);
    }
  }

  async function openMemory() {
    if (!activeConversation) return;
    setMemoryOpen(true);
    setMemory(null);
    setEditingFactId(null);
    try {
      const data = await api(
        `/api/conversations/${activeConversation.id}/memory`
      );
      setMemory(data);
    } catch (e) {
      setError(e.message);
    }
  }

  async function saveProfile(data) {
    const updated = await api('/api/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    setProfile(updated);
    showToast('设置已保存');
  }

  async function refreshMemory() {
    if (!activeConversation || memoryBusy) return;
    setMemoryBusy(true);
    try {
      const data = await api(
        `/api/conversations/${activeConversation.id}/memory/refresh`,
        { method: 'POST' }
      );
      setMemory(data);
      showToast('记忆已整理');
    } catch (e) {
      setError(e.message);
    } finally {
      setMemoryBusy(false);
    }
  }

  async function saveFact(factId) {
    const content = factDraft.trim();
    if (!content) return;
    try {
      const updated = await api(`/api/memories/${factId}`, {
        method: 'PATCH',
        body: JSON.stringify({ content }),
      });
      setMemory((prev) => ({
        ...prev,
        facts: prev.facts.map((f) => (f.id === factId ? updated : f)),
      }));
      setEditingFactId(null);
      showToast('记忆已保存');
    } catch (e) {
      setError(e.message);
    }
  }

  async function deleteFact(factId) {
    if (!window.confirm('删除这条记忆？')) return;
    try {
      await api(`/api/memories/${factId}`, { method: 'DELETE' });
      setMemory((prev) => ({
        ...prev,
        facts: prev.facts.filter((f) => f.id !== factId),
      }));
      showToast('记忆已删除');
    } catch (e) {
      setError(e.message);
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  }

  const activeIndex = characters.findIndex(
    (c) => c.id === activeCharacter?.id
  );
  const hue = Math.max(activeIndex, 0) % 4;
  const greetings = activeCharacter
    ? [activeCharacter.greeting, ...(activeCharacter.alternates || [])]
    : [];
  const currentGreeting =
    greetings[greetingIndex] || activeCharacter?.greeting || '';
  const keyword = search.trim().toLowerCase();
  const visibleConversations = keyword
    ? conversations.filter((c) =>
        `${c.title} ${c.last_message || ''}`.toLowerCase().includes(keyword)
      )
    : conversations;

  const frontendCard = Boolean(activeCharacter?.html_greeting);
  let stageMessage = null;
  let stageHtml = frontendCard ? activeCharacter?.html_greeting || '' : '';
  if (frontendCard) {
    for (const message of [...messages].reverse()) {
      if (message.role !== 'assistant') continue;
      const doc = usableStageHtml(message.content);
      if (doc) {
        stageMessage = message;
        stageHtml = doc;
        break;
      }
    }
  }
  const visibleMessages = stageMessage
    ? messages.filter((m) => m.id !== stageMessage.id)
    : messages;
  const stageStory = stageMessage ? outsideText(stageMessage.content) : '';

  if (!authReady) {
    return <div className="login-page" />;
  }

  if (!user) {
    return (
      <Login
        firstRun={firstRun}
        onLogin={(account) => {
          setUser(account);
          loadData().catch((e) => setError(e.message));
        }}
      />
    );
  }

  if (view === 'gallery') {
    return (
      <div className={`app theme-${profile.theme || 'default'}`}>
        <Gallery
          characters={characters}
          user={user}
          onStart={selectCharacter}
          onFavorite={toggleFavorite}
          onEdit={(character) => setEditingCharacter(character)}
          onExport={exportCard}
          onDelete={deleteCharacter}
          onImport={importCard}
          onCreate={() => setEditingCharacter('new')}
          onOpenInvites={() => setAdminOpen(true)}
          onLogout={logout}
        />

        {error && (
          <div className="error-bar gallery-error">
            <span>{error}</span>
            <button onClick={() => setError('')}>关闭</button>
          </div>
        )}

        {editingCharacter && (
          <CharacterEditor
            character={editingCharacter === 'new' ? null : editingCharacter}
            onClose={() => setEditingCharacter(null)}
            onSave={saveCharacter}
          />
        )}

        {adminOpen && <AdminPanel onClose={() => setAdminOpen(false)} />}
        {toast && <div className="toast">{toast}</div>}
      </div>
    );
  }

  return (
    <div className={`app theme-${profile.theme || 'default'}`}>
      {sidebarOpen && (
        <div className="scrim" onClick={() => setSidebarOpen(false)} />
      )}

      <aside className={`sidebar panel-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="panel-head">
          <button className="ghost-btn back-gallery" onClick={backToGallery}>
            ← 画廊
          </button>
          <div className="panel-tabs">
            <button
              className={leftTab === 'chats' ? 'active' : ''}
              onClick={() => setLeftTab('chats')}
            >
              会话
            </button>
            <button
              className={leftTab === 'editor' ? 'active' : ''}
              onClick={() => setLeftTab('editor')}
            >
              编辑
            </button>
            <button
              className={leftTab === 'settings' ? 'active' : ''}
              onClick={() => setLeftTab('settings')}
            >
              设置
            </button>
          </div>
        </div>

        <div className="panel-content">
          {leftTab === 'chats' && (
            <>
              <div className="sidebar-label label-row">
                <span>会话 · {activeCharacter?.name || '未选角色'}</span>
                <button className="link-btn" onClick={startNewConversation}>
                  新建
                </button>
              </div>
              <input
                className="search-input"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索会话…"
              />
              <div className="conv-list">
                {visibleConversations.map((conv) => (
                  <button
                    key={conv.id}
                    className={`conv ${
                      activeConversation?.id === conv.id ? 'active' : ''
                    }`}
                    onClick={() => openConversation(conv)}
                  >
                    <span className="conv-top">
                      <span className="conv-title">{conv.title}</span>
                      <small>{formatTime(conv.updated_at)}</small>
                    </span>
                    <span className="conv-preview">
                      {conv.last_message || '还没有消息'}
                    </span>
                  </button>
                ))}
                {!visibleConversations.length && (
                  <p className="empty-hint">
                    {conversations.length ? '没有匹配的会话' : '还没有会话'}
                  </p>
                )}
              </div>
            </>
          )}

          {leftTab === 'editor' && (
            <CharacterPanel
              key={`${activeCharacter?.id}-${panelVersion}`}
              character={activeCharacter}
              conversation={activeConversation}
              canManage={canManageCharacter(activeCharacter)}
              onSave={(data) => saveCharacter(activeCharacter.id, data)}
              onApply={applyCharacter}
              onAdapt={adaptCharacter}
            />
          )}

          {leftTab === 'settings' && (
            <SettingsPanel embedded profile={profile} onSave={saveProfile} />
          )}
        </div>

        <div className="panel-footer">
          {user?.is_admin && (
            <button className="settings-btn" onClick={() => setAdminOpen(true)}>
              邀请码
            </button>
          )}
          <button className="settings-btn" onClick={logout}>
            {user.username} · 退出
          </button>
        </div>
      </aside>

      <main
        className={`chat-pane ${frontendCard ? 'card-stage' : ''}`}
        style={{
          '--hue': hueOf(activeCharacter),
          ...(profile.background_url
            ? {
                backgroundImage: `linear-gradient(rgba(8, 9, 13, 0.82), rgba(8, 9, 13, 0.92)), url(${profile.background_url})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
              }
            : {}),
        }}
      >
        {frontendCard && (
          <div className="card-stage-bg">
            <HtmlFrame
              html={stageHtml}
              label="卡片界面"
              onRequest={handleCardBridge}
              bare
            />
          </div>
        )}
        {frontendCard && stageStory && (
          <div className="card-story">
            <div className="card-story-inner">{stageStory}</div>
          </div>
        )}
        <header className="chat-header">
          <button
            className="menu-btn"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="菜单"
          >
            <span />
            <span />
            <span />
          </button>
          <button
            className="chat-title"
            onClick={() => {
              if (!activeCharacter) return;
              setLeftTab('editor');
              setSidebarOpen(true);
            }}
            title="打开角色编辑"
          >
            {activeCharacter && (
              <Avatar character={activeCharacter} index={activeIndex} small />
            )}
            <div>
              <strong>{activeCharacter?.name || '选择角色'}</strong>
              <small>{activeCharacter?.tagline || '从左侧挑一个开始'}</small>
            </div>
          </button>
          <div className="header-actions">
            {activeConversation && (
              <button
                className="memory-btn"
                onClick={() => setImageOpen(true)}
              >
                生图
              </button>
            )}
            {activeConversation && (
              <button className="memory-btn" onClick={openMemory}>
                记忆
              </button>
            )}
            {activeConversation && (
              <div className="export-wrap">
                <button
                  className="memory-btn"
                  onClick={() => setExportOpen((open) => !open)}
                >
                  导出
                </button>
                {exportOpen && (
                  <div className="export-menu">
                    <button onClick={() => exportConversation('md')}>
                      Markdown
                    </button>
                    <button onClick={() => exportConversation('json')}>
                      JSON
                    </button>
                  </div>
                )}
              </div>
            )}
            <select
              className="model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={streaming}
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </header>

        <div
          className={`messages ${
            frontendCard && !historyOpen ? 'messages-hidden' : ''
          }`}
          ref={messagesRef}
          onScroll={onMessagesScroll}
          aria-live="polite"
        >
          {loadingMessages && (
            <div className="messages-loading">载入对话…</div>
          )}

          {!loadingMessages && !messages.length && activeCharacter && !frontendCard && (
            <div className="empty-chat">
              <Avatar character={activeCharacter} index={activeIndex} big />
              <h2>{activeCharacter.name}</h2>
              <p>{activeCharacter.tagline}</p>
              <p className="greeting">{currentGreeting}</p>
              {activeCharacter.html_greeting && (
                <div className="greeting-html">
                  <p className="hint">
                    这张卡自带前端界面，当前是只读预览（交互要等 B2）
                  </p>
                  <HtmlFrame
                    html={activeCharacter.html_greeting}
                    label="开场界面"
                    onRequest={handleCardBridge}
                  />
                </div>
              )}
              {greetings.length > 1 && (
                <button
                  className="ghost-btn greeting-switch"
                  onClick={() =>
                    setGreetingIndex((greetingIndex + 1) % greetings.length)
                  }
                >
                  换一个开场（{greetingIndex + 1}/{greetings.length}）
                </button>
              )}
              <p className="hint">发一条消息开始对话</p>
            </div>
          )}

          {visibleMessages.map((m, index) => (
            <Message
              key={m.id}
              message={m}
              character={activeCharacter}
              hue={hue}
              isLast={index === visibleMessages.length - 1}
              streaming={streaming}
              onRegenerate={regenerate}
              onSwipe={swipeMessage}
              onCopy={copyMessage}
              onEdit={editMessage}
              onDelete={deleteMessage}
              onIllustrate={() => setImageOpen(true)}
              onCardRequest={handleCardBridge}
            />
          ))}
          <div ref={bottomRef} />
        </div>

        {!nearBottom && !loadingMessages && (
          <button className="scroll-bottom" onClick={scrollToBottom}>
            回到最新
          </button>
        )}

        {error && (
          <div className="error-bar">
            <span>{error}</span>
            <button onClick={() => setError('')}>关闭</button>
          </div>
        )}

        {frontendCard && sentNote && (
          <div className="sent-preview">
            <span>我：</span>
            {sentNote}
          </div>
        )}
        {frontendCard && streaming && (
          <div className="card-loading">正在生成卡片回复…</div>
        )}

        <footer className="composer">
          <div className="composer-row">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={
                activeCharacter
                  ? `和${activeCharacter.name}说点什么…`
                  : '先选择一个角色'
              }
              rows={1}
              maxLength={4000}
              disabled={!activeCharacter}
            />
            {streaming ? (
              <button className="stop-btn" onClick={stopStreaming}>
                停止
              </button>
            ) : (
              <button onClick={send} disabled={!input.trim() || !activeCharacter}>
                发送
              </button>
            )}
          </div>
          <div className="composer-meta">
            {frontendCard && (
              <button
                className="history-toggle"
                onClick={() => setHistoryOpen((value) => !value)}
                type="button"
              >
                {historyOpen ? '收起历史' : '历史记录'}
              </button>
            )}
            <span>Enter 发送 · Shift+Enter 换行</span>
            <span>{input.length}/4000</span>
          </div>
        </footer>
      </main>

      {memoryOpen && (
        <div className="memory-overlay" onClick={() => setMemoryOpen(false)}>
          <div className="memory-panel" onClick={(e) => e.stopPropagation()}>
            <div className="memory-head">
              <strong>长期记忆</strong>
              <div className="memory-head-actions">
                <button onClick={refreshMemory} disabled={memoryBusy}>
                  {memoryBusy ? '整理中…' : '立即整理'}
                </button>
                <button onClick={() => setMemoryOpen(false)}>关闭</button>
              </div>
            </div>

            {memory?.updated_at && (
              <p className="memory-time">
                上次更新：{formatTime(memory.updated_at)}
              </p>
            )}

            {!memory && <p className="empty-hint">读取中…</p>}

            {memory && (
              <>
                <h4>剧情摘要</h4>
                <p className="memory-summary">
                  {memory.summary ||
                    '还没有形成摘要，多聊一会儿会自动生成。'}
                </p>
                <h4>已知事实</h4>
                {memory.facts.length ? (
                  <ul className="memory-facts">
                    {memory.facts.map((fact) => (
                      <li key={fact.id}>
                        {editingFactId === fact.id ? (
                          <span className="fact-edit">
                            <input
                              value={factDraft}
                              onChange={(e) => setFactDraft(e.target.value)}
                            />
                            <button onClick={() => saveFact(fact.id)}>
                              保存
                            </button>
                            <button onClick={() => setEditingFactId(null)}>
                              取消
                            </button>
                          </span>
                        ) : (
                          <span className="fact-row">
                            <span>{fact.content}</span>
                            <span className="fact-actions">
                              <button
                                onClick={() => {
                                  setEditingFactId(fact.id);
                                  setFactDraft(fact.content);
                                }}
                              >
                                编辑
                              </button>
                              <button onClick={() => deleteFact(fact.id)}>
                                删除
                              </button>
                            </span>
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-hint">还没有抽取到事实。</p>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {imageOpen && activeConversation && (
        <ImagePanel
          conversation={activeConversation}
          onClose={() => setImageOpen(false)}
        />
      )}

      {adminOpen && <AdminPanel onClose={() => setAdminOpen(false)} />}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
