# Graph analysis — сводка

В графовую ветку включены только те слои, которые дополняют друг друга и не дублируются:

- `v17` — weighted current/optimized graph, path cost, bottlenecks, decision entropy.
- `v19` — внутренние action→feedback subgraph-ы для `WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION`, `WS-DIAGNOSTICS`.
- `v20` — workspace-subgraph-ы для `WS-PROJECT`, `WS-SUITE`, `WS-BASELINE`, `WS-ANALYSIS`, `WS-ANIMATOR` и cross-workspace return loops.
- `v21` — reconciliation current → canonical, direct tree open enforcement, triage launchpoint-only окон, route-cost rebalancing.

Таким образом, внутри этого раздела есть:
- path-cost и entropy слой;
- внутренние рабочие подграфы;
- межпространственные возвраты и repair loops;
- reconciliation слой между текущим состоянием и каноном.
