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
