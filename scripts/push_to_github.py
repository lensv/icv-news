#!/usr/bin/env python
"""GitHub API push script - reads token from file"""
import base64, json, os, sys, urllib.request, urllib.error

OWNER, REPO = "lensv", "icv-news"
BRANCH = "main"
PROJECT = r"E:\trae_solo\自动化监测智能网联汽车新闻"
TOKEN_FILE = os.path.join(PROJECT, ".github_token")

token = ""
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE) as f:
        token = f.read().strip()

if not token:
    print("请把 Token 保存到文件 .github_token 中，然后重新运行")
    print("或者设置环境变量: set GH_TOKEN=你的token")
    sys.exit(1)

headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

def api_put(path, content, msg=None):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    data = json.dumps({
        "message": msg or f"Add {path}",
        "content": base64.b64encode(content.encode("utf-8")).decode(),
        "branch": BRANCH,
    }).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
    try:
        urllib.request.urlopen(req, timeout=30)
        return True, None
    except urllib.error.HTTPError as e:
        return False, f"{e.code}"

def push_dir(dir_rel):
    root = os.path.join(PROJECT, dir_rel.replace("/", "\\"))
    ok, fail = 0, 0
    for base, _, files in os.walk(root):
        for fname in files:
            fpath = os.path.join(base, fname)
            rel = os.path.relpath(fpath, PROJECT).replace("\\", "/")
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                s, err = api_put(rel, f.read())
            if s:
                print(f"  ✅ {rel}")
                ok += 1
            else:
                print(f"  ⏭️ {rel} ({err})")
                fail += 1
    return ok, fail

# Test token first
try:
    r = urllib.request.urlopen(urllib.request.Request(
        "https://api.github.com/user", headers=headers), timeout=10)
    user = json.loads(r.read())
    print(f"Token 有效，用户: {user['login']}")
except Exception as e:
    print(f"Token 无效: {e}")
    sys.exit(1)

print(f"\n推送文件到 {OWNER}/{REPO} ...")

# 核心文件
core = [".gitignore", "requirements.txt"]
for f in core:
    fp = os.path.join(PROJECT, f)
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as fh:
            ok, _ = api_put(f, fh.read())
        print(f"  {'✅' if ok else '⏭️'} {f}")

# 目录
ok1, f1 = push_dir(".github/workflows")
ok2, f2 = push_dir("scripts")
ok3, f3 = push_dir("templates")
ok4, f4 = push_dir("web/templates")

print(f"\n完成！共推送 {ok1+ok2+ok3+ok4} 个文件")
