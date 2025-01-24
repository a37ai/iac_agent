---
tool: git
category: version_control
version: "2.40"
topics:
  - commands
  - branching
  - merging
---
# Git Basic Operations

## Common Operations

### Repository Management
```bash
# Initialize repository
git init

# Clone repository
git clone https://github.com/user/repo.git

# Add and commit
git add .
git commit -m "Initial commit"
```

## Common Issues and Solutions

### Error: Authentication Failed
```error
fatal: Authentication failed for 'https://github.com/user/repo.git'
```

Solution:
1. Configure credentials:
```bash
git config --global credential.helper store
```

2. Use SSH:
```bash
git remote set-url origin git@github.com:user/repo.git
```

3. Generate token:
```bash
# Store GitHub token
git config --global credential.helper 'store --file ~/.git-credentials'
```

### Error: Merge Conflict
```error
CONFLICT (content): Merge conflict in file.txt
```

Solution:
1. Check status:
```bash
git status
```

2. Resolve conflicts:
```bash
git checkout --ours file.txt
# or
git checkout --theirs file.txt
```

3. Complete merge:
```bash
git add file.txt
git commit -m "Resolve merge conflict"
```

### Error: Large File Rejected
```error
remote: error: File exceeds 100MB limit
```

Solution:
1. Use Git LFS:
```bash
git lfs install
git lfs track "*.zip"
```

2. Clean history:
```bash
git filter-branch --force --tree-filter \
  'rm -f path/to/large/file' HEAD
```
