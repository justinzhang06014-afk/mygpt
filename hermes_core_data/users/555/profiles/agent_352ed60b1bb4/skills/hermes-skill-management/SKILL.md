---
name: hermes-skill-management
description: 完整的 Hermes skill 導入、共享、發布管理指南
triggers:
  - "skill"
  - "導入 skill"
  - "安裝 skill"
  - "共享 skill"
  - "publish skill"
  - "skill tap"
  - "skill bundle"
  - "分享 skill"
  - "skill 管理"
---

# Hermes Skill Management

## 快速導航
- [導入外部 skill](#導入)
- [共享 skill 給他人](#共享)
- [Tap 機制](#tap)
- [Bundle 打包](#bundle)
- [Publish 發布](#publish)
- [敏感資訊處理](#安全)

## <a id="導入"></a>導入外部 Skill

### 方式 A：Tap 整個 GitHub Repo（推薦）

```bash
hermes skills tap add owner/repo
hermes skills install owner/repo/skill-name -y
```

### 方式 B：直接從 URL 安裝

```bash
hermes skills install https://raw.githubusercontent.com/owner/repo/main/skill-name/SKILL.md -y
```

### 方式 C：從 Skills Hub 搜尋安裝

```bash
hermes skills browse          # 瀏覽
hermes skills search "keyword" # 搜尋
hermes skills inspect <id>     # 預覽
hermes skills install <id>     # 安裝
```

### 方式 D：Snapshot 批量導入導出

```bash
hermes skills snapshot export skills.json   # 匯出
hermes skills snapshot import skills.json   # 匯入
```

## <a id="共享"></a>共享 Skill 給他人

### 核心原則：公開和私人 skill 從源頭就分開

**Repo 結構：**
```
my-skills/                    # GitHub repo
├── skill-a/                  # 公開
│   └── SKILL.md
├── skill-b/                  # 公開
│   └── SKILL.md
└── private-skill/            # 不推到公開 repo
    └── SKILL.md
```

### 分享流程

**發布者操作：**
1. 把可公開的 skill 放到一個獨立 GitHub repo
2. 敏感資訊改用環境變數（見下方安全章節）
3. `git push` 到公開 repo

**使用者操作：**
```bash
hermes skills tap add owner/repo
hermes skills install owner/repo/skill-name -y
```

**後續更新：**
```bash
hermes skills check                          # 檢查更新
hermes skills update owner/repo/skill-name   # 更新
```

## <a id="tap"></a>Tap 機制

```bash
hermes skills tap add owner/repo     # 新增
hermes skills tap list               # 查看
hermes skills tap remove owner/repo  # 移除
```

Tap 後，repo 內所有 SKILL.md 都會被自動偵測並可搜尋。

## <a id="bundle"></a>Bundle 打包

把多個 skill 綁成一個指令：

```bash
hermes bundles create toolkit-name \
  --skill skill-a \
  --skill skill-b \
  --skill skill-c \
  --description "描述文字"

hermes bundles list    # 查看
hermes bundles show toolkit-name  # 查看內容
hermes bundles delete toolkit-name  # 刪除
```

## <a id="publish"></a>Publish 發布

```bash
hermes skills publish /path/to/skill --to github --repo owner/repo
```

## <a id="安全"></a>敏感資訊處理

**絕不硬編碼：**
```yaml
# 錯誤
api_key: "sk-12345"

# 正確：用環境變數
api_key: "${MY_API_KEY}"
```

使用者安裝後自行設定環境變數。
