---

## description: Analyze pending Git changes, generate a structured commit message, and create the commit safely.

# Git Commit

Analyze the current Git working tree and create a commit with a concise, structured commit message.

## Goal

Create a commit message in this format:

```text
<appdomain>: <short change description>

- <meaningful change 1>
- <meaningful change 2>
- <meaningful change 3>
```

Example:

```text
fin-reports: support Excel source metadata in GL tree

- Add Excel source metadata to GL tree transport models
- Propagate source information through the tree editor
- Align frontend types with the updated API contract
```

The bullets must describe meaningful changes, not merely list changed files.

## Workflow

### 1. Inspect repository state

First inspect the repository using Git.

At minimum examine:

```bash
git status --short
git diff --cached --stat
git diff --cached
git diff --stat
git diff
```

Also account for:

* added files;
* deleted files;
* renamed files;
* untracked files;
* staged changes;
* unstaged changes.

Do not infer the commit contents from the conversation alone. The Git index and working tree are the source of truth.

If there are no changes, report that there is nothing to commit and stop.

### 2. Determine what will be committed

Treat staged and unstaged changes separately.

#### Only staged changes exist

Use the staged changes as the commit scope.

Do not modify the index.

#### Staged AND unstaged changes exist

Do NOT automatically add the unstaged changes.

Summarize the situation and ask the user what to do.

Offer these choices:

1. **Commit staged only**
2. **Add all unstaged changes**
3. **Add selected unstaged files**

Show a compact list of staged and unstaged paths so the choice is understandable.

If the user chooses staged only, continue using only the current index.

If the user chooses all unstaged changes, stage them with the appropriate Git command and then re-read the staged diff.

If the user chooses selected files, ask which paths to add, stage only those paths, and then re-read the staged diff.

Never silently stage an unstaged file.

#### Only unstaged changes exist

There is currently nothing in the index to commit.

Show the changed/untracked paths and ask whether the user wants to:

1. stage all changes;
2. stage selected files;
3. cancel.

Do not stage anything without the user's choice.

### 3. Re-read the final staged state

After any staging operation, inspect the final commit contents again:

```bash
git status --short
git diff --cached --stat
git diff --cached
```

Generate the commit message ONLY from this final staged state.

Ignore remaining unstaged changes when describing the commit.

This rule is important: the commit message must describe exactly what is going into the commit.

### 4. Determine `<appdomain>`

Infer `appdomain` from the semantic ownership of the staged changes.

Prefer the narrowest stable application/domain name that makes sense in the repository.

For example, prefer:

```text
fin-reports
market-data
liquidity
calc-service
core-service
web
ui
infra
openspec
docs
```

over vague scopes such as:

```text
frontend
backend
changes
misc
code
```

When the repository structure exposes a business/module domain, prefer that domain over the technical layer.

For example:

```text
frontend/web/src/modules/fin-reports/...
```

should normally produce:

```text
fin-reports: ...
```

rather than:

```text
web: ...
```

If several files belong to the same semantic feature even though they cross technical layers, use that feature/domain when it is clear.

If the changes genuinely span unrelated application domains and there is no meaningful common domain, use:

```text
repo
```

Do not invent a domain that is not supported by the repository structure or the changed code.

### 5. Generate the short description

The header must be:

```text
<appdomain>: <short change description>
```

Requirements:

* one line;
* concise;
* describe the main intent of the commit;
* normally use an imperative/action-oriented description;
* do not end with a period;
* do not use generic descriptions such as `update files`, `changes`, `fix stuff`, or `misc changes`;
* do not duplicate the bullet list.

Good:

```text
fin-reports: align GL tree with Excel source metadata
calc-service: isolate S3 TLS configuration
openspec: simplify repository documentation policy
```

Bad:

```text
frontend: updates
repo: various changes
web: fix files
```

### 6. Generate the bullet list

After the header, add a blank line followed by a bulleted summary.

Example:

```text
fin-reports: align GL tree with Excel source metadata

- Extend GL tree models with Excel source information
- Propagate source metadata through editor transformations
- Update API mappings to match generated transport types
```

Rules:

* normally produce 2-6 bullets;
* group related file-level changes into semantic changes;
* describe WHAT changed;
* mention WHY only when it is apparent from the code;
* avoid implementation trivia unless it materially affects behavior;
* do not make claims unsupported by the diff;
* do not list filenames unless the filename itself is important;
* do not mention unstaged changes that are not part of the commit.

A single bullet is acceptable for a genuinely small commit.

### 7. Review before committing

Before executing `git commit`, verify that:

* the staged diff is not empty;
* the header matches the staged changes;
* every bullet is supported by the staged diff;
* no bullet describes remaining unstaged changes;
* `<appdomain>` represents the actual change scope;
* no accidental generated files, credentials, secrets, binaries, or obviously unrelated files appear in the staged set.

If something suspicious or clearly unrelated is staged, stop and ask the user rather than silently committing it.

### 8. Create the commit

Commit the final staged state using the generated message.

Preserve the exact multiline structure:

```text
<appdomain>: <short change description>

- change
- change
- change
```

Do not:

* amend an existing commit;
* push;
* rebase;
* reset unrelated changes;
* discard working-tree changes;
* stage additional files after the commit message has been generated.

After committing, verify the result with:

```bash
git status --short
git log -1 --oneline
```

Report:

* the created commit hash and header;
* whether any unstaged/untracked changes remain.

Do not create another commit automatically.
