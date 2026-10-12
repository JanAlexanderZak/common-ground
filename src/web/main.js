// Surface uncaught runtime errors visibly in #root so a silent React-mount
// failure doesn't look like a blank page. (Won't catch import-resolution
// failures - those happen before this module body runs; check dev tools.)
window.addEventListener("error", (e) => {
  const root = document.getElementById("root");
  if (root && !root.firstChild) {
    root.innerHTML = `<pre style="padding:1rem;color:#b91c1c;background:#fef2f2;white-space:pre-wrap;font:13px monospace">Error: ${e.message}\n${e.filename}:${e.lineno}:${e.colno}\n${e.error?.stack ?? ""}</pre>`;
  }
});
window.addEventListener("unhandledrejection", (e) => {
  const root = document.getElementById("root");
  if (root && !root.firstChild) {
    root.innerHTML = `<pre style="padding:1rem;color:#b91c1c;background:#fef2f2;white-space:pre-wrap;font:13px monospace">Unhandled: ${e.reason?.message ?? e.reason}\n${e.reason?.stack ?? ""}</pre>`;
  }
});

import { useCallback, useMemo, useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react";
import { html } from "htm/react";
import {
  dependencyTraceIds,
  policyStatements,
  statementById,
  visibleStatementsForView,
} from "./graph-utils.js";

const LAYER_NAMES = {
  0: "L0 - Empirical fact",
  1: "L1 - Stylized fact",
  2: "L2 - Causal mechanism",
  3: "L3 - Value claim",
  4: "L4 - Policy position",
};

const LAYER_CLASSES = {
  0: "bg-stone-50 border-stone-400 text-stone-900",
  1: "bg-slate-50 border-slate-400 text-slate-900",
  2: "bg-cyan-50 border-cyan-400 text-cyan-900",
  3: "bg-purple-50 border-purple-400 text-purple-900",
  4: "bg-indigo-50 border-indigo-400 text-indigo-900",
};

const VIEW_OPTIONS = [
  { id: "all", label: "All" },
  { id: "facts", label: "Facts & mechanisms" },
];

const RELATION_STYLES = {
  supports: { stroke: "#16a34a", strokeWidth: 2 },
  attacks: { stroke: "#dc2626", strokeWidth: 2, strokeDasharray: "6 3" },
  "attacked-by": { stroke: "#dc2626", strokeWidth: 2, strokeDasharray: "6 3" },
  evidence: { stroke: "#0284c7", strokeWidth: 2 },
  qualifies: { stroke: "#7c3aed", strokeWidth: 1.5, strokeDasharray: "2 2" },
};

const DEFAULT_RELATION_STYLE = { stroke: "#6b7280", strokeWidth: 1.5 };
const COMPOSITE_RELATION_STYLE = {
  stroke: "#111827",
  strokeWidth: 2,
  strokeDasharray: "4 3",
};

const NODE_W = 280;
const NODE_H = 112;
const COL_GAP = 220;
const ROW_GAP = 140;
const BAND_X_CLAMP = 60;
const Y_JITTER = 10;
const BAND_CENTER = {
  0: 0,
  1: NODE_W + COL_GAP,
  2: 2 * (NODE_W + COL_GAP),
  3: 3 * (NODE_W + COL_GAP),
  4: 4 * (NODE_W + COL_GAP),
};

function actorBadges(ids, kind) {
  if (!ids?.length) return null;
  const className =
    kind === "endorsed"
      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
      : "bg-rose-50 text-rose-800 border-rose-200";
  const prefix = kind === "endorsed" ? "+" : "-";
  return html`
    <div class="flex flex-wrap gap-1">
      ${ids.map(
        (id) => html`
          <span
            key=${`${kind}-${id}`}
            class="inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium ${className}"
          >
            ${prefix}@${id}
          </span>
        `,
      )}
    </div>
  `;
}

function StatementNode({ data }) {
  const layerClass = LAYER_CLASSES[data.layer] || "bg-white border-gray-400";
  const layerName = LAYER_NAMES[data.layer] || `L${data.layer}`;
  const isSelected = data._isSelected;
  const isFaded = data._traceActive && !data._inTrace;
  const selectedClass = isSelected
    ? "ring-2 ring-blue-500 ring-offset-1"
    : "";
  const fadeClass = isFaded ? "opacity-20" : "";
  const sourceCount = data.sources?.length ?? 0;
  const dataCount = data.data_refs?.length ?? 0;

  return html`
    <div
      class="rounded border-2 ${layerClass} shadow-sm p-3 ${selectedClass} ${fadeClass} relative transition-opacity"
      style=${{ width: NODE_W, minHeight: NODE_H }}
    >
      <${Handle} id="L-t" type="target" position=${Position.Left}
        style=${{ top: "20%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="L-m" type="target" position=${Position.Left}
        style=${{ top: "50%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="L-b" type="target" position=${Position.Left}
        style=${{ top: "80%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="R-t" type="source" position=${Position.Right}
        style=${{ top: "20%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="R-m" type="source" position=${Position.Right}
        style=${{ top: "50%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="R-b" type="source" position=${Position.Right}
        style=${{ top: "80%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="T-s" type="source" position=${Position.Top}
        style=${{ left: "30%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="T-t" type="target" position=${Position.Top}
        style=${{ left: "70%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="B-s" type="source" position=${Position.Bottom}
        style=${{ left: "30%", opacity: 0, background: "transparent", border: "none" }} />
      <${Handle} id="B-t" type="target" position=${Position.Bottom}
        style=${{ left: "70%", opacity: 0, background: "transparent", border: "none" }} />

      <div class="text-[10px] uppercase tracking-wide opacity-70 mb-1">
        ${layerName} - ${data.id}
      </div>
      <div
        class="text-sm font-medium leading-snug overflow-hidden"
        style=${{
          display: "-webkit-box",
          WebkitLineClamp: 3,
          WebkitBoxOrient: "vertical",
        }}
      >
        ${data.text}
      </div>
      <div class="mt-2 flex flex-wrap gap-1">
        ${sourceCount > 0 &&
        html`
          <span class="rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-800">
            ${sourceCount} ${sourceCount === 1 ? "source" : "sources"}
          </span>
        `}
        ${dataCount > 0 &&
        html`
          <span class="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-700">
            data
          </span>
        `}
        ${(data.endorsed_by?.length ?? 0) > 0 &&
        html`
          <span class="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800">
            +${data.endorsed_by.length}
          </span>
        `}
        ${(data.disputed_by?.length ?? 0) > 0 &&
        html`
          <span class="rounded border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-800">
            -${data.disputed_by.length}
          </span>
        `}
      </div>
    </div>
  `;
}

const NODE_TYPES = { statement: StatementNode };

function hashFloat(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h * 31) + s.charCodeAt(i)) | 0;
  return ((h % 1000) + 1000) % 1000 / 1000;
}

function applyLayout(nodes, edges) {
  const byLayer = { 0: [], 1: [], 2: [], 3: [], 4: [] };
  for (const node of nodes) {
    const layer = node.data.layer;
    if (byLayer[layer]) byLayer[layer].push(node);
  }

  const yCenterById = new Map();
  const positioned = [];
  const stride = NODE_H + ROW_GAP;

  for (const layer of [0, 1, 2, 3, 4]) {
    const group = byLayer[layer];
    if (group.length === 0) continue;

    if (layer > 0) {
      for (const node of group) {
        const lefts = edges
          .filter((edge) => edge.target === node.id)
          .map((edge) => yCenterById.get(edge.source))
          .filter((y) => y !== undefined);
        node._sortKey =
          lefts.length > 0
            ? lefts.reduce((a, b) => a + b, 0) / lefts.length
            : 0;
      }
      group.sort((a, b) => a._sortKey - b._sortKey);
    }

    const totalHeight = group.length * stride - ROW_GAP;
    const startY = -totalHeight / 2;
    group.forEach((node, index) => {
      const yJit = (hashFloat(node.id) * 2 - 1) * Y_JITTER;
      const y = startY + index * stride + yJit;
      yCenterById.set(node.id, y + NODE_H / 2);
      positioned.push({
        ...node,
        position: { x: BAND_CENTER[layer], y },
      });
    });
  }

  const xById = new Map(positioned.map((node) => [node.id, node.position.x]));
  const neighborsById = new Map();
  for (const node of positioned) neighborsById.set(node.id, []);
  for (const edge of edges) {
    if (neighborsById.has(edge.source) && neighborsById.has(edge.target)) {
      neighborsById.get(edge.source).push(edge.target);
      neighborsById.get(edge.target).push(edge.source);
    }
  }

  for (const node of positioned) {
    const neighbors = neighborsById.get(node.id);
    if (!neighbors || neighbors.length === 0) continue;
    const avgNeighborX =
      neighbors.reduce((sum, id) => sum + (xById.get(id) ?? 0), 0) /
      neighbors.length;
    const center = BAND_CENTER[node.data.layer];
    const dx = avgNeighborX - center;
    const offset = Math.max(-BAND_X_CLAMP, Math.min(BAND_X_CLAMP, dx * 0.4));
    node.position = { x: center + offset, y: node.position.y };
  }

  return positioned;
}

function groupByRelation(edges) {
  const groups = new Map();
  for (const edge of edges) {
    if (!groups.has(edge.relation)) groups.set(edge.relation, []);
    groups.get(edge.relation).push(edge);
  }
  return groups;
}

function TopicHeader({ graph, visibleCount, visibleEdges }) {
  const meta = graph.metadata || {};
  const totalStatements = graph.statements.length;
  const totalEdges = graph.derived?.edge_pairs?.length || graph.edges.length;
  const statementSummary =
    visibleCount === totalStatements
      ? `${totalStatements} statements`
      : `${visibleCount}/${totalStatements} statements`;
  const edgeSummary =
    visibleEdges === totalEdges ? `${totalEdges} edges` : `${visibleEdges}/${totalEdges} edges`;

  return html`
    <header class="border-b border-slate-200 bg-white px-4 py-3">
      <div class="flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 class="text-base font-semibold text-slate-950">
            ${meta.title || meta.topic || "Topic"}
          </h1>
          <div class="text-xs text-slate-500">
            ${statementSummary} - ${edgeSummary}${meta.language
              ? html` - ${meta.language}`
              : null}
          </div>
        </div>
        <div class="text-xs font-medium text-slate-500">
          Policy-first reference viewer
        </div>
      </div>
    </header>
  `;
}

function ViewControls({ viewMode, onViewModeChange, legendOpen, onToggleLegend }) {
  return html`
    <div class="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2">
      <div class="flex gap-1 rounded border border-slate-200 bg-white p-1">
        ${VIEW_OPTIONS.map((option) => {
          const active = viewMode === option.id;
          return html`
            <button
              key=${option.id}
              type="button"
              aria-pressed=${active}
              onClick=${() => onViewModeChange(option.id)}
              class="rounded px-2.5 py-1 text-xs font-medium transition-colors ${active
                ? "bg-slate-950 text-white"
                : "text-slate-700 hover:bg-slate-100"}"
            >
              ${option.label}
            </button>
          `;
        })}
      </div>
      <button
        type="button"
        aria-pressed=${legendOpen}
        onClick=${onToggleLegend}
        class="rounded border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
      >
        Legend
      </button>
    </div>
  `;
}

function PolicyRail({ policies, selectedId, onSelectPolicy }) {
  return html`
    <aside class="border-b border-slate-200 bg-white md:w-80 md:shrink-0 md:border-b-0 md:border-r">
      <div class="px-4 py-3">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Policy positions
        </div>
        <div class="mt-2 flex gap-2 overflow-x-auto pb-1 md:block md:space-y-2 md:overflow-visible md:pb-0">
          ${policies.map((policy) => {
            const active = policy.id === selectedId;
            return html`
              <button
                key=${policy.id}
                type="button"
                onClick=${() => onSelectPolicy(policy.id)}
                class="w-72 shrink-0 rounded border p-3 text-left transition-colors md:w-full ${active
                  ? "border-indigo-400 bg-indigo-50"
                  : "border-slate-200 bg-white hover:bg-slate-50"}"
              >
                <div class="text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                  ${policy.id}
                </div>
                <div class="mt-1 text-sm font-medium leading-snug text-slate-950">
                  ${policy.text}
                </div>
                <div class="mt-2 space-y-1">
                  ${actorBadges(policy.endorsed_by, "endorsed")}
                  ${actorBadges(policy.disputed_by, "disputed")}
                </div>
              </button>
            `;
          })}
        </div>
      </div>
    </aside>
  `;
}

function ManifestSection({ title, groups, side, statementsById, onSelectId }) {
  if (groups.size === 0) return null;
  return html`
    <section class="mt-4">
      <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">
        ${title}
      </h3>
      ${[...groups.entries()].map(
        ([relation, list]) => html`
          <div key=${relation} class="mt-1 text-sm">
            <span class="text-slate-500">${relation}:</span>
            ${list.map((edge, index) => {
              const otherId = side === "out" ? edge.target : edge.source;
              const other = statementsById.get(otherId);
              const layerClass = LAYER_CLASSES[other?.layer] || "bg-slate-100";
              const parts = layerClass.split(" ");
              return html`
                <button
                  key=${otherId + index}
                  type="button"
                  onClick=${() => onSelectId(otherId)}
                  title=${other?.text ?? otherId}
                  class="ml-1 mb-1 inline-block rounded border px-2 py-0.5 text-xs hover:opacity-80 ${parts[0]} ${parts[1]} ${parts[2]}"
                >
                  ${otherId}
                </button>
              `;
            })}
          </div>
        `,
      )}
    </section>
  `;
}

function SourceSection({ statement }) {
  if (statement.sources.length === 0) return null;
  return html`
    <section class="mt-4">
      <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Sources
      </h3>
      <div class="mt-1 space-y-2">
        ${statement.sources.map(
          (source, index) => html`
            <div key=${index} class="rounded border border-blue-100 bg-blue-50 p-2 text-sm">
              ${source.url
                ? html`
                    <a
                      href=${source.url}
                      target="_blank"
                      rel="noreferrer"
                      class="font-medium text-blue-800 underline"
                    >
                      ${source.label || source.url}
                    </a>
                  `
                : html`<span class="font-medium">${source.label}</span>`}
              <div class="mt-1 text-xs text-slate-600">
                ${source.source_type || "source"}${source.retrieved
                  ? html` - retrieved ${source.retrieved}`
                  : null}${source.jurisdiction
                  ? html` - ${source.jurisdiction}`
                  : null}
              </div>
            </div>
          `,
        )}
      </div>
    </section>
  `;
}

function DataSection({ statement }) {
  if (statement.data_refs.length === 0) return null;
  return html`
    <section class="mt-4">
      <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Data
      </h3>
      <div class="mt-1 space-y-2">
        ${statement.data_refs.map(
          (ref, index) => html`
            <div key=${index} class="rounded border border-slate-200 bg-slate-50 p-2 text-sm">
              <div class="font-medium text-slate-900">
                ${ref.label || ref.path}
              </div>
              ${ref.description &&
              html`
                <div class="mt-1 text-xs text-slate-600">
                  ${ref.description}
                </div>
              `}
            </div>
          `,
        )}
      </div>
    </section>
  `;
}

function DetailsPanel({
  statement,
  edges,
  statementsById,
  traceActive,
  onSelectId,
  onToggleTrace,
  onClose,
}) {
  if (!statement) return null;
  const layerName = LAYER_NAMES[statement.layer] || `L${statement.layer}`;
  const outgoing = edges.filter((edge) => edge.source === statement.id);
  const incoming = edges.filter((edge) => edge.target === statement.id);
  const buildsOn = groupByRelation(outgoing);
  const usedBy = groupByRelation(incoming);
  const evidenceFirst = statement.layer <= 1;

  return html`
    <aside class="fixed inset-0 z-20 overflow-y-auto border-l border-slate-200 bg-white shadow-xl md:static md:w-96 md:shrink-0 md:shadow-none">
      <div class="p-4">
        <button
          onClick=${onClose}
          aria-label="Close"
          class="float-right rounded px-2 py-1 text-xl leading-none text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        >
          x
        </button>
        <div class="text-xs uppercase tracking-wide text-slate-500">
          ${layerName} - ${statement.id}
        </div>
        <h2 class="mt-1 text-base font-semibold leading-snug text-slate-950">
          ${statement.text}
        </h2>

        ${evidenceFirst && html`<${SourceSection} statement=${statement} />`}
        ${evidenceFirst && html`<${DataSection} statement=${statement} />`}

        <button
          type="button"
          aria-pressed=${traceActive}
          onClick=${onToggleTrace}
          class="mt-4 w-full rounded border px-3 py-2 text-sm font-medium transition-colors ${traceActive
            ? "border-blue-600 bg-blue-600 text-white"
            : "border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100"}"
        >
          ${traceActive ? "Clear trace" : "Trace dependencies"}
        </button>

        ${!evidenceFirst && html`<${SourceSection} statement=${statement} />`}
        ${!evidenceFirst && html`<${DataSection} statement=${statement} />`}

        ${(statement.endorsed_by.length > 0 || statement.disputed_by.length > 0) &&
        html`
          <section class="mt-4">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Actors
            </h3>
            <div class="mt-1 space-y-1">
              ${actorBadges(statement.endorsed_by, "endorsed")}
              ${actorBadges(statement.disputed_by, "disputed")}
            </div>
          </section>
        `}

        <${ManifestSection}
          title="Builds on"
          groups=${buildsOn}
          side="out"
          statementsById=${statementsById}
          onSelectId=${onSelectId}
        />
        <${ManifestSection}
          title="Used by"
          groups=${usedBy}
          side="in"
          statementsById=${statementsById}
          onSelectId=${onSelectId}
        />
      </div>
    </aside>
  `;
}

function uniqueRelations(values) {
  return [...new Set(values.filter(Boolean))];
}

function relationValues(values, fallback) {
  if (Array.isArray(values) && values.length > 0) {
    return uniqueRelations(values);
  }
  return fallback ? [fallback] : [];
}

function edgePairRelationValues(edgePair) {
  return uniqueRelations([
    ...relationValues(edgePair.relations, edgePair.relation),
    ...relationValues(edgePair.inverseRelations, edgePair.inverseRelation),
  ]);
}

function edgePairLabel(edgePair) {
  const forward = relationValues(edgePair.relations, edgePair.relation);
  const reverse = relationValues(
    edgePair.inverseRelations,
    edgePair.inverseRelation,
  );
  const forwardLabel = forward.join(" / ") || edgePair.relation || "relation";
  if (!edgePair.mutual) return forwardLabel;

  const reverseLabel = reverse.join(" / ");
  return reverseLabel ? `${forwardLabel} <-> ${reverseLabel}` : `${forwardLabel} <->`;
}

function styleKey(style) {
  return [
    style.stroke,
    style.strokeWidth,
    style.strokeDasharray || "",
  ].join("|");
}

function edgePairStyle(edgePair) {
  const styles = edgePairRelationValues(edgePair)
    .map((relation) => RELATION_STYLES[relation])
    .filter(Boolean);
  if (styles.length === 0) return DEFAULT_RELATION_STYLE;

  const styleKeys = new Set(styles.map(styleKey));
  return styleKeys.size === 1 ? styles[0] : COMPOSITE_RELATION_STYLE;
}

function relationLine(relation) {
  const style = RELATION_STYLES[relation] || DEFAULT_RELATION_STYLE;
  return html`
    <svg width="32" height="6" viewBox="0 0 32 6">
      <line
        x1="0"
        y1="3"
        x2="28"
        y2="3"
        stroke=${style.stroke}
        strokeWidth=${style.strokeWidth}
        strokeDasharray=${style.strokeDasharray || ""}
      />
      <polygon points="32,3 27,1 27,5" fill=${style.stroke} />
    </svg>
  `;
}

function Legend({ hasMutual }) {
  return html`
    <div class="rounded border border-slate-200 bg-white p-3 text-xs shadow space-y-1.5">
      <div class="font-semibold">Layers</div>
      ${[0, 1, 2, 3, 4].map((layer) => {
        const parts = LAYER_CLASSES[layer].split(" ");
        return html`
          <div key=${layer} class="flex items-center gap-2">
            <div class="h-3 w-4 rounded border ${parts[0]} ${parts[1]}"></div>
            <span>${LAYER_NAMES[layer]}</span>
          </div>
        `;
      })}
      <div class="border-t border-slate-200 my-2"></div>
      <div class="font-semibold">Connections</div>
      ${["supports", "evidence", "qualifies", "attacks"].map(
        (relation) => html`
          <div key=${relation} class="flex items-center gap-2">
            ${relationLine(relation)}
            <span>${relation}</span>
          </div>
        `,
      )}
      ${hasMutual &&
      html`
        <div class="flex items-center gap-2">
          <span class="inline-block w-8 text-center">${"<->"}</span>
          <span class="text-slate-600">mutual</span>
        </div>
      `}
    </div>
  `;
}

function GraphCanvas({
  graph,
  visibleStatements,
  visibleStatementIds,
  edgePairs,
  statementsById,
  selectedId,
  traceSet,
  legendOpen,
  onSelectId,
  onClearSelection,
}) {
  const hasMutual = useMemo(
    () => edgePairs.some((edgePair) => edgePair.mutual),
    [edgePairs],
  );

  const { nodes, edges } = useMemo(() => {
    const initialNodes = visibleStatements.map((statement) => {
      const inTrace = traceSet ? traceSet.has(statement.id) : true;
      return {
        id: statement.id,
        type: "statement",
        data: {
          ...statement,
          _isSelected: statement.id === selectedId,
          _inTrace: inTrace,
          _traceActive: !!traceSet,
        },
        position: { x: 0, y: 0 },
      };
    });

    const visibleEdgePairs = edgePairs.filter(
      (edgePair) =>
        visibleStatementIds.has(edgePair.source) &&
        visibleStatementIds.has(edgePair.target),
    );

    const visualEdges = visibleEdgePairs.map((edgePair, index) => {
      const sourceLayer = statementsById.get(edgePair.source)?.layer ?? 0;
      const targetLayer = statementsById.get(edgePair.target)?.layer ?? 0;
      const flip = sourceLayer > targetLayer;
      const visualSource = flip ? edgePair.target : edgePair.source;
      const visualTarget = flip ? edgePair.source : edgePair.target;
      const baseStyle = edgePairStyle(edgePair);
      const inTrace = traceSet
        ? traceSet.has(edgePair.source) && traceSet.has(edgePair.target)
        : true;
      const opacity = traceSet ? (inTrace ? 1 : 0.12) : 1;
      const marker = {
        type: MarkerType.ArrowClosed,
        color: baseStyle.stroke,
        width: 18,
        height: 18,
      };
      return {
        id: `${edgePair.source}->${edgePair.target}-${index}`,
        source: visualSource,
        target: visualTarget,
        _sameBand: sourceLayer === targetLayer,
        type: "smoothstep",
        pathOptions: { offset: 24, borderRadius: 12 },
        label: edgePairLabel(edgePair),
        style: { ...baseStyle, opacity },
        markerEnd: marker,
        markerStart: edgePair.mutual ? marker : undefined,
        labelStyle: { fontSize: 10, fill: "#334155", opacity },
        labelBgStyle: { fill: "white", fillOpacity: 0.9 * opacity },
        labelBgPadding: [4, 2],
        labelBgBorderRadius: 2,
      };
    });

    const positionedNodes = applyLayout(initialNodes, visualEdges);
    const posById = new Map(
      positionedNodes.map((node) => [node.id, node.position]),
    );

    const edgesWithHandles = visualEdges.map((edge) => {
      const sourcePosition = posById.get(edge.source);
      const targetPosition = posById.get(edge.target);
      if (!sourcePosition || !targetPosition) return edge;
      const sourceCy = sourcePosition.y + NODE_H / 2;
      const targetCy = targetPosition.y + NODE_H / 2;
      const dy = targetCy - sourceCy;
      let sourceHandle;
      let targetHandle;
      if (edge._sameBand) {
        if (dy >= 0) {
          sourceHandle = "B-s";
          targetHandle = "T-t";
        } else {
          sourceHandle = "T-s";
          targetHandle = "B-t";
        }
      } else {
        const threshold = NODE_H * 0.6;
        if (dy > threshold) {
          sourceHandle = "R-b";
          targetHandle = "L-t";
        } else if (dy < -threshold) {
          sourceHandle = "R-t";
          targetHandle = "L-b";
        } else {
          sourceHandle = "R-m";
          targetHandle = "L-m";
        }
      }
      const { _sameBand, ...rest } = edge;
      return { ...rest, sourceHandle, targetHandle };
    });

    return { nodes: positionedNodes, edges: edgesWithHandles };
  }, [
    edgePairs,
    selectedId,
    statementsById,
    traceSet,
    visibleStatementIds,
    visibleStatements,
  ]);

  return html`
    <section class="min-h-[420px] flex-1 md:min-h-0">
      <${ReactFlow}
        nodes=${nodes}
        edges=${edges}
        nodeTypes=${NODE_TYPES}
        onNodeClick=${(_, node) => onSelectId(node.id)}
        onPaneClick=${onClearSelection}
        defaultViewport=${{ x: 120, y: 320, zoom: 0.42 }}
        proOptions=${{ hideAttribution: true }}
        minZoom=${0.15}
        maxZoom=${2}
      >
        <${Background} />
        <${Controls} />
        <${MiniMap} pannable zoomable />
        ${legendOpen &&
        html`
          <${Panel} position="bottom-left">
            <${Legend} hasMutual=${hasMutual} />
          <//>
        `}
      <//>
    </section>
  `;
}

function App() {
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [traceId, setTraceId] = useState(null);
  const [viewMode, setViewMode] = useState("all");
  const [legendOpen, setLegendOpen] = useState(false);

  useEffect(() => {
    fetch("./topic.json")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status} fetching topic.json`);
        return response.json();
      })
      .then(setGraph)
      .catch((e) => setError(e.message));
  }, []);

  const statementsById = useMemo(() => {
    if (!graph) return new Map();
    return statementById(graph.statements);
  }, [graph]);

  const policies = useMemo(() => {
    if (!graph) return [];
    return policyStatements(graph.statements);
  }, [graph]);

  const edgePairs = graph?.derived?.edge_pairs ?? [];

  const visibleStatements = useMemo(() => {
    if (!graph) return [];
    return visibleStatementsForView(graph.statements, viewMode);
  }, [graph, viewMode]);

  const visibleStatementIds = useMemo(
    () => new Set(visibleStatements.map((statement) => statement.id)),
    [visibleStatements],
  );

  const selectedStatement = useMemo(() => {
    if (!graph || !selectedId) return null;
    return statementsById.get(selectedId) ?? null;
  }, [graph, selectedId, statementsById]);

  const traceSet = useMemo(() => {
    if (!graph || !traceId) return null;
    return dependencyTraceIds(traceId, graph.statements, graph.edges);
  }, [graph, traceId]);

  useEffect(() => {
    if (selectedId && !visibleStatementIds.has(selectedId)) {
      setSelectedId(null);
      setTraceId(null);
    }
  }, [selectedId, visibleStatementIds]);

  const visibleEdgeCount = useMemo(
    () =>
      edgePairs.filter(
        (edgePair) =>
          visibleStatementIds.has(edgePair.source) &&
          visibleStatementIds.has(edgePair.target),
      ).length,
    [edgePairs, visibleStatementIds],
  );

  const selectStatement = useCallback((statementId) => {
    setSelectedId(statementId);
    setTraceId((currentTraceId) =>
      currentTraceId === statementId ? currentTraceId : null,
    );
  }, []);

  const selectPolicy = useCallback((statementId) => {
    setViewMode("all");
    setSelectedId(statementId);
    setTraceId((currentTraceId) =>
      currentTraceId === statementId ? currentTraceId : null,
    );
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedId(null);
    setTraceId(null);
  }, []);

  const toggleTrace = useCallback(() => {
    if (!selectedId) return;
    setTraceId((currentTraceId) =>
      currentTraceId === selectedId ? null : selectedId,
    );
  }, [selectedId]);

  if (error) {
    return html`
      <div class="h-full bg-red-50 p-6 text-red-700">
        <div class="mb-2 font-semibold">Failed to load topic.json</div>
        <div class="text-sm">${error}</div>
        <div class="mt-4 text-sm text-slate-700">
          Run
          <code class="bg-white px-1"
            >uv run python build.py &lt;topic-path&gt; web/topic.json</code
          >
          from the project root, then serve
          <code class="bg-white px-1">web/</code> via
          <code class="bg-white px-1">python -m http.server</code>.
        </div>
      </div>
    `;
  }

  if (!graph) {
    return html`<div class="p-6 text-slate-500">Loading...</div>`;
  }

  return html`
    <div class="flex h-full overflow-hidden flex-col bg-slate-100 text-slate-900">
      <${TopicHeader}
        graph=${graph}
        visibleCount=${visibleStatements.length}
        visibleEdges=${visibleEdgeCount}
      />
      <${ViewControls}
        viewMode=${viewMode}
        onViewModeChange=${setViewMode}
        legendOpen=${legendOpen}
        onToggleLegend=${() => setLegendOpen((current) => !current)}
      />
      <main class="flex min-h-0 flex-1 flex-col md:flex-row">
        <${PolicyRail}
          policies=${policies}
          selectedId=${selectedId}
          onSelectPolicy=${selectPolicy}
        />
        <${GraphCanvas}
          graph=${graph}
          visibleStatements=${visibleStatements}
          visibleStatementIds=${visibleStatementIds}
          edgePairs=${edgePairs}
          statementsById=${statementsById}
          selectedId=${selectedId}
          traceSet=${traceSet}
          legendOpen=${legendOpen}
          onSelectId=${selectStatement}
          onClearSelection=${clearSelection}
        />
        <${DetailsPanel}
          statement=${selectedStatement}
          edges=${graph.edges}
          statementsById=${statementsById}
          traceActive=${traceId === selectedId}
          onSelectId=${selectStatement}
          onToggleTrace=${toggleTrace}
          onClose=${clearSelection}
        />
      </main>
    </div>
  `;
}

const root = createRoot(document.getElementById("root"));
root.render(html`<${App} />`);
