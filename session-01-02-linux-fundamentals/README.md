# Session 1 & 2 – Linux Fundamentals (Homework)

**Name:** Saniya Sanjiv Patil  
**Roll No:** 24bcs10246  
**Batch:** B

All commands below were executed on an Ubuntu 24.04 machine (user `saniya`, host `saniya-devops`); the output shown is the real terminal output.
For `journalctl` (which needs systemd) the commands were run inside an Ubuntu 24.04 systemd container.

---

## Task 1 – Soft Link vs Hard Link

| | Hard link | Soft (symbolic) link |
|---|---|---|
| What it is | Another directory entry pointing to the **same inode** | A small special file that stores the **path** of the target |
| Command | `ln target linkname` | `ln -s target linkname` |
| Inode | Same inode number as the original | Its own, different inode |
| If original is deleted | Data still accessible (link count just drops) | Link becomes **dangling/broken** |
| Directories | Not allowed (for normal users) | Allowed |
| Across filesystems/partitions | Not possible | Possible |
| `ls -l` shows | Normal file, link count > 1 | `l` type with `link -> target` |

**Interview one-liner:** a hard link is a second *name* for the same data (inode); a soft link is a *shortcut* that points to a path.

### Practice
```console
saniya@saniya-devops:~$ mkdir -p linkdemo && cd linkdemo && echo 'Hello from Saniya' > original.txt && ls -li
total 4
1106670 -rw-r--r-- 1 saniya saniya 18 Oct  7 12:38 original.txt
```

```console
saniya@saniya-devops:~$ cd linkdemo && ln original.txt hardlink.txt && ln -s original.txt softlink.txt && ls -li
total 8
1106670 -rw-r--r-- 2 saniya saniya 18 Oct  7 12:38 hardlink.txt
1106670 -rw-r--r-- 2 saniya saniya 18 Oct  7 12:38 original.txt
1106673 lrwxrwxrwx 1 saniya saniya 12 Oct  7 12:38 softlink.txt -> original.txt
```

Notice: `hardlink.txt` has the **same inode** as `original.txt` and the link count is now 2. `softlink.txt` has a different inode and points to `original.txt`.

```console
saniya@saniya-devops:~$ cd linkdemo && cat hardlink.txt softlink.txt && stat -c '%n inode=%i links=%h' original.txt hardlink.txt softlink.txt
Hello from Saniya
Hello from Saniya
original.txt inode=1106670 links=2
hardlink.txt inode=1106670 links=2
softlink.txt inode=1106673 links=1
```

### Delete the original and observe

```console
saniya@saniya-devops:~$ cd linkdemo && rm original.txt && ls -li
total 4
1106670 -rw-r--r-- 1 saniya saniya 18 Oct  7 12:38 hardlink.txt
1106673 lrwxrwxrwx 1 saniya saniya 12 Oct  7 12:38 softlink.txt -> original.txt
```

```console
saniya@saniya-devops:~$ cd linkdemo && cat hardlink.txt; cat softlink.txt
Hello from Saniya
cat: softlink.txt: No such file or directory
```

The hard link still has the data; the soft link is now broken (dangling).

### Soft link to a directory, and deleting links

```console
saniya@saniya-devops:~$ cd linkdemo && mkdir mydir && ln -s mydir mydir_link && ln mydir mydir_hard; ls -l
ln: mydir: hard link not allowed for directory
total 8
-rw-r--r-- 1 saniya saniya   18 Oct  7 12:38 hardlink.txt
drwxr-xr-x 2 saniya saniya 4096 Oct  7 12:38 mydir
lrwxrwxrwx 1 saniya saniya    5 Oct  7 12:38 mydir_link -> mydir
lrwxrwxrwx 1 saniya saniya   12 Oct  7 12:38 softlink.txt -> original.txt
```

```console
saniya@saniya-devops:~$ cd linkdemo && unlink softlink.txt && rm hardlink.txt mydir_link && ls -l
total 4
drwxr-xr-x 2 saniya saniya 4096 Oct  7 12:38 mydir
```

---

## Task 2 – `adduser` vs `useradd`

| `useradd` | `adduser` |
|---|---|
| Low-level binary, available on every Linux distro | Friendly Perl wrapper script (Debian/Ubuntu) around `useradd` |
| Does **not** create a home dir unless `-m`, no password prompt, shell defaults to `/bin/sh` unless `-s` | Interactively creates home dir, copies `/etc/skel`, sets password, asks for full name, sets shell `/bin/bash` |
| Good for scripts/automation | Recommended for humans on **Ubuntu/Debian** |

**On Ubuntu the recommended command is `adduser`** (the `useradd` man page itself says Debian admins should use `adduser`), because it applies sane defaults and sets everything up in one go.

### Practice
```console
saniya@saniya-devops:~$ sudo adduser --disabled-password --gecos 'Test User Saniya' testsaniya
info: Adding user `testsaniya' ...
info: Selecting UID/GID from range 1000 to 59999 ...
info: Adding new group `testsaniya' (1002) ...
info: Adding new user `testsaniya' (1002) with group `testsaniya (1002)' ...
info: Creating home directory `/home/testsaniya' ...
info: Copying files from `/etc/skel' ...
info: Adding new user `testsaniya' to supplemental / extra groups `users' ...
info: Adding user `testsaniya' to group `users' ...
```

```console
saniya@saniya-devops:~$ id testsaniya; ls -la /home/testsaniya; grep testsaniya /etc/passwd
uid=1002(testsaniya) gid=1002(testsaniya) groups=1002(testsaniya),100(users)
ls: cannot open directory '/home/testsaniya': Permission denied
testsaniya:x:1002:1002:Test User Saniya,,,:/home/testsaniya:/bin/bash
```

Compare with the low-level `useradd` (no flags):

```console
saniya@saniya-devops:~$ sudo useradd testplain; grep testplain /etc/passwd; ls -d /home/testplain
testplain:x:1003:1003::/home/testplain:/bin/sh
ls: cannot access '/home/testplain': No such file or directory
```

`useradd` without `-m -s /bin/bash` created no home directory and set shell to `/bin/sh`. Cleanup:

```console
saniya@saniya-devops:~$ sudo userdel testplain && sudo deluser --remove-home testsaniya
info: Looking for files to backup/remove ...
info: Removing files ...
warn: `/usr/bin/crontab' not executed. Skipping crontab removal. Package `cron' required.
info: Removing user `testsaniya' ...
```

---

## Task 3 – `journalctl`

`journalctl` is used to query and view logs collected by **systemd-journald** – kernel messages, boot logs and the stdout/stderr of every systemd service.

| Command | Purpose |
|---|---|
| `journalctl` | All logs (oldest first) |
| `journalctl -n 20` | Last 20 lines |
| `journalctl -f` | Follow live (like `tail -f`) |
| `journalctl -u nginx` | Logs of a specific service/unit |
| `journalctl -b` | Logs since current boot |
| `journalctl -p err` | Only priority error and above |
| `journalctl --since "10 min ago"` | Time filter |
| `journalctl -xeu nginx` | Jump to end with explanations – used for troubleshooting |
| `journalctl --disk-usage` | Space used by journal |

### Practice – checking logs of a specific service (nginx)
I installed nginx and started it, but it **failed**. `journalctl` showed the reason:
```console
root@ubuntu-systemd:~# systemctl start nginx; systemctl is-active nginx
Job for nginx.service failed because the control process exited with error code.
See "systemctl status nginx.service" and "journalctl -xeu nginx.service" for details.
failed
```

```console
root@ubuntu-systemd:~# journalctl -u nginx --no-pager -n 6
Oct 07 12:38:46 11cded5a7968 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Oct 07 12:38:46 11cded5a7968 nginx[645]: nginx: [emerg] socket() [::]:80 failed (97: Address family not supported by protocol)
Oct 07 12:38:46 11cded5a7968 nginx[645]: nginx: configuration file /etc/nginx/nginx.conf test failed
Oct 07 12:38:46 11cded5a7968 systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Oct 07 12:38:46 11cded5a7968 systemd[1]: nginx.service: Failed with result 'exit-code'.
Oct 07 12:38:46 11cded5a7968 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
```

Root cause: the container has no IPv6, but the default config has `listen [::]:80`. Fix and restart:

```console
root@ubuntu-systemd:~# sed -i '/listen \[::\]:80/d' /etc/nginx/sites-enabled/default && systemctl restart nginx && systemctl is-active nginx
active
```

```console
root@ubuntu-systemd:~# journalctl -u nginx --no-pager -n 3
Oct 07 12:38:46 11cded5a7968 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
Oct 07 12:38:47 11cded5a7968 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Oct 07 12:38:47 11cded5a7968 systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
```

```console
root@ubuntu-systemd:~# journalctl -p err --no-pager -n 5
Oct 07 12:35:23 11cded5a7968 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
Oct 07 12:35:23 11cded5a7968 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
Oct 07 12:37:09 11cded5a7968 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
Oct 07 12:38:46 11cded5a7968 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
```

```console
root@ubuntu-systemd:~# journalctl -b --no-pager -n 5
Oct 07 12:38:46 11cded5a7968 systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Oct 07 12:38:46 11cded5a7968 systemd[1]: nginx.service: Failed with result 'exit-code'.
Oct 07 12:38:46 11cded5a7968 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
Oct 07 12:38:47 11cded5a7968 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Oct 07 12:38:47 11cded5a7968 systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
```

```console
root@ubuntu-systemd:~# journalctl --disk-usage
Archived and active journals take up 8.0M in the file system.
```

---

## Task 4 – Linux Command Cheat Sheet (practised)

| Category | Commands |
|---|---|
| Navigation | `pwd`, `ls -la`, `cd`, `tree` |
| Files | `touch`, `cp`, `mv`, `rm`, `mkdir -p`, `rmdir`, `cat`, `less`, `head`, `tail -f` |
| Search | `find`, `grep -rn`, `which`, `locate` |
| Permissions | `chmod 755`, `chown user:group`, `umask` |
| Processes | `ps aux`, `top`, `kill -9`, `pgrep`, `nohup`, `&`, `jobs` |
| Disk / memory | `df -h`, `du -sh`, `free -h` |
| Users | `whoami`, `id`, `adduser`, `usermod -aG`, `passwd`, `sudo` |
| Text processing | `wc`, `sort`, `uniq`, `cut`, `awk`, `sed`, `tr` |
| Archives | `tar -czvf`, `tar -xzvf`, `zip`, `unzip` |
| Networking | `ip a`, `ping`, `curl`, `ss -tulnp` |
| Services | `systemctl status/start/stop/enable`, `journalctl` |
| Packages | `apt update`, `apt install`, `apt remove` |

### Practice
```console
saniya@saniya-devops:~$ mkdir -p practice/a/b && touch practice/a/b/file{1..3}.txt && tree practice
practice
`-- a
    `-- b
        |-- file1.txt
        |-- file2.txt
        `-- file3.txt

3 directories, 3 files
```

```console
saniya@saniya-devops:~$ cd practice && echo -e 'apple\nbanana\napple\ncherry' > fruits.txt && sort fruits.txt | uniq -c && wc -l fruits.txt && grep -n apple fruits.txt
      2 apple
      1 banana
      1 cherry
4 fruits.txt
1:apple
3:apple
```

```console
saniya@saniya-devops:~$ cd practice && chmod 755 a && ls -ld a && find . -name '*.txt'
drwxr-xr-x 3 saniya saniya 4096 Oct  7 12:38 a
./fruits.txt
./a/b/file2.txt
./a/b/file3.txt
./a/b/file1.txt
```

```console
saniya@saniya-devops:~$ echo 'name,roll' > practice/s.csv; echo 'saniya,24bcs10246' >> practice/s.csv; cut -d, -f2 practice/s.csv; awk -F, 'NR>1{print toupper($1)}' practice/s.csv
roll
24bcs10246
SANIYA
```

```console
saniya@saniya-devops:~$ tar -czf practice.tar.gz practice && tar -tzf practice.tar.gz | head -5
practice/
practice/fruits.txt
practice/s.csv
practice/a/
practice/a/b/
```

```console
saniya@saniya-devops:~$ df -h / && free -h && whoami && uname -r
Filesystem      Size  Used Avail Use% Mounted on
overlay         252G   16G   28G  37% /
               total        used        free      shared  buff/cache   available
Mem:           7.8Gi       1.1Gi       3.6Gi        22Mi       3.5Gi       6.8Gi
Swap:             0B          0B          0B
saniya
6.18.44-fc-v77
```

```console
saniya@saniya-devops:~$ ps aux --sort=-%mem | head -5
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
saniya      4161  0.0  0.0   7904  4040 ?        R    12:38   0:00 ps aux --sort=-%mem
saniya      4155  0.0  0.0   4336  3380 ?        Ss   12:38   0:00 bash -c umask 022; ps aux --sort=-%mem | head -5
root           1  0.0  0.0   2708  1600 ?        Ss   12:36   0:00 sleep infinity
saniya      4162  0.0  0.0   2720  1416 ?        S    12:38   0:00 head -5
```

