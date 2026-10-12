# BOT. 圖標

| 檔案 | 用途 |
| --- | --- |
| `bot-logo-mark.png`／`.svg` | 只有標誌（透明背景） |
| `bot-logo-wordmark.png`／`.svg` | 標誌加 BOT.，字是深色，用在淺色背景 |
| `bot-logo-wordmark-light.png`／`.svg` | 標誌加 BOT.，字是淺色，用在深色背景 |
| `bot-avatar.png`／`.svg` | 圓角方形底的版本，給機器人的 Discord 頭像與應用程式圖示 |

Discord 會把頭像顯示成圓形，所以標誌放在底板的中央，圓形裁切後仍完整。

`generate.py` 是產生這些圖的程式（只用 Python 標準函式庫）：

```bash
python assets/logo/generate.py 輸出資料夾
```

它輸出 SVG；PNG 用瀏覽器或任何 SVG 轉換工具轉出。形狀與顏色的座標都寫在檔案開頭。
