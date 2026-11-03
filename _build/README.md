# 公開版網站產生器

- 編輯後台：Claude 上的「Hungryforest 30」部落格（artifact fee3a7c2-e181-4c67-98aa-b9959c7ec382）
- 同步方式：把後台資料庫的 posts / site/config / site/categories 匯出成 data/*.json，新圖片放進 img/，然後：
  `python3 _build/gen.py . https://網址`
- 圖片引用格式：`f:img/<名稱>.jpg`（後台用 `asset:<id>` 上傳的新圖要先下載轉成 img/ 檔案）
