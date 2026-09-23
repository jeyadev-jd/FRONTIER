import { useState, useEffect, useCallback, useRef, KeyboardEvent } from 'react'
import axios from 'axios'

const API = 'http://localhost:8000'

// LLM generation can take up to 3min on cold start
axios.defaults.timeout = 180_000

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg: '#0a0a0a', surface: '#141414', surface2: '#1a1a1a', border: '#222',
  border2: '#2a2a2a', text: '#e0e0e0', muted: '#888', dim: '#444', dimmer: '#333',
  green: '#00ff88', blue: '#4488ff', purple: '#aa88ff', orange: '#ffaa00',
  red: '#ff4444', yellow: '#ffdd44',
}

const s = {
  app: { minHeight: '100vh', background: C.bg, color: C.text, fontFamily: "'Segoe UI', system-ui, sans-serif", fontSize: 14 },
  header: { background: C.surface, borderBottom: `1px solid ${C.border}`, padding: '0 24px', display: 'flex', alignItems: 'center', gap: 20, height: 52, position: 'sticky' as const, top: 0, zIndex: 100 },
  logo: { fontSize: 18, fontWeight: 800, color: C.green, letterSpacing: 3, flexShrink: 0 },
  headerStatus: { display: 'flex', gap: 16, fontSize: 12, color: C.muted, alignItems: 'center', flex: 1 },
  headerRight: { display: 'flex', gap: 8, alignItems: 'center', marginLeft: 'auto' },
  dot: (ok: boolean | null) => ({ width: 7, height: 7, borderRadius: '50%', background: ok === null ? C.dimmer : ok ? C.green : C.red, display: 'inline-block', marginRight: 5, flexShrink: 0 }),
  main: { maxWidth: 1120, margin: '0 auto', padding: '0 16px 40px' },
  tabBar: { display: 'flex', borderBottom: `1px solid ${C.border}`, marginBottom: 24, overflowX: 'auto' as const, scrollbarWidth: 'none' as const, background: C.bg, position: 'sticky' as const, top: 52, zIndex: 90, paddingTop: 4 },
  tab: (a: boolean) => ({ padding: '10px 16px', cursor: 'pointer', fontSize: 12, fontWeight: a ? 700 : 400, color: a ? C.green : C.dim, borderBottom: a ? `2px solid ${C.green}` : '2px solid transparent', background: 'none', border: 'none', outline: 'none', whiteSpace: 'nowrap' as const, display: 'flex', alignItems: 'center', gap: 6, transition: 'color 0.1s' }),
  badge: (c: string, big = false) => ({ background: c + '25', color: c, padding: big ? '2px 8px' : '1px 6px', borderRadius: 3, fontSize: big ? 11 : 10, fontWeight: 700, lineHeight: 1.4 }),
  pill: (c: string) => ({ display: 'inline-block', background: c + '22', color: c, padding: '2px 8px', borderRadius: 10, fontSize: 11, marginRight: 4, marginBottom: 4 }),
  card: { background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16, marginBottom: 10 },
  cardHover: { background: C.surface, border: `1px solid ${C.border2}`, borderRadius: 10, padding: 16, marginBottom: 10 },
  channel: { fontSize: 11, background: C.green + '18', color: C.green, padding: '2px 8px', borderRadius: 4, fontFamily: 'monospace', fontWeight: 600 },
  content: (expanded: boolean) => ({ fontSize: 13, color: '#bbb', lineHeight: 1.65, whiteSpace: 'pre-wrap' as const, wordBreak: 'break-word' as const, maxHeight: expanded ? 'none' : 200, overflow: 'hidden' }),
  contentFade: { position: 'relative' as const },
  btnRow: { display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' as const, alignItems: 'center' },
  btn: (c: string, filled = false) => ({ background: filled ? c + '22' : 'none', border: `1px solid ${c}`, color: c, padding: '6px 14px', borderRadius: 5, cursor: 'pointer', fontSize: 12, fontWeight: 600, transition: 'background 0.1s', display: 'inline-flex', alignItems: 'center', gap: 5 }),
  btnSm: (c: string) => ({ background: 'none', border: `1px solid ${c}55`, color: c, padding: '3px 9px', borderRadius: 4, cursor: 'pointer', fontSize: 11, fontWeight: 500 }),
  btnIcon: (c: string) => ({ background: 'none', border: `1px solid ${c}44`, color: c, padding: '4px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 11, lineHeight: 1 }),
  textarea: { width: '100%', background: C.surface2, border: `1px solid ${C.border2}`, borderRadius: 6, color: C.text, padding: '10px 12px', fontSize: 13, resize: 'vertical' as const, outline: 'none', fontFamily: 'inherit', lineHeight: 1.6, boxSizing: 'border-box' as const },
  input: { width: '100%', background: C.surface2, border: `1px solid ${C.border2}`, borderRadius: 6, color: C.text, padding: '8px 12px', fontSize: 13, outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box' as const },
  select: { background: C.surface2, border: `1px solid ${C.border2}`, borderRadius: 6, color: C.text, padding: '7px 10px', fontSize: 12, outline: 'none', cursor: 'pointer' },
  label: { fontSize: 10, color: C.muted, marginBottom: 5, display: 'block', textTransform: 'uppercase' as const, letterSpacing: 0.8, fontWeight: 600 },
  row: { marginBottom: 14 },
  section: { fontSize: 10, fontWeight: 700, color: C.dim, textTransform: 'uppercase' as const, letterSpacing: 1.2, marginBottom: 14 },
  divider: { borderTop: `1px solid ${C.border}`, margin: '20px 0' },
  score: { fontSize: 12, color: C.muted },
  msg: (ok: boolean) => ({ fontSize: 13, marginBottom: 14, padding: '10px 14px', background: ok ? '#001a0d' : '#1a0000', borderRadius: 6, border: `1px solid ${ok ? '#004422' : '#440000'}`, color: ok ? C.green : '#ff8888', display: 'flex', alignItems: 'center', gap: 8 }),
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 },
  profileRow: { display: 'flex', gap: 12, padding: '7px 0', borderBottom: `1px solid ${C.border}`, alignItems: 'flex-start' },
  profileKey: { fontSize: 11, color: C.muted, width: 148, flexShrink: 0, paddingTop: 2 },
  profileVal: { fontSize: 13, color: '#ccc', flex: 1 },
  skeleton: { background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16, marginBottom: 10, opacity: 0.5 },
  emptyState: { color: C.dim, fontSize: 13, textAlign: 'center' as const, padding: '40px 0', letterSpacing: 0.3 },
  statCard: (c: string) => ({ background: C.surface, border: `1px solid ${c}33`, borderRadius: 10, padding: '14px 16px' }),
  barTrack: { height: 6, background: C.border2, borderRadius: 3, overflow: 'hidden', flex: 1, marginLeft: 10 },
  barFill: (c: string, pct: number) => ({ height: '100%', width: `${Math.min(pct * 100, 100)}%`, background: c, borderRadius: 3, transition: 'width 0.6s ease' }),
  kbd: { background: C.surface2, border: `1px solid ${C.border2}`, borderRadius: 3, padding: '1px 5px', fontSize: 10, color: C.muted, fontFamily: 'monospace' },
}

const CHANNELS = ['#neural','#forge','#lab','#arena','#bug-hunt','#missions','#launchpad','#signal','#frontier-lounge','#frontier-guide']
const CATEGORIES = ['AI','BUILD','RESEARCH','HACKATHON','PITCHING','DEBUGGING','OPPORTUNITY','GENERAL']
const DISCOVER_CATS = ['AI','BUILD','RESEARCH','HACKATHON','OPPORTUNITY','ALL']
const STYLE_CATS = ['general','ai','research','hackathons','announcements','build','debugging']
const CAT_COLORS: Record<string, string> = { AI: C.green, BUILD: C.blue, RESEARCH: C.purple, HACKATHON: C.orange, PITCHING: C.yellow, DEBUGGING: C.red, OPPORTUNITY: '#44ddff', GENERAL: C.muted }

type Tab = 'generate' | 'discover' | 'pending' | 'published' | 'style' | 'sources' | 'scheduler' | 'analytics'

interface Post { id: string; content: string; channel: string; category: string; source_url?: string; source_title?: string; status: string; created_at: string; model?: string; relevance?: number }
interface Health { status: string; llm: { healthy: boolean; provider: string; model?: string }; discord: { healthy: boolean } }
interface QueueItem { id: string; title: string; url: string; category: string; channel: string; relevance: number; credibility: number }
interface StyleEx { id: string; category: string; content_preview: string; source_label?: string; created_at: string }
interface StyleAttr { tone: string[]; sentence_length: string; technical_depth: string; humor_level: string; emoji_usage: string; formality: string; vocabulary?: { preferred?: string[]; avoided?: string[] }; structural_patterns?: string[]; things_to_avoid?: string[]; summary?: string }
interface StyleProfileData { exists: boolean; tone?: string; formality?: string; technical_depth?: string; emoji_usage?: string; example_count?: number; full_attributes?: StyleAttr; updated_at?: string }

// ─── Sub-components ───────────────────────────────────────────────────────────

function Skeleton({ lines = 3 }) {
  return (
    <div style={s.skeleton}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} style={{ height: 12, background: C.border2, borderRadius: 4, marginBottom: 8, width: i === lines - 1 ? '60%' : '100%' }} />
      ))}
    </div>
  )
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <button style={s.btnIcon(copied ? C.green : C.dim)} onClick={copy} title="Copy to clipboard">
      {copied ? '✓' : '⎘'}
    </button>
  )
}

interface PostCardProps {
  post: Post
  onPublish?: (id: string) => void
  onReject?: (id: string) => void
  onFeedback?: (id: string, fb: string) => void
  showSource?: boolean
}

function PostCard({ post, onPublish, onReject, onFeedback, showSource }: PostCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [fb, setFb] = useState('')
  const [showFb, setShowFb] = useState(false)
  const [regen, setRegen] = useState(false)
  const long = post.content.length > 220

  const catColor = CAT_COLORS[post.category] || C.muted

  return (
    <div style={{ ...s.cardHover, borderLeft: `3px solid ${catColor}44` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10, gap: 8 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={s.channel}>{post.channel}</span>
          {post.category && <span style={s.badge(catColor)}>{post.category}</span>}
          {post.relevance != null && <span style={{ fontSize: 10, color: C.dim }}>{(post.relevance * 100).toFixed(0)}%</span>}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          {post.model && <span style={{ fontSize: 10, color: C.dimmer }}>{post.model}</span>}
          <CopyBtn text={post.content} />
        </div>
      </div>

      <div style={s.contentFade}>
        <pre style={s.content(expanded)}>{post.content}</pre>
        {long && !expanded && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 40, background: `linear-gradient(transparent, ${C.surface})` }} />
        )}
      </div>

      {long && (
        <button style={{ ...s.btnSm(C.dim), marginTop: 4, marginBottom: 4 }} onClick={() => setExpanded(!expanded)}>
          {expanded ? '▲ collapse' : '▼ expand'}
        </button>
      )}

      {showSource && (post.source_title || post.source_url) && (
        <div style={{ fontSize: 11, color: C.dimmer, marginTop: 6, marginBottom: 2 }}>
          Source: {post.source_title && <span style={{ color: C.dim }}>{post.source_title.slice(0, 60)}</span>}
          {post.source_url && <a href={post.source_url} target="_blank" rel="noreferrer" style={{ color: C.blue + 'aa', marginLeft: 6, fontSize: 10 }}>↗ link</a>}
        </div>
      )}

      {(onPublish || onReject || onFeedback) && (
        <div style={s.btnRow}>
          {onPublish && <button style={s.btn(C.green, true)} onClick={() => onPublish(post.id)}>✓ Publish</button>}
          {onFeedback && (
            <button style={s.btn(C.blue)} onClick={() => setShowFb(!showFb)}>↻ Regen</button>
          )}
          {onReject && <button style={s.btn(C.red)} onClick={() => onReject(post.id)}>✕ Reject</button>}
        </div>
      )}

      {showFb && onFeedback && (
        <div style={{ marginTop: 10 }}>
          <input style={s.input} placeholder="Feedback: shorter, add emoji, change tone…" value={fb} onChange={e => setFb(e.target.value)}
            onKeyDown={async e => {
              if (e.key === 'Enter' && fb.trim() && !regen) {
                setRegen(true)
                await onFeedback(post.id, fb)
                setFb(''); setShowFb(false); setRegen(false)
              }
            }}
          />
          <div style={{ fontSize: 10, color: C.dimmer, marginTop: 4 }}>Press Enter to regenerate</div>
        </div>
      )}
    </div>
  )
}

// ─── Bar chart row ────────────────────────────────────────────────────────────
function BarRow({ label, val, max, color }: { label: string; val: number; max: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8, gap: 8 }}>
      <span style={{ fontSize: 11, color: C.muted, width: 110, flexShrink: 0, textAlign: 'right' }}>{label}</span>
      <div style={s.barTrack}>
        <div style={s.barFill(color, max > 0 ? val / max : 0)} />
      </div>
      <span style={{ fontSize: 12, color, fontWeight: 700, width: 28, textAlign: 'right' }}>{val}</span>
    </div>
  )
}

// ─── Main app ────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState<Tab>('generate')
  const [health, setHealth] = useState<Health | null>(null)
  const [loading, setLoading] = useState(false)

  // Generate
  const [topic, setTopic] = useState(''), [chan, setChan] = useState(''), [cat, setCat] = useState('GENERAL')
  const [generating, setGenerating] = useState(false), [generated, setGenerated] = useState<Post | null>(null)
  const [feedback, setFeedback] = useState('')
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const topicRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Lists
  const [pending, setPending] = useState<Post[] | null>(null)
  const [published, setPublished] = useState<Post[] | null>(null)
  const [queue, setQueue] = useState<QueueItem[] | null>(null)
  const [pendingCount, setPendingCount] = useState(0)

  // Discover
  const [discoverCat, setDiscoverCat] = useState('AI'), [discovering, setDiscovering] = useState(false)

  // Analytics
  const [analyticsData, setAnalyticsData] = useState<any>(null)
  const [activityData, setActivityData] = useState<any[]>([])
  const [topContent, setTopContent] = useState<any[]>([])
  const [analyticsDays, setAnalyticsDays] = useState(7)

  // Sources
  const [sources, setSources] = useState<any>(null)
  const [newSrc, setNewSrc] = useState({ name: '', source_type: 'RSS', url: '', query: '', category: 'AI' })

  // Channel sync
  const [channelSync, setChannelSync] = useState<any>(null)
  const [syncing, setSyncing] = useState(false)

  // Scheduler
  const [schedJobs, setSchedJobs] = useState<any>(null)
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null)
  const [apRules, setApRules] = useState<any[]>([])
  const [apSaving, setApSaving] = useState<number | null>(null)

  // Style
  const [profile, setProfile] = useState<StyleProfileData | null>(null)
  const [examples, setExamples] = useState<StyleEx[]>([])
  const [newExample, setNewExample] = useState(''), [exCat, setExCat] = useState('general'), [exLabel, setExLabel] = useState('')
  const [rebuilding, setRebuilding] = useState(false)
  const [selectedExIds, setSelectedExIds] = useState<Set<string>>(new Set())

  // UI
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const msgTimer = useRef<ReturnType<typeof setTimeout>>()

  const showMsg = (text: string, ok = true) => {
    clearTimeout(msgTimer.current)
    setMsg({ text, ok })
    msgTimer.current = setTimeout(() => setMsg(null), 5000)
  }

  // ─── Health poll ──────────────────────────────────────────────────────────
  useEffect(() => {
    const check = () => axios.get(`${API}/health`).then(r => setHealth(r.data)).catch(() => {})
    check()
    const iv = setInterval(check, 15000)
    return () => clearInterval(iv)
  }, [])

  // ─── Pending count badge ──────────────────────────────────────────────────
  useEffect(() => {
    const poll = () => axios.get(`${API}/posts/pending`).then(r => setPendingCount(r.data?.length ?? 0)).catch(() => {})
    poll()
    const iv = setInterval(poll, 30000)
    return () => clearInterval(iv)
  }, [])

  // ─── Tab loading ──────────────────────────────────────────────────────────
  const loadTab = useCallback(async (t: Tab) => {
    setLoading(true)
    try {
      if (t === 'pending') {
        const r = await axios.get(`${API}/queue?limit=50`)
        setPending(r.data)
        setPendingCount(r.data.length)
      }
      if (t === 'published') {
        const r = await axios.get(`${API}/posts/published?limit=50`)
        setPublished(r.data)
      }
      if (t === 'discover') {
        const r = await axios.get(`${API}/discovery/queue`)
        setQueue(r.data)
      }
      if (t === 'style') {
        const [p, e] = await Promise.all([
          axios.get(`${API}/style/profile`),
          axios.get(`${API}/style/examples`),
        ])
        setProfile(p.data); setExamples(e.data)
      }
      if (t === 'sources') {
        const r = await axios.get(`${API}/sources`)
        setSources(r.data)
      }
      if (t === 'scheduler') {
        const [sched, rules] = await Promise.all([
          axios.get(`${API}/scheduler`),
          axios.get(`${API}/autopublish/rules`),
        ])
        setSchedJobs(sched.data)
        setApRules(rules.data)
      }
      if (t === 'analytics') {
        const [a, act, top] = await Promise.all([
          axios.get(`${API}/analytics/summary?days=${analyticsDays}`),
          axios.get(`${API}/analytics/activity?days=14`),
          axios.get(`${API}/analytics/top-content?limit=8`),
        ])
        setAnalyticsData(a.data); setActivityData(act.data); setTopContent(top.data)
      }
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [analyticsDays])

  useEffect(() => { loadTab(tab) }, [tab, loadTab])

  // ─── Keyboard shortcut Ctrl+Enter to generate ─────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && tab === 'generate' && topic.trim() && !generating) {
        e.preventDefault()
        generate()
      }
    }
    window.addEventListener('keydown', handler as any)
    return () => window.removeEventListener('keydown', handler as any)
  }, [tab, topic, generating])

  // ─── Actions ──────────────────────────────────────────────────────────────
  const generate = async () => {
    if (!topic.trim()) return
    setGenerating(true); setGenerated(null)
    try {
      let r
      if (attachedFile) {
        const fd = new FormData()
        fd.append('topic', topic)
        fd.append('channel', chan || '')
        fd.append('category', cat)
        fd.append('file', attachedFile)
        r = await axios.post(`${API}/posts/generate-with-file`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      } else {
        r = await axios.post(`${API}/posts/generate`, { topic, channel: chan || null, category: cat })
      }
      setGenerated(r.data)
      setAttachedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (e: any) { showMsg('Generation failed: ' + (e.response?.data?.detail || e.message), false) }
    finally { setGenerating(false) }
  }

  const publishPost = async (postId: string) => {
    // Optimistic: remove from pending list immediately
    if (tab === 'pending') setPending(prev => prev ? prev.filter(p => p.id !== postId) : prev)
    if (tab === 'generate') { setGenerated(null); setTopic('') }
    try {
      await axios.post(`${API}/posts/${postId}/approve-and-publish`)
      showMsg('Published to Discord!')
    } catch (e: any) {
      if (tab === 'pending') loadTab('pending')
      const detail = e.response?.data?.detail
      const errMsg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg).join(', ') : e.message
      showMsg('Publish failed: ' + errMsg, false)
    }
  }

  const rejectPost = async (postId: string) => {
    // Optimistic: remove immediately
    if (tab === 'pending') setPending(prev => prev ? prev.filter(p => p.id !== postId) : prev)
    if (tab === 'generate') setGenerated(null)
    try {
      await axios.post(`${API}/posts/${postId}/reject`, { reason: 'dashboard' })
      showMsg('Rejected.')
    } catch (e: any) {
      if (tab === 'pending') loadTab('pending')
      const detail = e.response?.data?.detail
      const errMsg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg).join(', ') : e.message
      showMsg('Reject failed: ' + errMsg, false)
    }
  }

  const regenPost = async (postId: string, feedbackText: string) => {
    setGenerating(true)
    try {
      const r = await axios.post(`${API}/posts/regenerate`, { post_id: postId, feedback: feedbackText })
      setGenerated(r.data)
    } catch { showMsg('Regenerate failed', false) }
    finally { setGenerating(false) }
  }

  const draftFromQueue = async (itemId: string) => {
    setLoading(true)
    try {
      const r = await axios.post(`${API}/discovery/${itemId}/draft`)
      setGenerated({ ...r.data, status: 'DRAFTED', category: r.data.category || 'GENERAL', created_at: new Date().toISOString() })
      setTab('generate'); showMsg('Draft ready — review and approve.')
    } catch { showMsg('Draft failed', false) }
    finally { setLoading(false) }
  }

  const runDiscover = async () => {
    setDiscovering(true)
    try {
      await axios.post(`${API}/discovery/run`, { category: discoverCat, max_items: 12 })
      showMsg(`Discovery running for ${discoverCat}. Refreshing in 12s…`)
      setTimeout(() => axios.get(`${API}/discovery/queue`).then(r => setQueue(r.data)).catch(() => {}), 12000)
    } catch { showMsg('Discovery failed', false) }
    finally { setDiscovering(false) }
  }

  const addExample = async () => {
    if (newExample.trim().length < 50) { showMsg('Minimum 50 characters', false); return }
    try {
      await axios.post(`${API}/style/examples`, { content: newExample, category: exCat, source_label: exLabel || null })
      setNewExample(''); setExLabel('')
      showMsg('Example added — rebuild profile to apply changes.')
      loadTab('style')
    } catch { showMsg('Failed to add example', false) }
  }

  const rebuildProfile = async () => {
    setRebuilding(true)
    try {
      await axios.post(`${API}/style/rebuild/sync`)
      showMsg('Style profile rebuilt.')
      loadTab('style')
    } catch (e: any) { showMsg('Rebuild failed: ' + (e.response?.data?.detail || e.message), false) }
    finally { setRebuilding(false) }
  }

  const deleteExample = async (id: string) => {
    await axios.delete(`${API}/style/examples/${id}`).catch(() => {})
    setSelectedExIds(prev => { const n = new Set(prev); n.delete(id); return n })
    loadTab('style')
  }

  const deleteSelectedExamples = async () => {
    await Promise.all([...selectedExIds].map(id => axios.delete(`${API}/style/examples/${id}`).catch(() => {})))
    setSelectedExIds(new Set())
    loadTab('style')
  }

  const attrs = profile?.full_attributes

  // ─── Tab labels with badges ───────────────────────────────────────────────
  const tabLabel = (t: Tab) => {
    const labels: Record<Tab, any> = {
      generate: '⚡ Generate',
      discover: '🔍 Discover',
      pending: <><span>⏳ Pending</span>{pendingCount > 0 && <span style={{ background: C.orange + '33', color: C.orange, padding: '0 5px', borderRadius: 10, fontSize: 10, fontWeight: 700 }}>{pendingCount}</span>}</>,
      published: '📤 Published',
      style: '🎨 Style',
      sources: '📡 Sources',
      scheduler: '⏰ Scheduler',
      analytics: '📊 Analytics',
    }
    return labels[t]
  }

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div style={s.app}>
      {/* Header */}
      <div style={s.header}>
        <span style={s.logo}>FRONTIER</span>
        <div style={s.headerStatus}>
          {health ? (
            <>
              <span><span style={s.dot(health.llm.healthy)} />{health.llm.provider}{health.llm.model && <span style={{ color: C.dimmer }}> · {health.llm.model}</span>}</span>
              <span><span style={s.dot(health.discord.healthy)} />Discord</span>
              <span style={{ color: health.status === 'ok' ? C.green : C.orange, fontSize: 11 }}>{health.status.toUpperCase()}</span>
            </>
          ) : (
            <span style={{ color: C.dimmer }}>connecting…</span>
          )}
        </div>
        <div style={s.headerRight}>
          <button
            style={{ ...s.btnSm(syncing ? C.dim : C.blue), fontSize: 11 }}
            disabled={syncing}
            onClick={async () => {
              setSyncing(true)
              try {
                const r = await axios.post(`${API}/channels/resync`)
                setChannelSync(r.data)
                if (r.data.all_present) showMsg(`Channels synced — all ${r.data.synced_count} present`)
                else showMsg(`Synced. ${r.data.missing_count} channel(s) missing — see banner below.`, false)
              } catch { showMsg('Resync failed', false) }
              finally { setSyncing(false) }
            }}
          >{syncing ? '⟳ Syncing…' : '⟳ Resync Channels'}</button>
          <span style={{ fontSize: 10, color: C.dimmer }}><span style={s.kbd}>Ctrl</span>+<span style={s.kbd}>Enter</span> generate</span>
        </div>
      </div>

      {/* Tab bar */}
      <div style={s.main}>
        <div style={s.tabBar}>
          {(['generate','discover','pending','published','style','sources','scheduler','analytics'] as Tab[]).map(t => (
            <button key={t} style={s.tab(tab === t)} onClick={() => setTab(t)}>
              {tabLabel(t)}
            </button>
          ))}
        </div>

        {channelSync && channelSync.missing_count > 0 && (
          <div style={{ background: '#1a0800', border: `1px solid ${C.orange}44`, borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.orange }}>⚠ {channelSync.missing_count} Discord channel{channelSync.missing_count !== 1 ? 's' : ''} missing</span>
              <button style={s.btnIcon(C.dim)} onClick={() => setChannelSync(null)}>✕</button>
            </div>
            {channelSync.missing.map((m: any) => (
              <div key={m.channel} style={{ marginBottom: 8, paddingLeft: 8, borderLeft: `2px solid ${C.orange}44` }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
                  <span style={s.channel}>{m.channel}</span>
                  <span style={{ fontSize: 11, color: '#ccc' }}>{m.purpose}</span>
                </div>
                <div style={{ fontSize: 11, color: C.orange }}>→ {m.action}</div>
              </div>
            ))}
          </div>
        )}

        {msg && (
          <div style={s.msg(msg.ok)}>
            <span>{msg.ok ? '✓' : '✕'}</span>
            <span>{msg.text}</span>
          </div>
        )}

        {/* ═══ GENERATE ══════════════════════════════════════════════════════ */}
        {tab === 'generate' && (
          <div style={{ maxWidth: 760 }}>
            <div style={s.section}>Generate Post</div>

            <div style={s.row}>
              <label style={s.label}>Topic, URL, or idea</label>
              <textarea
                ref={topicRef}
                style={{ ...s.textarea, minHeight: 88 }}
                placeholder="e.g. 'new Claude API features' · 'explain RAG for beginners' · or paste https://..."
                value={topic}
                onChange={e => setTopic(e.target.value)}
                onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); generate() }
                }}
              />
            </div>

            {/* File attachment */}
            <div style={{ marginBottom: 12 }}>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,video/*,.pdf,.txt,.md,.csv"
                style={{ display: 'none' }}
                onChange={e => setAttachedFile(e.target.files?.[0] || null)}
              />
              {attachedFile ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: C.surface2, border: `1px solid ${C.blue}44`, borderRadius: 6, padding: '8px 12px' }}>
                  <span style={{ fontSize: 16 }}>
                    {attachedFile.type.startsWith('image/') ? '🖼️' : attachedFile.type.startsWith('video/') ? '🎬' : '📄'}
                  </span>
                  <span style={{ fontSize: 12, color: C.text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{attachedFile.name}</span>
                  <span style={{ fontSize: 11, color: C.muted }}>{(attachedFile.size / 1024).toFixed(0)} KB</span>
                  <button style={s.btnIcon(C.red)} onClick={() => { setAttachedFile(null); if (fileInputRef.current) fileInputRef.current.value = '' }}>✕</button>
                </div>
              ) : (
                <button style={{ ...s.btn(C.dim), fontSize: 12 }} onClick={() => fileInputRef.current?.click()}>
                  📎 Attach file
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <label style={s.label}>Channel</label>
                <select style={s.select} value={chan} onChange={e => setChan(e.target.value)}>
                  <option value="">Auto-route</option>
                  {CHANNELS.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label style={s.label}>Category</label>
                <select style={s.select} value={cat} onChange={e => setCat(e.target.value)}>
                  {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <button
                style={{ ...s.btn(generating ? C.dim : C.green, !generating), padding: '8px 20px', fontSize: 13, marginLeft: 'auto' }}
                onClick={generate}
                disabled={generating || !topic.trim()}
              >
                {generating ? '⏳ Generating…' : '⚡ Generate'}
              </button>
            </div>

            {generating && !generated && <Skeleton lines={4} />}

            {generated && (
              <div style={{ ...s.card, borderLeft: `3px solid ${C.green}` }}>
                <PostCard
                  post={generated}
                  onPublish={publishPost}
                  onReject={rejectPost}
                  onFeedback={regenPost}
                />
              </div>
            )}
          </div>
        )}

        {/* ═══ DISCOVER ══════════════════════════════════════════════════════ */}
        {tab === 'discover' && (
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginBottom: 20, flexWrap: 'wrap' }}>
              <div>
                <label style={s.label}>Category</label>
                <select style={s.select} value={discoverCat} onChange={e => setDiscoverCat(e.target.value)}>
                  {DISCOVER_CATS.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <button style={s.btn(C.orange, true)} onClick={runDiscover} disabled={discovering}>
                {discovering ? '🔍 Searching…' : '🔍 Run Discovery'}
              </button>
              <button style={s.btn(C.dim)} onClick={() => loadTab('discover')}>↻ Refresh</button>
              {queue !== null && <span style={{ fontSize: 12, color: C.dim, marginLeft: 4 }}>{queue.length} item{queue.length !== 1 ? 's' : ''} in queue</span>}
            </div>

            {queue === null && <>{Array.from({length: 3}).map((_, i) => <Skeleton key={i} />)}</>}
            {queue?.length === 0 && <div style={s.emptyState}>Queue empty — run discovery to find new content.</div>}
            {queue?.map(item => {
              const catColor = CAT_COLORS[item.category] || C.muted
              return (
                <div key={item.id} style={{ ...s.cardHover, borderLeft: `3px solid ${catColor}44` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span style={s.channel}>{item.channel}</span>
                      <span style={s.badge(catColor)}>{item.category}</span>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: item.relevance >= 0.8 ? C.green : item.relevance >= 0.6 ? C.orange : C.muted }}>
                        {(item.relevance * 100).toFixed(0)}%
                      </div>
                      <div style={{ fontSize: 10, color: C.dimmer }}>relevance</div>
                    </div>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: C.text }}>{item.title || 'Untitled'}</div>
                  {item.url && <div style={{ fontSize: 11, color: C.dimmer, marginBottom: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.url}</div>}
                  <div style={s.btnRow}>
                    <button style={s.btn(C.green, true)} onClick={() => draftFromQueue(item.id)}>⚡ Draft Post</button>
                    {item.url && <a href={item.url} target="_blank" rel="noreferrer" style={{ ...s.btnSm(C.blue), textDecoration: 'none' }}>↗ Open</a>}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* ═══ PENDING ═══════════════════════════════════════════════════════ */}
        {tab === 'pending' && (
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
              <div style={{ ...s.section, margin: 0 }}>Pending Approval</div>
              {pending !== null && <span style={s.badge(C.orange, true)}>{pending.length}</span>}
              <button style={{ ...s.btn(C.dim), marginLeft: 'auto' }} onClick={() => loadTab('pending')}>↻ Refresh</button>
              {pending && pending.length > 0 && (
                <button style={s.btn(C.orange)} onClick={async () => {
                  showMsg('Running auto-draft cycle…')
                  const r = await axios.post(`${API}/queue/run-cycle-sync`).catch(() => null)
                  if (r) showMsg(`Cycle done: ${r.data.drafted} drafted, ${r.data.expired} expired`)
                  loadTab('pending')
                }}>▶ Queue Cycle</button>
              )}
            </div>

            {pending === null && <>{Array.from({length: 3}).map((_, i) => <Skeleton key={i} lines={4} />)}</>}
            {pending?.length === 0 && (
              <div style={s.emptyState}>
                No pending posts.<br />
                <span style={{ fontSize: 12 }}>Run a queue cycle or generate a post manually.</span>
              </div>
            )}
            {pending?.map(p => (
              <PostCard
                key={p.id}
                post={p}
                onPublish={publishPost}
                onReject={rejectPost}
                onFeedback={regenPost}
                showSource
              />
            ))}
          </div>
        )}

        {/* ═══ PUBLISHED ═════════════════════════════════════════════════════ */}
        {tab === 'published' && (
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 20 }}>
              <div style={{ ...s.section, margin: 0 }}>Published</div>
              {published !== null && <span style={s.badge(C.green, true)}>{published.length}</span>}
              <button style={{ ...s.btn(C.dim), marginLeft: 'auto' }} onClick={() => loadTab('published')}>↻ Refresh</button>
            </div>

            {published === null && <>{Array.from({length: 3}).map((_, i) => <Skeleton key={i} lines={3} />)}</>}
            {published?.length === 0 && <div style={s.emptyState}>No published posts yet.</div>}
            {published?.map(p => (
              <PostCard key={p.id} post={p} />
            ))}
          </div>
        )}

        {/* ═══ SOURCES ═══════════════════════════════════════════════════════ */}
        {tab === 'sources' && (
          <div>
            {/* Add source */}
            <div style={{ ...s.card, marginBottom: 24 }}>
              <div style={{ ...s.section, marginBottom: 12 }}>Add Custom Source</div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
                <div style={{ flex: '2 1 200px' }}>
                  <label style={s.label}>Name</label>
                  <input style={s.input} placeholder="HuggingFace Blog" value={newSrc.name} onChange={e => setNewSrc(p => ({ ...p, name: e.target.value }))} />
                </div>
                <div style={{ flex: '0 0 auto' }}>
                  <label style={s.label}>Type</label>
                  <select style={s.select} value={newSrc.source_type} onChange={e => setNewSrc(p => ({ ...p, source_type: e.target.value }))}>
                    {['RSS', 'X', 'WEB_SEARCH'].map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div style={{ flex: '0 0 auto' }}>
                  <label style={s.label}>Category</label>
                  <select style={s.select} value={newSrc.category} onChange={e => setNewSrc(p => ({ ...p, category: e.target.value }))}>
                    {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div style={s.row}>
                <label style={s.label}>{newSrc.source_type === 'RSS' ? 'Feed URL' : 'Search Query'}</label>
                <input style={s.input}
                  placeholder={newSrc.source_type === 'RSS' ? 'https://example.com/feed.xml' : 'AI tools released lang:en -is:retweet'}
                  value={newSrc.source_type === 'RSS' ? newSrc.url : newSrc.query}
                  onChange={e => newSrc.source_type === 'RSS' ? setNewSrc(p => ({ ...p, url: e.target.value })) : setNewSrc(p => ({ ...p, query: e.target.value }))}
                />
              </div>
              <button style={s.btn(C.green, true)} disabled={!newSrc.name.trim()} onClick={async () => {
                const payload = { ...newSrc, url: newSrc.source_type === 'RSS' ? newSrc.url || null : null, query: newSrc.source_type !== 'RSS' ? newSrc.query || null : null }
                try {
                  await axios.post(`${API}/sources`, payload)
                  setNewSrc({ name: '', source_type: 'RSS', url: '', query: '', category: 'AI' })
                  showMsg('Source added!')
                  loadTab('sources')
                } catch (e: any) { showMsg(e.response?.data?.detail || 'Add failed', false) }
              }}>+ Add Source</button>
            </div>

            {/* Built-in feeds */}
            {sources?.builtin?.length > 0 && (
              <>
                <div style={s.section}>Built-in RSS Feeds ({sources.builtin.length})</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 8, marginBottom: 24 }}>
                  {sources.builtin.map((src: any) => (
                    <div key={src.id} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: '10px 14px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{src.name}</span>
                        <span style={s.badge(CAT_COLORS[src.category] || C.muted)}>{src.category}</span>
                      </div>
                      <div style={{ fontSize: 11, color: C.dimmer, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{src.url}</div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Custom sources */}
            {sources !== null && sources.custom?.length === 0 && sources.builtin?.length === 0 && (
              <div style={s.emptyState}>No sources yet. Add one above.</div>
            )}
            {sources?.custom?.length > 0 && (
              <>
                <div style={s.section}>Custom Sources ({sources.custom.length})</div>
                {sources.custom.map((src: any) => (
                  <div key={src.id} style={{ ...s.cardHover, opacity: src.is_enabled ? 1 : 0.5 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 4 }}>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>{src.name}</span>
                          <span style={s.badge(C.orange)}>{src.source_type}</span>
                          <span style={s.badge(CAT_COLORS[src.category] || C.muted)}>{src.category}</span>
                          {!src.is_enabled && <span style={s.badge(C.dim)}>paused</span>}
                        </div>
                        <div style={{ fontSize: 11, color: C.dimmer }}>{(src.url || src.query)?.slice(0, 80)}</div>
                        {src.fetch_count > 0 && (
                          <div style={{ fontSize: 10, color: C.dimmer, marginTop: 4 }}>
                            fetched {src.fetch_count}× · last {src.last_fetched?.slice(0, 16) || 'never'}
                            {src.error_count > 0 && <span style={{ color: C.red, marginLeft: 8 }}>{src.error_count} errors</span>}
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                        <button style={s.btnSm(C.orange)} title="Fetch now" onClick={async () => {
                          try {
                            const r = await axios.post(`${API}/sources/${src.id}/fetch`)
                            showMsg(`${src.name}: ${r.data.saved} new items saved`)
                            loadTab('sources')
                          } catch { showMsg('Fetch failed', false) }
                        }}>↻ fetch</button>
                        <button style={s.btnSm(src.is_enabled ? C.dim : C.green)} onClick={async () => {
                          await axios.post(`${API}/sources/${src.id}/toggle`).catch(() => {})
                          loadTab('sources')
                        }}>{src.is_enabled ? 'pause' : 'resume'}</button>
                        <button style={s.btnSm(C.red)} onClick={async () => {
                          await axios.delete(`${API}/sources/${src.id}`).catch(() => {})
                          loadTab('sources')
                        }}>✕</button>
                      </div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* ═══ SCHEDULER ═════════════════════════════════════════════════════ */}
        {tab === 'scheduler' && (
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 20 }}>
              <div style={{ ...s.section, margin: 0 }}>Scheduled Jobs</div>
              {schedJobs?.running && <span style={s.badge(C.green, true)}>running</span>}
              {schedJobs && !schedJobs.running && <span style={s.badge(C.red, true)}>stopped</span>}
              <button style={{ ...s.btn(C.dim), marginLeft: 'auto' }} onClick={() => loadTab('scheduler')}>↻ Refresh</button>
            </div>

            {!schedJobs && <Skeleton lines={3} />}
            {schedJobs && !schedJobs.running && (
              <div style={{ ...s.card, borderLeft: `3px solid ${C.orange}` }}>
                <div style={{ color: C.orange, fontWeight: 600, marginBottom: 6 }}>Scheduler not running</div>
                <div style={{ fontSize: 12, color: C.muted }}>Start FRONTIER via <code style={{ color: C.text }}>python run.py</code> to enable automatic discovery.</div>
              </div>
            )}

            {schedJobs?.jobs?.map((job: any) => (
              <div key={job.id} style={{ ...s.cardHover, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{job.description}</div>
                  <div style={{ fontSize: 11, color: C.dim }}>
                    cron: <code style={{ background: C.surface2, padding: '1px 5px', borderRadius: 3, color: C.text }}>{job.cron}</code>
                    {job.next_run && (
                      <span style={{ marginLeft: 10, color: C.dimmer }}>
                        next: {job.next_run.slice(0, 16)} UTC
                      </span>
                    )}
                  </div>
                </div>
                <button
                  style={s.btn(triggeringJob === job.id ? C.dim : C.green, triggeringJob !== job.id)}
                  disabled={triggeringJob === job.id}
                  onClick={async () => {
                    setTriggeringJob(job.id)
                    try {
                      await axios.post(`${API}/scheduler/${job.id}/run-sync`)
                      showMsg(`${job.description} complete.`)
                    } catch (e: any) { showMsg('Job failed: ' + (e.response?.data?.detail || e.message), false) }
                    finally { setTriggeringJob(null) }
                  }}
                >
                  {triggeringJob === job.id ? '⏳ Running…' : '▶ Run Now'}
                </button>
              </div>
            ))}

            {/* ── Auto-publish rules ─────────────────────────────────────── */}
            {apRules.length > 0 && (
              <>
                <div style={{ ...s.divider }} />
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 }}>
                  <div style={{ ...s.section, margin: 0 }}>Auto-Publish Rules</div>
                  <span style={{ fontSize: 11, color: C.dim }}>— bypass human approval when enabled</span>
                  <button style={{ ...s.btnSm(C.orange), marginLeft: 'auto' }} onClick={async () => {
                    try {
                      const r = await axios.post(`${API}/autopublish/run`)
                      showMsg(`Auto-publish: ${r.data.auto_published} posts published`)
                    } catch { showMsg('Auto-publish run failed', false) }
                  }}>▶ Run Now</button>
                </div>

                <div style={{ ...s.card, background: C.surface2, marginBottom: 14, fontSize: 12, color: C.muted, lineHeight: 1.6 }}>
                  ⚠️ Auto-published posts skip human review and go live immediately.
                  Rules are <strong style={{ color: C.text }}>disabled by default</strong>.
                  Enable only for content types you trust at the score threshold.
                  <strong style={{ color: C.red }}> #signal and #missions are permanently blocked.</strong>
                </div>

                {apRules.map((rule: any) => (
                  <div key={rule.id} style={{ ...s.cardHover, borderLeft: `3px solid ${rule.is_enabled ? C.orange : C.border}`, opacity: rule.is_enabled ? 1 : 0.65 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>{rule.name}</span>
                          {rule.category && <span style={s.badge(CAT_COLORS[rule.category] || C.muted)}>{rule.category}</span>}
                          {rule.channel && <span style={s.channel}>{rule.channel}</span>}
                          {rule.is_enabled && <span style={s.badge(C.orange, true)}>LIVE</span>}
                        </div>
                        <div style={{ fontSize: 11, color: C.dim }}>
                          min score: <strong style={{ color: rule.min_score >= 0.92 ? C.green : C.orange }}>{(rule.min_score * 100).toFixed(0)}%</strong>
                          <span style={{ marginLeft: 12 }}>{rule.category || 'any category'} → {rule.channel || 'any channel'}</span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {/* Min score nudge */}
                        <select
                          style={{ ...s.select, fontSize: 11, padding: '4px 8px' }}
                          value={rule.min_score}
                          disabled={apSaving === rule.id}
                          onChange={async e => {
                            const score = parseFloat(e.target.value)
                            setApSaving(rule.id)
                            try {
                              await axios.patch(`${API}/autopublish/rules/${rule.id}`, { min_score: score })
                              setApRules(prev => prev.map(r => r.id === rule.id ? { ...r, min_score: score } : r))
                            } catch { showMsg('Save failed', false) }
                            finally { setApSaving(null) }
                          }}
                        >
                          {[0.80, 0.85, 0.88, 0.90, 0.92, 0.95].map(v => (
                            <option key={v} value={v}>{(v * 100).toFixed(0)}%</option>
                          ))}
                        </select>
                        {/* Enable/disable toggle */}
                        <button
                          style={s.btn(rule.is_enabled ? C.red : C.green, rule.is_enabled)}
                          disabled={apSaving === rule.id}
                          onClick={async () => {
                            setApSaving(rule.id)
                            try {
                              await axios.patch(`${API}/autopublish/rules/${rule.id}`, { is_enabled: !rule.is_enabled })
                              setApRules(prev => prev.map(r => r.id === rule.id ? { ...r, is_enabled: !r.is_enabled } : r))
                              showMsg(rule.is_enabled ? `Rule "${rule.name}" disabled.` : `Rule "${rule.name}" enabled — posts will auto-publish!`)
                            } catch (e: any) { showMsg(e.response?.data?.detail || 'Toggle failed', false) }
                            finally { setApSaving(null) }
                          }}
                        >
                          {apSaving === rule.id ? '…' : rule.is_enabled ? 'Disable' : 'Enable'}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* ═══ ANALYTICS ═════════════════════════════════════════════════════ */}
        {tab === 'analytics' && (
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
              <div style={{ ...s.section, margin: 0 }}>Analytics</div>
              <select style={s.select} value={analyticsDays} onChange={e => setAnalyticsDays(Number(e.target.value))}>
                {[3,7,14,30].map(d => <option key={d} value={d}>Last {d}d</option>)}
              </select>
              <button style={s.btn(C.dim)} onClick={() => loadTab('analytics')}>↻ Refresh</button>
              <button style={{ ...s.btn(C.orange), marginLeft: 'auto' }} onClick={async () => {
                showMsg('Running queue cycle…')
                try {
                  const r = await axios.post(`${API}/queue/run-cycle-sync`)
                  showMsg(`Cycle done: ${r.data.drafted} drafted · ${r.data.expired} expired · ${r.data.notified} notified`)
                  loadTab('analytics')
                } catch { showMsg('Cycle failed', false) }
              }}>▶ Run Queue Cycle</button>
            </div>

            {analyticsData === null && <>{Array.from({length: 2}).map((_, i) => <Skeleton key={i} lines={4} />)}</>}

            {/* Funnel stat cards */}
            {analyticsData?.funnel && (() => {
              const f = analyticsData.funnel
              const stats = [
                { label: 'Discovered', val: f.discovered, color: C.blue },
                { label: 'Analyzed', val: f.analyzed, color: C.purple },
                { label: 'Drafted', val: f.drafted, color: C.orange },
                { label: 'Pending', val: f.pending_approval, color: '#ff8800' },
                { label: 'Published', val: f.published, color: C.green },
                { label: 'Rejected', val: f.rejected, color: C.red },
                { label: 'Expired', val: f.expired, color: C.dim },
                { label: 'Dupes blocked', val: f.duplicates_blocked, color: C.dimmer },
              ]
              return (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 10, marginBottom: 20 }}>
                    {stats.map(st => (
                      <div key={st.label} style={s.statCard(st.color)}>
                        <div style={{ fontSize: 26, fontWeight: 800, color: st.color, lineHeight: 1.1 }}>{st.val}</div>
                        <div style={{ fontSize: 11, color: C.muted, marginTop: 4 }}>{st.label}</div>
                      </div>
                    ))}
                  </div>

                  {/* Rates */}
                  <div style={{ ...s.card, display: 'flex', gap: 32, flexWrap: 'wrap', marginBottom: 20 }}>
                    <div>
                      <div style={{ fontSize: 10, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>Publish rate</div>
                      <div style={{ fontSize: 28, fontWeight: 800, color: C.green }}>{(f.publish_rate * 100).toFixed(0)}%</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>Duplicate filter rate</div>
                      <div style={{ fontSize: 28, fontWeight: 800, color: C.orange }}>{(f.duplicate_rate * 100).toFixed(0)}%</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>Period</div>
                      <div style={{ fontSize: 28, fontWeight: 800, color: C.muted }}>{analyticsDays}d</div>
                    </div>
                  </div>
                </>
              )
            })()}

            {/* Category + channel bar charts */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16, marginBottom: 20 }}>
              {analyticsData?.by_category?.length > 0 && (
                <div style={s.card}>
                  <div style={s.section}>By Category</div>
                  {(() => {
                    const maxVal = Math.max(...analyticsData.by_category.map((r: any) => r.count), 1)
                    return analyticsData.by_category.slice(0, 8).map((r: any) => (
                      <BarRow key={r.category} label={r.category} val={r.count} max={maxVal} color={CAT_COLORS[r.category] || C.muted} />
                    ))
                  })()}
                </div>
              )}
              {analyticsData?.by_channel?.length > 0 && (
                <div style={s.card}>
                  <div style={s.section}>By Channel</div>
                  {(() => {
                    const maxVal = Math.max(...analyticsData.by_channel.map((r: any) => r.count), 1)
                    return analyticsData.by_channel.slice(0, 8).map((r: any) => (
                      <BarRow key={r.channel} label={r.channel} val={r.count} max={maxVal} color={C.green} />
                    ))
                  })()}
                </div>
              )}
            </div>

            {/* Activity table */}
            {activityData.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={s.section}>Daily Activity (14d)</div>
                <div style={{ ...s.card, padding: 0, overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: C.surface2 }}>
                        <th style={{ textAlign: 'left', padding: '8px 14px', color: C.dim, fontWeight: 600 }}>Date</th>
                        <th style={{ textAlign: 'right', padding: '8px 14px', color: C.blue, fontWeight: 600 }}>Discovered</th>
                        <th style={{ textAlign: 'right', padding: '8px 14px', color: C.green, fontWeight: 600 }}>Published</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...activityData].reverse().map(d => (
                        <tr key={d.date} style={{ borderTop: `1px solid ${C.border}` }}>
                          <td style={{ padding: '7px 14px', color: C.muted }}>{d.date}</td>
                          <td style={{ padding: '7px 14px', textAlign: 'right', color: d.discovered > 0 ? C.blue : C.dimmer, fontWeight: d.discovered > 0 ? 600 : 400 }}>{d.discovered || '—'}</td>
                          <td style={{ padding: '7px 14px', textAlign: 'right', color: d.published > 0 ? C.green : C.dimmer, fontWeight: d.published > 0 ? 600 : 400 }}>{d.published || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Top content */}
            {topContent.length > 0 && (
              <>
                <div style={s.section}>Top Scoring Content</div>
                {topContent.map(ci => (
                  <div key={ci.id} style={{ ...s.cardHover, borderLeft: `3px solid ${CAT_COLORS[ci.category] || C.dim}44` }}>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>{ci.title?.slice(0, 90) || 'Untitled'}</div>
                        {ci.url && <div style={{ fontSize: 11, color: C.dimmer, marginBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ci.url}</div>}
                        <div>
                          {ci.category && <span style={s.badge(CAT_COLORS[ci.category] || C.muted)}>{ci.category}</span>}
                          {ci.channel && <span style={{ ...s.badge(C.green), marginLeft: 4 }}>{ci.channel}</span>}
                          <span style={{ ...s.badge(ci.status === 'PUBLISHED' ? C.green : C.dim), marginLeft: 4 }}>{ci.status}</span>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div style={{ fontSize: 20, fontWeight: 800, color: ci.score >= 0.8 ? C.green : ci.score >= 0.6 ? C.orange : C.muted }}>
                          {(ci.score * 100).toFixed(0)}%
                        </div>
                        <div style={{ fontSize: 10, color: C.dimmer }}>score</div>
                      </div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* ═══ STYLE ══════════════════════════════════════════════════════════ */}
        {tab === 'style' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div style={{ ...s.section, margin: 0 }}>Writing Style Profile</div>
              <button style={s.btn(C.orange, rebuilding)} onClick={rebuildProfile} disabled={rebuilding}>
                {rebuilding ? '⏳ Rebuilding…' : '↺ Rebuild Profile'}
              </button>
            </div>

            {profile?.exists && attrs ? (
              <div style={{ ...s.card, marginBottom: 24, borderLeft: `3px solid ${C.green}44` }}>
                <div style={{ fontSize: 11, color: C.dim, marginBottom: 12 }}>
                  Active · {profile.example_count} example{profile.example_count !== 1 ? 's' : ''} · updated {profile.updated_at?.slice(0, 10)}
                </div>
                {attrs.summary && (
                  <div style={{ fontSize: 14, color: '#bbb', marginBottom: 16, fontStyle: 'italic', borderLeft: `2px solid ${C.green}44`, paddingLeft: 12 }}>
                    "{attrs.summary}"
                  </div>
                )}
                {[
                  ['Tone', Array.isArray(attrs.tone) ? attrs.tone.map((t: string) => <span key={t} style={s.pill(C.green)}>{t}</span>) : attrs.tone],
                  ['Formality', attrs.formality],
                  ['Sentence length', attrs.sentence_length],
                  ['Technical depth', attrs.technical_depth],
                  ['Humor level', attrs.humor_level],
                  ['Emoji usage', attrs.emoji_usage],
                  ['Preferred words', (attrs.vocabulary?.preferred || []).map((w: string) => <span key={w} style={s.pill(C.blue)}>{w}</span>)],
                  ['Avoided words', (attrs.vocabulary?.avoided || []).map((w: string) => <span key={w} style={s.pill(C.red)}>{w}</span>)],
                  ['Things to avoid', (attrs.things_to_avoid || []).join(' · ')],
                  ['Structure', (attrs.structural_patterns || []).join(' · ')],
                ].map(([k, v]) => v && (Array.isArray(v) ? (v as any[]).length > 0 : String(v).trim()) ? (
                  <div key={String(k)} style={s.profileRow}>
                    <span style={s.profileKey}>{k}</span>
                    <span style={s.profileVal}>{v}</span>
                  </div>
                ) : null)}
              </div>
            ) : profile !== null ? (
              <div style={{ ...s.card, color: C.dim, marginBottom: 24 }}>
                No style profile yet. Add writing examples below, then click "Rebuild Profile".
              </div>
            ) : <Skeleton lines={8} />}

            <div style={s.divider} />

            {/* Add example */}
            <div style={{ ...s.section, marginBottom: 12 }}>Add Writing Example</div>
            <div style={s.card}>
              <div style={{ fontSize: 12, color: C.muted, marginBottom: 12, lineHeight: 1.6 }}>
                Paste your own writing here — Discord posts, announcements, messages you wrote. FRONTIER learns your voice from these.
              </div>
              <div style={s.row}>
                <label style={s.label}>Your writing ({newExample.trim().length} chars{newExample.trim().length < 50 ? ` — need ${50 - newExample.trim().length} more` : ' ✓'})</label>
                <textarea style={{ ...s.textarea, minHeight: 120 }}
                  placeholder="Paste one of your own posts or messages here…"
                  value={newExample} onChange={e => setNewExample(e.target.value)} />
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
                <div>
                  <label style={s.label}>Category</label>
                  <select style={s.select} value={exCat} onChange={e => setExCat(e.target.value)}>
                    {STYLE_CATS.map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <label style={s.label}>Label (optional)</label>
                  <input style={s.input} placeholder="e.g. 'my #neural post Jan 2025'" value={exLabel} onChange={e => setExLabel(e.target.value)} />
                </div>
              </div>
              <button style={s.btn(C.green, newExample.trim().length >= 50)} onClick={addExample} disabled={newExample.trim().length < 50}>
                + Add Example
              </button>
            </div>

            {/* Existing examples */}
            {examples.length > 0 && (
              <>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 24, marginBottom: 14 }}>
                  <div style={{ ...s.section, margin: 0 }}>Stored Examples ({examples.length})</div>
                  {selectedExIds.size > 0 && (
                    <button style={s.btn(C.red)} onClick={deleteSelectedExamples}>
                      Delete {selectedExIds.size} selected
                    </button>
                  )}
                </div>
                {examples.map(ex => {
                  const sel = selectedExIds.has(ex.id)
                  return (
                    <div key={ex.id} style={{ ...s.cardHover, borderLeft: `3px solid ${sel ? C.blue : C.border}`, cursor: 'pointer' }}
                      onClick={() => setSelectedExIds(prev => { const n = new Set(prev); sel ? n.delete(ex.id) : n.add(ex.id); return n })}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <input type="checkbox" checked={sel} onChange={() => {}} style={{ accentColor: C.blue }} />
                          <span style={s.badge(CAT_COLORS[ex.category.toUpperCase()] || C.blue, true)}>{ex.category}</span>
                          {ex.source_label && <span style={{ fontSize: 11, color: C.dim }}>{ex.source_label}</span>}
                          <span style={{ fontSize: 10, color: C.dimmer }}>{ex.created_at?.slice(0, 10)}</span>
                        </div>
                        <button style={s.btnIcon(C.red)} onClick={e => { e.stopPropagation(); deleteExample(ex.id) }}>✕</button>
                      </div>
                      <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>{ex.content_preview}</div>
                    </div>
                  )
                })}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
