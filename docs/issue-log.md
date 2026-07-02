# Issue Log

## Mock GraphRAG ingestion benchmark

Status: blocked externally

Attempted command:

```powershell
gh issue create --repo TAVE-FitBack/AI --title "Implement mock GraphRAG ingestion benchmark" --body "..."
```

Result:

```text
GraphQL: Could not resolve to a Repository with the name 'TAVE-FitBack/AI'. (repository)
```

The local GitHub CLI is authenticated as `L-dragon-woo`, but `gh auth status` reports missing `repo` and `read:org` scopes. The available MCP GitHub issue search also failed with a repository visibility/permission error.

Retried after successfully pushing `feature/mock-graphrag-ingestion`:

```powershell
gh issue create --repo TAVE-FitBack/AI --title "Implement mock GraphRAG ingestion benchmark" --body "..."
```

Result:

```text
GraphQL: Could not resolve to a Repository with the name 'TAVE-FitBack/AI'. (repository)
```

`gh repo view TAVE-FitBack/AI --json nameWithOwner,url,viewerPermission` fails with the same GraphQL repository visibility error even though `git push` succeeds. This means the currently configured GitHub API token cannot read/create issues for this org repository.

Suggested issue body once GitHub CLI/API scopes are fixed:

```markdown
## Summary

Implement mock GraphRAG ingestion benchmarking for the Fitback AI repository.

## Done

- Added a Python CLI for deterministic mock store-management data generation.
- Added Neo4j AuraDB graph projection loading and verification.
- Added `.env.example` placeholders while keeping secrets in `.env` only.
- Added README handoff documentation for future AI agents and developers.
- Ignored local spreadsheet samples such as `상담메모_예시.xlsx`.

## Verification

- `python -m pytest -q` -> 2 passed
- `python -m fitback_ai generate --count 100 --output .omx\mock-data.json` -> generated 100 records
- `NEO4J_TRUST_SELF_SIGNED=true python -m fitback_ai smoke --count 100` -> passed

## Branch

`feature/mock-graphrag-ingestion`

## Commits

- `6ee851f` Enable AuraDB mock ingestion benchmarking
- `612c3b3` Keep consultation sample out of source history
- `584cc78` Document AI handoff for graph ingestion
```
