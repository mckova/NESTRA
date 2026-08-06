# Memory model

Memory records are isolated by both `scope` and `namespace`.

| Scope | Typical lifetime | Examples |
|---|---|---|
| user | Cross-project when explicitly allowed | Stable preferences and accessibility settings |
| project | Across sessions | Stable conventions and verified domain facts |
| session | One user session | Preferences and temporary working context |
| mission | One goal | Queen instructions and final evidence |
| team | One role group | Shared retrieval evidence |
| agent | One worker attempt | Drafts and scratch state |

Recall also enforces role visibility, trust, sensitivity, status, score, and limit. Retention combines recency, confidence, relevance, source quality, verified utility, reuse, and sensitivity. Untrusted records start with reduced utility. Only verified successful use may reinforce a record.

Decay has three explicit outcomes: cool, archive, or delete. Mission/team/agent records are deleted at the end of the reference benchmark to prevent cross-question contamination. Applications decide when their corresponding scopes end and call deterministic decay or deletion explicitly.

## Project Memory compilation

The compiler creates one fact per source sentence. Every fact carries a deterministic ID, document ID, sentence position, content hash, source URI, trust, sensitivity, source quality, entity IDs, and project provenance. Entities and relations form a local recall index; they are not sent to a provider unless selected as evidence for a question.

Compiled facts can be hydrated into `ScopedMemory` under the `project` scope. The compiler defaults unknown sources to `untrusted`; controlled benchmark sources must opt into `trusted` explicitly.
