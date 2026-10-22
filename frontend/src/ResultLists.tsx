import { useMemo, useState } from "react";
import type { Entity, GitImpact } from "./api";

type Change = GitImpact["changes"][number];

export function EntityResults({ title, items }: { title: string; items: Entity[] }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return items;
    return items.filter((entity) =>
      `${entity.name} ${entity.entity_type} ${entity.file_path}`.toLocaleLowerCase().includes(normalized));
  }, [items, query]);

  return <article className="panel result-panel">
    <details open>
      <summary className="result-summary"><span>{title}</span><span className="badge">{items.length}</span><span className="collapse-hint">⌄</span></summary>
      {items.length > 0 && <ResultFilter label={`Filter ${title.toLocaleLowerCase()}`} value={query} onChange={setQuery} />}
      {filtered.length ? filtered.map((entity) => <div className="entity-row" key={entity.id}>
        <span className="entity-kind">{entity.entity_type.slice(0, 1)}</span>
        <div><b>{entity.name}</b><small>{entity.file_path}:{entity.line_number}</small></div>
      </div>) : <p className="muted center">{items.length ? "No matching entities." : "No entities found."}</p>}
      {query && filtered.length > 0 && <p className="result-count">Showing {filtered.length} of {items.length}</p>}
    </details>
  </article>;
}

export function ChangeResults({ items }: { items: Change[] }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return items;
    return items.filter((change) =>
      `${change.path} ${change.old_path ?? ""} ${change.change_type}`.toLocaleLowerCase().includes(normalized));
  }, [items, query]);

  return <article className="panel result-panel">
    <details open>
      <summary className="result-summary"><span>Changed files</span><span className="badge">{items.length}</span><span className="collapse-hint">⌄</span></summary>
      {items.length > 0 && <ResultFilter label="Filter changed files" value={query} onChange={setQuery} />}
      {filtered.length ? filtered.map((change, index) => <div className="change-row" key={`${change.path}-${index}`}>
        <span className="change-type">{change.change_type}</span><code>{change.path}</code>
        {change.old_path && <small>from {change.old_path}</small>}
      </div>) : <p className="muted center">{items.length ? "No matching files." : "No changed files found for these refs."}</p>}
      {query && filtered.length > 0 && <p className="result-count">Showing {filtered.length} of {items.length}</p>}
    </details>
  </article>;
}

function ResultFilter({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="result-filter"><span>{label}</span><input type="search" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Type to filter…" /></label>;
}
