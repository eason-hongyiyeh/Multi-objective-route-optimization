# 從 GitHub 移除 `.gitignore` 的操作紀錄

日期：2026-07-26（Asia/Taipei）

## 目的

1. 從 Git 儲存庫與 GitHub 移除已被追蹤的 `.gitignore`。
2. 保留原有的忽略規則。
3. 確保日後執行 `git add .` 時，不會再次加入 `.gitignore`。

## 執行方式

本專案改用只在本機生效的 `.local-git-excludes` 作為 Git 排除檔。該檔案包含：

- 原 `.gitignore` 的所有忽略規則。
- `.gitignore`，防止它日後被 `git add .` 加回。
- `.local-git-excludes` 自己，防止本機排除檔被提交。

接著執行：

```powershell
git config --local core.excludesFile "D:/MyFirstProject/myproject/.local-git-excludes"
git rm .gitignore
git add .
git commit -m "Remove tracked gitignore and document local exclusions"
git push origin main
```

## 驗證方式

```powershell
git check-ignore -v .gitignore
git check-ignore -v .local-git-excludes
git status --short
```

前兩個指令應顯示規則來自 `.local-git-excludes`；最後一個指令在提交完成後應無待提交變更。

## 注意事項

`core.excludesFile` 是此工作目錄的本機 Git 設定，不會跟著儲存庫傳到其他電腦。若在另一台電腦重新 clone，需要建立自己的本機排除檔並重新設定；否則建議一般專案仍將 `.gitignore` 保留在儲存庫中，讓所有協作者共享相同規則。
