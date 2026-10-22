import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { api } from "./api";
import type { Entity, GitImpact, Impact, Relationship, Summary } from "./api";
import { ChangeResults, EntityResults } from "./ResultLists";

type Screen = "Repository" | "Overview" | "Graph" | "Impact" | "Git changes";
const screens: Screen[] = ["Repository", "Overview", "Graph", "Impact", "Git changes"];

export default function App() {
  const [screen, setScreen] = useState<Screen>("Repository");
  const [path, setPath] = useState("");
  const [analysis, setAnalysis] = useState<Summary | null>(null);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [impact, setImpact] = useState<Impact | null>(null);
  const [gitImpact, setGitImpact] = useState<GitImpact | null>(null);
  const [baseRef, setBaseRef] = useState("");
  const [targetRef, setTargetRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected = entities.find((entity) => entity.id === selectedId) ?? null;
  const orderedEntities = useMemo(() => [...entities].sort((a, b) =>
    a.file_path.localeCompare(b.file_path) || a.line_number - b.line_number), [entities]);

  async function analyzeRepository(event: FormEvent) {
    event.preventDefault();
    if (!path.trim()) return;
    setBusy(true); setError(""); setImpact(null); setGitImpact(null);
    try {
      const result = await api.analyze(path.trim());
      const [summaryDetails, entityRows, relationshipRows] = await Promise.all([
        api.summary(result.analysis_id), api.entities(result.analysis_id), api.relationships(result.analysis_id),
      ]);
      setAnalysis(summaryDetails); setEntities(entityRows); setRelationships(relationshipRows);
      setSelectedId(entityRows[0]?.id ?? ""); setScreen("Overview");
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  async function refreshSummary() {
    if (!analysis) return;
    setBusy(true); setError("");
    try { setAnalysis(await api.summary(analysis.analysis_id)); }
    catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  async function chooseEntity(id: string) {
    setSelectedId(id); setImpact(null); setError("");
    if (!analysis || !id) return;
    try { setImpact(await api.impact(analysis.analysis_id, id)); }
    catch (reason) { setError((reason as Error).message); }
  }

  async function compareGit() {
    if (!analysis) return;
    setBusy(true); setError(""); setGitImpact(null);
    try {
      const cleanBase = baseRef.trim();
      const effectiveBase = (!cleanBase || cleanBase === "Saved analysis commit") ? null : cleanBase;
      const cleanTarget = targetRef.trim() || null;
      setGitImpact(await api.gitImpact(analysis.analysis_id, effectiveBase, cleanTarget));
    }
    catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">T</span><div><b>TRACEGRAPH</b><small>CODE INTELLIGENCE</small></div></div>
      <div className="sidebar-label">WORKSPACE</div>
      <nav>{screens.map((item, index) => <button key={item}
        className={screen === item ? "nav-item active" : "nav-item"}
        onClick={() => { setError(""); setScreen(item); }}>
        <span className="nav-icon">{["⌂", "▦", "⌘", "◎", "⑂"][index]}</span>{item}
        {index === 0 && !analysis && <span className="nav-dot" />}
      </button>)}</nav>
      <div className="sidebar-bottom"><div className="engine"><span className="online-dot" /><div><b>Analysis engine</b><small>Deterministic · Local</small></div></div><div className="sidebar-foot">TRACEGRAPH <i>·</i> MILESTONE 6</div></div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="breadcrumbs">Tracegraph <i>/</i> <b>{screen}</b></div><span className="local-badge"><span className="online-dot" /> LOCAL ANALYSIS</span></header>
      <div className="content">
        {error && <div className="alert"><b>!</b><span>{error}</span><button aria-label="Dismiss" onClick={() => setError("")}>×</button></div>}

        {screen === "Repository" && <section className="hero">
          <div className="eyebrow">CODEBASE INTELLIGENCE</div>
          <h1>Understand your code.<br /><em>See what changes.</em></h1>
          <p className="hero-copy">Map a Python repository, trace dependencies, and understand the reach of every change.</p>
          <form className="panel analyze-form" onSubmit={analyzeRepository}>
            <label htmlFor="repository-path">REPOSITORY PATH</label>
            <input id="repository-path" required value={path} onChange={(event) => setPath(event.target.value)} placeholder="C:\path\to\your\repository" />
            <div className="form-footer"><small>Local directory accessible to the Tracegraph API server</small><button className="primary" disabled={busy || !path.trim()}>{busy ? "Analyzing…" : <>Analyze repository <span>→</span></>}</button></div>
          </form>
          <div className="capabilities"><span>01　Python AST parsing</span><span>02　Dependency mapping</span><span>03　Git-aware impact</span></div>
          <p className="privacy-note">Your source code is analyzed locally and is never executed by Tracegraph.</p>
        </section>}

        {screen === "Overview" && <section>
          <PageHeading title="Repository overview" detail={analysis?.repository_path ?? "Analysis summary"} />
          {!analysis ? <EmptyState onAnalyze={() => setScreen("Repository")} /> : <>
            <div className="metrics">
              <Metric label="ENTITIES" value={analysis.total_entities} note="Files, classes & functions" />
              <Metric label="RELATIONSHIPS" value={analysis.total_relationships} note="Resolved connections" />
              <Metric label="PACKAGES" value={analysis.packages?.length ?? 0} note="Detected Python packages" />
              <Metric label="PARSE ISSUES" value={analysis.parse_errors?.length ?? 0} note="Files needing attention" />
            </div>
            <article className="panel"><PanelHeading title="Analysis details" badge={analysis.status} action={<button className="text-button" disabled={busy} onClick={refreshSummary}>{busy ? "Refreshing…" : "Refresh"}</button>} />
              <Detail label="Repository" value={analysis.repository_path} code />
              <Detail label="Analysis ID" value={analysis.analysis_id} code />
              <Detail label="Engine" value="Static Python AST · deterministic" />
              <Detail label="Baseline commit" value={analysis.commit_hash ? analysis.commit_hash.slice(0, 8) : "None (unversioned)"} code={Boolean(analysis.commit_hash)} />
              <Detail label="Packages" value={analysis.packages?.join(", ") || "No packages reported"} />
            </article>
            {!!analysis.parse_errors?.length && <article className="panel issue-panel"><PanelHeading title="Parse issues" badge={analysis.parse_errors.length} />{analysis.parse_errors.map((row, index) => <div className="issue-row" key={index}>⚠　<code>{row.join(" · ")}</code></div>)}</article>}
            <div className="quick-links">{(["Graph", "Impact", "Git changes"] as Screen[]).map((item) => <button key={item} onClick={() => setScreen(item)}>{item} <span>→</span></button>)}</div>
          </>}
        </section>}

        {screen === "Graph" && <section>
          <PageHeading title="Dependency graph" detail="Explore direct code connections from the analyzed repository." />
          {!analysis ? <EmptyState onAnalyze={() => setScreen("Repository")} /> : <>
            <EntityPicker items={orderedEntities} value={selectedId} onChange={setSelectedId} />
            <DependencyGraph selected={selected} entities={entities} relationships={relationships} />
            <p className="graph-caption">Showing direct neighbors of the selected entity · {relationships.length} total relationships</p>
          </>}
        </section>}

        {screen === "Impact" && <section>
          <PageHeading title="Impact analysis" detail="Trace what an entity depends on and which entities may depend on it." />
          {!analysis ? <EmptyState onAnalyze={() => setScreen("Repository")} /> : <>
            <EntityPicker items={orderedEntities} value={selectedId} onChange={chooseEntity} />
            {selected && <div className="selected-entity"><span>◎</span><div><small>SELECTED ENTITY</small><b>{selected.name}</b><code>{selected.file_path}:{selected.line_number}</code></div></div>}
            {impact ? <div className="two-column">
              <EntityResults title="Direct dependents" items={impact.direct_dependents} />
              <EntityResults title="Indirect dependents" items={impact.indirect_dependents} />
              <EntityResults title="Direct dependencies" items={impact.direct_dependencies} />
              <EntityResults title="Indirect dependencies" items={impact.indirect_dependencies} />
            </div> : <div className="panel muted center">{selected ? <button className="text-button" onClick={() => void chooseEntity(selected.id)}>Load impact for {selected.name} →</button> : "Select an entity to calculate its impact."}</div>}
            <p className="footnote">Impact is a static estimate from resolved relationships; it does not guarantee runtime behavior.</p>
          </>}
        </section>}

        {screen === "Git changes" && <section>
          <PageHeading title="Git changes & impact" detail="Compare the analyzed baseline with your working tree or another Git ref." />
          {!analysis ? <EmptyState onAnalyze={() => setScreen("Repository")} /> : <>
            <article className="panel git-form"><div className="baseline"><span>⑂</span><div><b>Analysis baseline</b><small>{analysis.commit_hash ? `Defaults to saved commit: ${analysis.commit_hash.slice(0, 8)}` : "Defaults to the commit recorded when this analysis ran."}</small></div></div>
              <div className="ref-grid"><label>BASE REF<input value={baseRef} onChange={(event) => setBaseRef(event.target.value)} placeholder={analysis.commit_hash ? `Saved commit (${analysis.commit_hash.slice(0, 7)})` : "Saved analysis commit"} /></label><label>TARGET REF<input value={targetRef} onChange={(event) => setTargetRef(event.target.value)} placeholder="Working tree (default)" /></label></div>
              <button className="primary" disabled={busy} onClick={compareGit}>{busy ? "Comparing…" : <>Compare changes <span>→</span></>}</button>
            </article>
            {gitImpact && <>
              <div className="metrics three"><Metric label="CHANGED FILES" value={gitImpact.changes.length} note="Detected by local Git" /><Metric label="MAPPED ENTITIES" value={gitImpact.mapped_entities.length} note="Entities in changed files" /><Metric label="POTENTIALLY AFFECTED" value={gitImpact.potentially_affected_dependents.length} note="Dependents in baseline graph" /></div>
              <ChangeResults items={gitImpact.changes} />
              <div className="two-column"><EntityResults title="Mapped entities" items={gitImpact.mapped_entities} /><EntityResults title="Potentially affected dependents" items={gitImpact.potentially_affected_dependents} /></div>
              <p className="footnote">Git impact is file-level: changed files map all of their baseline entities. New untracked files may have no baseline dependents.</p>
            </>}
          </>}
        </section>}
      </div>
    </main>
  </div>;
}

function PageHeading({ title, detail }: { title: string; detail: string }) {
  return <div className="page-heading"><div className="eyebrow">TRACEGRAPH ANALYSIS</div><h1>{title}</h1><p>{detail}</p></div>;
}
function Metric({ label, value, note }: { label: string; value: number; note: string }) {
  return <article className="metric"><small>{label}</small><b>{value.toLocaleString()}</b><span>{note}</span></article>;
}
function PanelHeading({ title, badge, action }: { title: string; badge?: string | number; action?: ReactNode }) {
  return <div className="panel-heading"><h3>{title}</h3><div>{badge !== undefined && <span className="badge">{badge}</span>}{action}</div></div>;
}
function Detail({ label, value, code = false }: { label: string; value: string; code?: boolean }) {
  return <div className="detail-row"><span>{label}</span>{code ? <code>{value}</code> : <span>{value}</span>}</div>;
}
function EntityPicker({ items, value, onChange }: { items: Entity[]; value: string; onChange: (id: string) => void }) {
  return <label className="entity-picker">ENTITY<select value={value} onChange={(event) => onChange(event.target.value)}>{items.map((entity) => <option key={entity.id} value={entity.id}>{entity.name} · {entity.file_path}:{entity.line_number}</option>)}</select></label>;
}
function EmptyState({ onAnalyze }: { onAnalyze: () => void }) {
  return <div className="empty-state"><span>⌘</span><h3>Analyze a repository first</h3><p>Analysis results will appear here when the repository scan is complete.</p><button className="secondary" onClick={onAnalyze}>Go to repository analysis →</button></div>;
}
function DependencyGraph({ selected, entities, relationships }: { selected: Entity | null; entities: Entity[]; relationships: Relationship[] }) {
  const graph = useMemo(() => {
    if (!selected) return { nodes: [] as Entity[], edges: [] as Relationship[] };
    const edges = relationships.filter((edge) => edge.source_id === selected.id || edge.target_id === selected.id);
    const ids = new Set([selected.id, ...edges.map((edge) => edge.source_id), ...edges.map((edge) => edge.target_id)]);
    const nodes = [...ids].map((id) => entities.find((entity) => entity.id === id)).filter((entity): entity is Entity => Boolean(entity)).slice(0, 25);
    const visibleIds = new Set(nodes.map((node) => node.id));
    return { nodes, edges: edges.filter((edge) => visibleIds.has(edge.source_id) && visibleIds.has(edge.target_id)) };
  }, [selected, entities, relationships]);
  const positions = graph.nodes.map((node, index) => node.id === selected?.id
    ? { x: 450, y: 230 }
    : { x: 450 + Math.cos((index / Math.max(graph.nodes.length, 1)) * Math.PI * 2 - Math.PI / 2) * 315,
        y: 230 + Math.sin((index / Math.max(graph.nodes.length, 1)) * Math.PI * 2 - Math.PI / 2) * 155 });
  const indexById = new Map(graph.nodes.map((node, index) => [node.id, index]));
  return <div className="graph-canvas"><svg viewBox="0 0 900 460" role="img" aria-label="Direct dependency graph">
    {graph.edges.map((edge, index) => {
      const from = positions[indexById.get(edge.source_id)!], to = positions[indexById.get(edge.target_id)!];
      return <g key={index}><line x1={from.x} y1={from.y} x2={to.x} y2={to.y} /><text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 5}>{edge.relationship_type}</text></g>;
    })}
    {graph.nodes.map((node, index) => <g key={node.id} className={node.id === selected?.id ? "graph-node focus" : "graph-node"} transform={`translate(${positions[index].x} ${positions[index].y})`}>
      <circle r={node.id === selected?.id ? 38 : 31} /><text className="node-name" y="-2">{node.name.length > 17 ? `${node.name.slice(0, 15)}…` : node.name}</text><text className="node-kind" y="13">{node.entity_type}</text>
    </g>)}
    {!graph.nodes.length && <text className="empty-graph" x="450" y="230">Select an entity to explore its connections</text>}
  </svg></div>;
}
