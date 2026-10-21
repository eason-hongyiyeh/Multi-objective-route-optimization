# 夜市營業時間查詢結果

查詢日期：2026-10-19。所有時間為臺灣當地時間；24:00 是當日結束，翌日表示跨日。

對照現有 35 筆 GeoJSON：26 筆找到政府網站時段、1 筆找到非官方報導、5 筆需確認、2 筆未查得可確認時段、1 筆曾公告暫停營業。這是來源物件筆數，同一夜市的分區或不同物件仍各列一筆。

採夜市專頁、地方政府市場處或官方旅遊網站。官方頁面不一定代表即時營業狀態，攤商可能提早收攤、休息或因天候取消；非官方報導與互相矛盾的資料另行註明。

## 需要先確認的資料

| 原始名稱／來源 ID | 查詢結果 | 原因與參考來源 |
| --- | --- | --- |
| 蘆洲早夜市<br>`relation/17332141` | 待確認（缺少確切名稱對照） | 官網的蘆洲廟口夜市列每日 15:00–23:00；原檔名稱為蘆洲早夜市，尚未確認兩者範圍相同，未直接套用時段。<br>[新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/detail/107424) |
| 早市, 夜市(逢周六)<br>`way/367362476` | 原檔名稱記載週六夜市；開始與結束時間未確認 | 原檔僅有「早市, 夜市(逢周六)」及座標，未查得能確認同一場址的正式名稱與營業時段。<br>未找到可確認的公開來源 |
| 桃園觀光夜市<br>`way/546054452` | 待確認：景點頁每日 17:00–24:00；消費資訊頁週末至翌日 01:00 | 同一官方網站存在差異：消費資訊頁為週一至五 17:00–24:00、六日 17:00–翌日 01:00；商圈列表另列 17:30–24:00。未合併成單一確定時段。<br>[桃園觀光導覽網：桃園觀光夜市景點頁](https://travel.tycg.gov.tw/zh-tw/travel/attraction/969)、[桃園觀光導覽網：桃園觀光夜市消費資訊](https://travel.tycg.gov.tw/zh-tw/Consume/Detail/73?print=1)、[桃園觀光導覽網：商圈列表](https://travel.tycg.gov.tw/zh-tw/consume/business-district) |
| 夜市<br>`way/730666401` | 原檔說明記載每週二、五；開始與結束時間未確認 | 原名只有「夜市」。查到深坑慈聖夜市每週二、五的介紹，但尚未確認與此來源物件相同，未改名或套用時段。<br>[深坑慈聖夜市介紹（待確認是否為同一點位）](https://carollin.tw/shenkeng-nightmarket/) |
| 台灣夜市<br>`way/775603768` | 分區時段待確認；所在臺北車站商場公布每日 10:00–22:00 | 原檔標示台北車站內的台灣夜市分區，manager 仍為微風。商場已於 2026-07-25 改由新光三越營運；目前未找到此舊分區名稱的個別時段，不把商場時間當成分區確定時間。<br>[新光三越：臺北車站分店資訊](https://www.skm.com.tw/branch/16/1112)、[台視：2026-07-25 商場營運移轉報導](https://news.ttv.com.tw/wbc/news/Views/11507250011000I) |
| 新莊思源夜市<br>`way/1313165663` | 曾公告自 2024-10-01 暫停營業；目前是否復業待確認 | 報導引述夜市粉專公告。本次未查得可確認的復業公告；原檔週五至日 16:00–24:00 移至 opening_hours_original 留存，不作為現行時段。<br>[民視：新莊思源夜市暫停營業報導（2024-09-29）](https://www.ftvnews.com.tw/news/detail/2024929W0124) |
| 鶯歌龍鳳夜市<br>`way/1336425254` | 待確認：市府 2024 年頁面列每週二、五、六 16:30–21:30 | 市府頁面更新於 2024-09-16；另查到非官方資訊列週三、五、六、日，地址與時段也不同。以市府內容作參考，現行場址與時段仍需向業者確認。<br>[新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=0893b8d8-00f6-492c-b971-a777d0c00b63&id=73&mid=60&param=pn%3D1%26mid%3D60%26id%3D0)、[TonightMarkets 龍鳳夜市資訊（非官方，與市府有差異）](https://tonightmarkets.com/night-markets/yinggelongfeng-night-market) |
| 弘道街夜市 (星期二、五晚上)<br>`node/12092325283` | 每週二、五 17:00–23:00（2022 年報導；遇雨可能取消） | 找到具名採訪報導，尚未找到官方營業時間；報導較舊，現況仍待確認。<br>[鏡週刊：弘道街夜市（2022-07-22）](https://www.mirrormedia.mg/story/amp/20220722food004) |
| 桃園夜市美食廣場<br>`node/12531604654` | 未查得此美食廣場的個別營業時間 | 此筆在原檔為獨立 food_court 點位。查到的是桃園觀光夜市整體時段，不能直接視為這個美食廣場的營業時間。<br>[桃園觀光導覽網：桃園觀光夜市景點頁](https://travel.tycg.gov.tw/zh-tw/travel/attraction/969) |

## 全部資料

| 夜市（保留原名） | 來源 ID | 營業時間／查詢結果 | 資料狀態 | 來源 |
| --- | --- | --- | --- | --- |
| 林口夜市 | `relation/10220395` | 每週三、日 17:00–23:00 | 政府網站 | [新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=48372f2d-c979-458b-a32e-b6ef7d775c15&id=69&mid=60&param=pn%3D1%26mid%3D60%26id%3D0) |
| 新莊廟街夜市 | `relation/12773846` | 每日 16:00–24:00 | 政府網站 | [新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/detail/107166) |
| 蘆洲早夜市 | `relation/17332141` | 待確認（缺少確切名稱對照） | 待確認 | [新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/detail/107424) |
| 興仁夜市(B) | `way/188179149` | 每週二、五、六、日 17:00–24:00 | 政府網站 | [桃園觀光導覽網：興仁花園夜市](https://travel.tycg.gov.tw/zh-tw/travel/attraction/959) |
| 興仁花園夜市 美食A區 | `way/188179187` | 每週二、五、六、日 17:00–24:00 | 政府網站 | [桃園觀光導覽網：興仁花園夜市](https://travel.tycg.gov.tw/zh-tw/travel/attraction/959) |
| 興南夜市 | `way/233876913` | 每日 18:00–24:00 | 政府網站 | [新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/detail/402920) |
| 遼寧街夜市 | `way/254453771` | 每日 18:00–24:00 | 政府網站 | [臺北市市場處：遼寧夜市](https://www.tcma.gov.taipei/News_Content.aspx?n=FAC14AD2DE4E01A4&s=378B3348E6FD63C5&sms=32F7BA052C5CA548) |
| 南雅觀光夜市 | `way/317584691` | 每日 17:00–翌日 02:00 | 政府網站 | [新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/detail/109711) |
| 早市, 夜市(逢周六) | `way/367362476` | 原檔名稱記載週六夜市；開始與結束時間未確認 | 未查得 | 未找到可確認的公開來源 |
| 士林夜市 | `way/375486258` | 每日 16:00–24:00 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1536) |
| 華西街観光夜市 | `way/375486272` | 每日 16:00–24:00 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1535) |
| 西昌街夜市 | `way/375486277` | 每日 15:00–21:00 | 政府網站 | [臺北旅遊網：西昌街夜市（英文頁）](https://www.travel.taipei/en/attraction/details/2156) |
| 樂華夜市 | `way/388224261` | 每日 16:00–24:00 | 政府網站 | [新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/detail/107161) |
| 寧夏夜市 | `way/396410905` | 每日 17:00–23:30 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1560) |
| 臨江街觀光夜市 | `way/457483394` | 每日 18:00–24:00 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1562) |
| 樹林興仁花園夜市 | `way/458084083` | 每週三、五、六、日 17:00–24:00 | 政府網站 | [新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=a44e35b2-4ab3-4b83-b55f-f3b16a8d59d8&id=64&mid=26&param=pn%3D1%26cid%3D35%26mid%3D26%26id%3D74) |
| 饒河街觀光夜市 | `way/516455044` | 每日 17:00–24:00 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1538) |
| 廣州街夜市 | `way/520781824` | 每日 16:00–24:00 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1565) |
| 桃園觀光夜市 | `way/546054452` | 待確認：景點頁每日 17:00–24:00；消費資訊頁週末至翌日 01:00 | 待確認 | [桃園觀光導覽網：桃園觀光夜市景點頁](https://travel.tycg.gov.tw/zh-tw/travel/attraction/969)、[桃園觀光導覽網：桃園觀光夜市消費資訊](https://travel.tycg.gov.tw/zh-tw/Consume/Detail/73?print=1)、[桃園觀光導覽網：商圈列表](https://travel.tycg.gov.tw/zh-tw/consume/business-district) |
| 南機場夜市 | `way/593801638` | 每日 17:00–24:00 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1564) |
| 公館夜市 | `way/679004546` | 每日 17:00–24:00 | 政府網站 | [臺北市市場處：公館夜市](https://www.tcma.gov.taipei/News_Content.aspx?n=FAC14AD2DE4E01A4&s=01DFBEEC7B87B051&sms=32F7BA052C5CA548) |
| 夜市 | `way/730666401` | 原檔說明記載每週二、五；開始與結束時間未確認 | 待確認 | [深坑慈聖夜市介紹（待確認是否為同一點位）](https://carollin.tw/shenkeng-nightmarket/) |
| 三和夜市 | `way/736385631` | 每日 17:00–24:00 | 政府網站 | [新北市觀光旅遊網](https://newtaipei.travel/zh-tw/attractions/detail/110341) |
| 台灣夜市 | `way/775603768` | 分區時段待確認；所在臺北車站商場公布每日 10:00–22:00 | 待確認 | [新光三越：臺北車站分店資訊](https://www.skm.com.tw/branch/16/1112)、[台視：2026-07-25 商場營運移轉報導](https://news.ttv.com.tw/wbc/news/Views/11507250011000I) |
| 沙崙夜市（B區） | `way/781490557` | 每週五、日 17:00–22:00 | 政府網站 | [新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=8e33057f-f05b-47e4-9546-aad2fa14b504&id=71&mid=26&param=pn%3D1%26cid%3D44%26mid%3D26%26id%3D74) |
| 沙崙夜市（A區） | `way/1271731730` | 每週五、日 17:00–22:00 | 政府網站 | [新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=8e33057f-f05b-47e4-9546-aad2fa14b504&id=71&mid=26&param=pn%3D1%26cid%3D44%26mid%3D26%26id%3D74) |
| 樟樹灣夜市 | `way/1301435279` | 每週三、六、日 17:00–23:00 | 政府網站 | [新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=0d97d351-1ac1-4585-8e7d-3594e8735fcc&id=61&mid=26&param=pn%3D1%26cid%3D21%26mid%3D26%26id%3D74) |
| 新莊思源夜市 | `way/1313165663` | 曾公告自 2024-10-01 暫停營業；目前是否復業待確認 | 曾公告暫停營業，現況待確認 | [民視：新莊思源夜市暫停營業報導（2024-09-29）](https://www.ftvnews.com.tw/news/detail/2024929W0124) |
| 鶯歌龍鳳夜市 | `way/1336425254` | 待確認：市府 2024 年頁面列每週二、五、六 16:30–21:30 | 待確認 | [新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=0893b8d8-00f6-492c-b971-a777d0c00b63&id=73&mid=60&param=pn%3D1%26mid%3D60%26id%3D0)、[TonightMarkets 龍鳳夜市資訊（非官方，與市府有差異）](https://tonightmarkets.com/night-markets/yinggelongfeng-night-market) |
| 樹林夜市 | `node/8365952045` | 17:00–22:00（來源未列每週休市日） | 政府網站 | [新北市政府市場處](https://www.newtaipeimarket.ntpc.gov.tw/tc/mapDetail.aspx?chk=db7c8652-b0d0-4f74-8ec6-0bcd917abc01&id=63&mid=73&param=pn%3D1%26mid%3D73%26id%3D0) |
| 汐止夜市 | `node/9276520217` | 17:00–23:00（來源未列每週休市日） | 政府網站 | [汐止區公所：汐止觀光夜市](https://www.xizhi.ntpc.gov.tw/home.jsp?id=0e5a1b2e43639bf0) |
| 汐止觀光夜市 | `node/9849235453` | 17:00–23:00（來源未列每週休市日） | 政府網站 | [汐止區公所：汐止觀光夜市](https://www.xizhi.ntpc.gov.tw/home.jsp?id=0e5a1b2e43639bf0) |
| 弘道街夜市 (星期二、五晚上) | `node/12092325283` | 每週二、五 17:00–23:00（2022 年報導；遇雨可能取消） | 非官方報導，現況待確認 | [鏡週刊：弘道街夜市（2022-07-22）](https://www.mirrormedia.mg/story/amp/20220722food004) |
| 廣州街觀光夜市 | `node/12146204001` | 每日 16:00–24:00 | 政府網站 | [臺北旅遊網](https://www.travel.taipei/zh-tw/attraction/details/1565) |
| 桃園夜市美食廣場 | `node/12531604654` | 未查得此美食廣場的個別營業時間 | 未查得 | [桃園觀光導覽網：桃園觀光夜市景點頁](https://travel.tycg.gov.tw/zh-tw/travel/attraction/969) |

## GeoJSON 欄位

- `opening_hours`：已找到明確時段的排程字串。未確定時段不填入，也不以空白代表歇業。來源只給時段未列休市日時，文字與備註會指出，不能據此保證每日營業。
- `opening_hours_text`：地圖顯示的中文時段或待確認說明。
- `opening_hours_status`：`official` 政府頁面有記載；`reported` 非官方報導；`needs_review` 名稱、場址或時段需確認；`not_found` 未查得；`suspension_reported` 找到暫停營業報導但未確認現況。
- `opening_hours_sources`：來源名稱與網址；對待確認資料，這些可能只是候選對照來源，請一起閱讀備註。
- `opening_hours_checked_on`：本次查詢日期，並非來源更新日期或現場查證日期。
- `opening_hours_note`：來源範圍、矛盾資訊與不確定原因。
- `opening_hours_original`：本次更正或移開的原始 OSM 時段，保留供追溯；不是現行營業時間。

點位名稱、座標與其他原有欄位保持不變。GeoJSON 頂層 timestamp 是原始 OSM 匯出時間；本次補充時段的來源與日期以各筆 opening_hours_* 欄位為準。

重新啟動 `python mrt_map.py` 並刷新網頁，點選夜市即可查看中文時間、查詢來源及待確認原因。營業時間補充不影響已計算的步行路線。
