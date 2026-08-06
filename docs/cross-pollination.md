# Cross-pollination with Agent Hive

The accidental overlap produced a few useful ideas, but the projects now have a hard filesystem boundary.

| Idea | Agent Hive use | NESTRA use |
|---|---|---|
| Scoped memory | Optional worker context for coding missions | Core colony communication and retention model |
| Goals and hooks | Mission lifecycle and bounded repair | Queen control, stop conditions, and colony events |
| Guardrails and audit | Local orchestration safety | Retrieval, memory, and low-token acceptance safety |
| Role specialization | Provider workers compiled through HIVE/1 | Bio-inspired colony topology |

The two repositories currently keep independent implementations. Neither imports the other. If a shared contract becomes stable, it should be extracted later as a third, separately versioned package with compatibility tests. Prematurely sharing source files would recreate the coupling this split removes.
