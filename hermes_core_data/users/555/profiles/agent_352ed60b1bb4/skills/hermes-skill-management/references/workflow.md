# 對話流程指南

## 當用戶丟 GitHub 連結要我處理 skill

### 情境 1：用戶丟完整 repo 連結
```
用戶：幫我裝 https://github.com/owner/repo
```

執行：
```bash
hermes skills tap add owner/repo
hermes skills list
hermes skills install owner/repo/skill-name -y
```

### 情境 2：用戶丟 raw SKILL.md 連結
```
用戶：裝這個 https://raw.githubusercontent.com/owner/repo/main/skill/SKILL.md
```

執行：
```bash
hermes skills install https://raw.githubusercontent.com/.../SKILL.md -y
```

### 情境 3：用戶要發布自己的 skill
```
用戶：把我的 skill 分享到 GitHub
```

執行：
```bash
hermes skills publish /opt/data/profiles/<profile>/skills/<skill> --to github --repo owner/repo
```

### 情境 4：用戶要打包多個 skill
```
用戶：把這幾個 skill 打包
```

執行：
```bash
hermes bundles create name --skill a --skill b --skill c --description "..."
```

## 關鍵提醒
- skill 共享不需要 Docker，走 Git + tap 機制
- 敏感資訊用環境變數，不硬編碼
- Tap 後 skill 有完整 update/uninstall 支援
- Bundle 適合把相關 skill 綁成一個指令
