export const DEPENDENCY_RELATIONS = new Set(["supports", "evidence", "qualifies"]);

export function statementById(statements) {
  return new Map(statements.map((statement) => [statement.id, statement]));
}

export function policyStatements(statements) {
  return statements.filter((statement) => statement.layer === 4);
}

export function dependencyTraceIds(startId, statements, edges) {
  const byId = statementById(statements);
  if (!byId.has(startId)) return new Set();

  const outgoing = new Map();
  for (const edge of edges) {
    if (!DEPENDENCY_RELATIONS.has(edge.relation)) continue;
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
    outgoing.get(edge.source).push(edge.target);
  }

  const reached = new Set([startId]);
  const queue = [startId];
  while (queue.length > 0) {
    const current = queue.shift();
    const currentLayer = byId.get(current)?.layer ?? Number.POSITIVE_INFINITY;
    for (const target of outgoing.get(current) ?? []) {
      const targetStatement = byId.get(target);
      if (!targetStatement || reached.has(target)) continue;
      if (targetStatement.layer > currentLayer) continue;
      reached.add(target);
      queue.push(target);
    }
  }
  return reached;
}

export function visibleStatementsForView(statements, viewMode) {
  if (viewMode === "facts") {
    return statements.filter((statement) => statement.layer <= 2);
  }
  return statements;
}
