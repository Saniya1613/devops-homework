# Session 5 – Git & GitHub Homework

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

All commands and outputs below are from my terminal (Ubuntu 24.04, git 2.43).

---

## Task 1 – `git commit -a -m` vs `git commit -m`

| `git commit -m "msg"` | `git commit -a -m "msg"` |
|---|---|
| Commits **only what is already staged** (`git add`) | Automatically stages **all modified & deleted tracked files**, then commits |
| Unstaged changes are left out | No `git add` needed for tracked files |
| Works for new (untracked) files after `git add` | **Ignores new untracked files** – they still need `git add` |

### Setup
```console
saniya@saniya-devops:~$ mkdir git-demo && cd git-demo && git init && echo 'line 1' > tracked.txt && git add tracked.txt && git commit -m 'Initial commit' 
Initialized empty Git repository in /home/saniya/git-demo/.git/
[main (root-commit) 46d4fcf] Initial commit
 1 file changed, 1 insertion(+)
 create mode 100644 tracked.txt
```

### Test 1: modify a tracked file and use `git commit -m` **without** `git add`

```console
saniya@saniya-devops:~$ cd git-demo && echo 'line 2' >> tracked.txt && git commit -m 'Try commit without add'
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   tracked.txt

no changes added to commit (use "git add" and/or "git commit -a")
```

Nothing was committed – `-m` alone only commits the staging area, which is empty.

### Test 2: same change with `git commit -a -m`

```console
saniya@saniya-devops:~$ cd git-demo && git commit -a -m 'Commit with -a flag' && git log --oneline
[main ca0c664] Commit with -a flag
 1 file changed, 1 insertion(+)
ca0c664 Commit with -a flag
46d4fcf Initial commit
```

`-a` staged the modified tracked file automatically and committed it.

### Test 3: a NEW untracked file with `git commit -a -m`

```console
saniya@saniya-devops:~$ cd git-demo && echo 'new' > newfile.txt && echo 'line 3' >> tracked.txt && git commit -a -m 'Commit -a with new file' && git status --short
[main 94d6c53] Commit -a with new file
 1 file changed, 1 insertion(+)
?? newfile.txt
```

`tracked.txt` was committed, but `newfile.txt` is still untracked (`??`) – `-a` never adds new files.

```console
saniya@saniya-devops:~$ cd git-demo && git add newfile.txt && git commit -m 'Add new file using git add + commit -m' && git log --oneline
[main db3c430] Add new file using git add + commit -m
 1 file changed, 1 insertion(+)
 create mode 100644 newfile.txt
db3c430 Add new file using git add + commit -m
94d6c53 Commit -a with new file
ca0c664 Commit with -a flag
46d4fcf Initial commit
```

---

## Task 2 – Git Cherry-Pick

`git cherry-pick <commit-hash>` applies the changes introduced by **one specific commit** from another branch onto the current branch, creating a new commit (new hash, same change).

### Step 1 – Create 3 commits in `main`
```console
saniya@saniya-devops:~$ mkdir cherry-demo && cd cherry-demo && git init -q && echo '# App' > README.md && git add . && git commit -q -m 'main: add README' && echo 'v1' > app.txt && git add . && git commit -q -m 'main: add app v1' && echo 'config=1' > config.txt && git add . && git commit -q -m 'main: add config' && echo done
done
```

### Step 2 – View commits with git log

```console
saniya@saniya-devops:~$ cd cherry-demo && git log --oneline
50d16cc main: add config
b95b66b main: add app v1
9871a24 main: add README
```

### Step 3 – Create a new branch and make 3 commits

```console
saniya@saniya-devops:~$ cd cherry-demo && git checkout -b feature && echo 'login feature' > login.txt && git add . && git commit -q -m 'feature: add login' && echo 'bug fix: null check' > bugfix.txt && git add . && git commit -q -m 'feature: critical bug fix' && echo 'experimental' > exp.txt && git add . && git commit -q -m 'feature: experimental work' && git log --oneline
Switched to a new branch 'feature'
9b38356 feature: experimental work
75b4955 feature: critical bug fix
44c68e3 feature: add login
50d16cc main: add config
b95b66b main: add app v1
9871a24 main: add README
```

### Step 4 – Identify the specific commit

Only the **critical bug fix** should go to `main` now (login and experimental work are not ready).

```console
saniya@saniya-devops:~$ cd cherry-demo && git log --oneline --grep='critical bug fix' feature
75b4955 feature: critical bug fix
```

### Step 5 – Cherry-pick it into main

```console
saniya@saniya-devops:~$ cd cherry-demo && git checkout main && git cherry-pick $(git log --format=%h --grep='critical bug fix' -n1 feature)
Switched to branch 'main'
[main 6ae95c9] feature: critical bug fix
 Date: Wed Oct 7 12:39:08 2026 +0000
 1 file changed, 1 insertion(+)
 create mode 100644 bugfix.txt
```

### Step 6 – Verify

```console
saniya@saniya-devops:~$ cd cherry-demo && git log --oneline && ls
6ae95c9 feature: critical bug fix
50d16cc main: add config
b95b66b main: add app v1
9871a24 main: add README
README.md
app.txt
bugfix.txt
config.txt
```

```console
saniya@saniya-devops:~$ cd cherry-demo && git show --stat HEAD | head -8
commit 6ae95c931bcb0e201dfa07bb35e5800069f34eb6
Author: Saniya Sanjiv Patil <saniya.24bcs10246@sst.scaler.com>
Date:   Wed Oct 7 12:39:08 2026 +0000

    feature: critical bug fix

 bugfix.txt | 1 +
 1 file changed, 1 insertion(+)
```

```console
saniya@saniya-devops:~$ cd cherry-demo && git log --oneline --graph --all
* 9b38356 feature: experimental work
* 75b4955 feature: critical bug fix
* 44c68e3 feature: add login
| * 6ae95c9 feature: critical bug fix
|/  
* 50d16cc main: add config
* b95b66b main: add app v1
* 9871a24 main: add README
```

✅ `bugfix.txt` is now in `main`, while `login.txt` and `exp.txt` are **not** – only the selected commit was applied.
Note the cherry-picked commit in `main` has a **different hash** than the original on `feature` (new commit, same change).

---

## Useful Git commands practised
`git init`, `git status`, `git add`, `git commit -m`, `git commit -a -m`, `git log --oneline --graph --all`,
`git branch`, `git checkout -b`, `git switch`, `git merge`, `git cherry-pick`, `git show`, `git diff`, `git remote add origin`, `git push -u origin main`, `git pull`, `git clone`.
