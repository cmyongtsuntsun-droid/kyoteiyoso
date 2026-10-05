(() => {
  "use strict";
  const languages = ["en", "zh-cn", "zh-tw", "ko"];
  const first = location.pathname.split("/").filter(Boolean)[0] || "ja";
  const lang = languages.includes(first.toLowerCase()) ? first.toLowerCase() : "ja";
  if (lang === "ja") return;
  const ix = { en: 0, "zh-cn": 1, "zh-tw": 2, ko: 3 };
  const weekday = {
    en: {"日":"Sun","月":"Mon","火":"Tue","水":"Wed","木":"Thu","金":"Fri","土":"Sat"},
    "zh-cn": {"日":"周日","月":"周一","火":"周二","水":"周三","木":"周四","金":"周五","土":"周六"},
    "zh-tw": {"日":"週日","月":"週一","火":"週二","水":"週三","木":"週四","金":"週五","土":"週六"},
    ko: {"日":"일","月":"월","火":"화","水":"수","木":"목","金":"금","土":"토"}
  };
  const fixed = {
    "本日": ["Today", "今天", "今天", "오늘"],
    "結果": ["Results", "结果", "結果", "결과"],
    "予定": ["Scheduled", "预定", "預定", "예정"],
    "全場": ["All venues", "全部场馆", "全部場館", "전체 경기장"],
    "選手分析": ["Racer analysis", "选手分析", "選手分析", "선수 분석"],
    "本日の予想": ["Today's predictions", "今日预测", "今日預測", "오늘의 예상"],
    "リンク集": ["Links", "链接", "連結", "링크"],
    "データソース:": ["Data sources:", "数据来源：", "資料來源：", "데이터 출처:"],
    "→ 本日の予想トップ": ["→ Today's predictions", "→ 今日预测", "→ 今日預測", "→ 오늘의 예상"],
    "本日の予想トップ": ["Today's predictions", "今日预测", "今日預測", "오늘의 예상"],
    "予測": ["Rank", "预测", "預測", "예측"],
    "艇": ["Boat", "艇", "艇", "보트"],
    "選手": ["Racer", "选手", "選手", "선수"],
    "全国勝率": ["National win rate", "全国胜率", "全國勝率", "전국 승률"],
    "M2連率": ["Motor top-two rate", "马达前二率", "馬達前二率", "모터 2연대율"],
    "展示T": ["Trial time", "展示时间", "展示時間", "전시 타임"],
    "勝率(AI)": ["AI win probability", "AI胜率", "AI勝率", "AI 승률"],
    "1着率": ["Win rate", "胜率", "勝率", "1위율"],
    "2連対率": ["Top-two rate", "前二率", "前二率", "2연대율"],
    "3連対率": ["Top-three rate", "前三率", "前三率", "3연대율"],
    "平均ST": ["Avg. start timing", "平均起步时机", "平均起步時機", "평균 스타트 타이밍"],
    "ST安定度(σ)": ["ST consistency (σ)", "ST稳定度（σ）", "ST穩定度（σ）", "ST 안정도(σ)"],
    "展示平均": ["Avg. trial time", "平均展示时间", "平均展示時間", "평균 전시 시간"],
    "コース別成績": ["Results by lane", "按赛道统计", "按航道統計", "코스별 성적"],
    "場別成績": ["Results by venue", "按场地统计", "按場地統計", "경기장별 성적"],
    "直近10走": ["Last 10 races", "最近10场", "最近10場", "최근 10경주"],
    "コース": ["Lane", "赛道", "航道", "코스"],
    "場": ["Venue", "场地", "場地", "경기장"],
    "進入": ["Entry lane", "进场赛道", "進場航道", "진입 코스"],
    "着順": ["Finish", "名次", "名次", "착순"],
    "締切": ["Cutoff", "截止", "截止", "마감"],
    "風": ["Wind", "风", "風", "바람"],
    "波": ["Waves", "浪", "浪", "파도"],
    "信頼度": ["Confidence", "信心", "信心", "신뢰도"],
    "本命": ["AI pick", "AI看好", "AI看好", "AI 추천"],
    "3連単": ["trifecta", "三连单", "三連單", "삼연승식"],
    "舟券": ["betting ticket", "舟券", "舟券", "승선권"],
    "出走数順": ["Most starts", "出场次数", "出賽次數", "출전 횟수"],
    "全級別": ["All classes", "全部级别", "全部級別", "전체 등급"],
    "選手データ": ["Racer statistics", "选手数据", "選手資料", "선수 데이터"],
    "AI本命": ["AI pick", "AI看好", "AI看好", "AI 추천"],
    "3連単推奨": ["Suggested trifecta", "三连单建议", "三連單建議", "삼연승식 추천"],
    "選手名": ["Racer name", "选手姓名", "選手姓名", "선수명"],
    "出走": ["Starts", "出场", "出賽", "출전"],
    "2連対": ["Top-two", "前二", "前二", "2연대"],
    "3連対": ["Top-three", "前三", "前三", "3연대"],
    "あわせて読みたい": ["Read next", "延伸阅读", "延伸閱讀", "함께 읽기"],
    "注目レース": ["Featured races", "重点赛事", "焦點賽事", "주요 경주"],
    "的中": ["Hits", "命中", "命中", "적중"],
    "対象日:": ["Date:", "日期：", "日期：", "날짜:"],
    "予測生成:": ["Generated:", "生成时间：", "產生時間：", "생성:"],
    "登番": ["Registration no.", "注册编号", "登錄編號", "등록 번호"],
    "級": ["Class", "级别", "級別", "등급"],
    "直近調子": ["Recent form", "近期状态", "近期狀態", "최근 컨디션"],
    "閉じる": ["Close", "关闭", "關閉", "닫기"],
    "行クリックで詳細": ["Click a row for details", "点击行查看详情", "點擊列查看詳細資料", "행을 클릭해 상세 보기"]
  };
  const splitEdges = (raw, value) => {
    const left = raw.match(/^\s*/)?.[0] || "";
    const right = raw.match(/\s*$/)?.[0] || "";
    return left + value + right;
  };
  function dynamic(value) {
    if (fixed[value]) return fixed[value][ix[lang]];
    let m = value.match(/^(\d{1,2}\/\d{1,2})\(([日月火水木金土])\)$/);
    if (m) return m[1] + " (" + weekday[lang][m[2]] + ")";
    m = value.match(/^的中\s*([\d,]+)\s*\/\s*([\d,]+)$/);
    if (m) return {en:"Hits "+m[1]+" / "+m[2],"zh-cn":"命中 "+m[1]+" / "+m[2],"zh-tw":"命中 "+m[1]+" / "+m[2],ko:"적중 "+m[1]+" / "+m[2]}[lang];
    m = value.match(/^全([\d,]+)レース$/);
    if (m) return {en:m[1]+" races","zh-cn":m[1]+"场赛事","zh-tw":m[1]+"場賽事",ko:"경주 "+m[1]+"개"}[lang];
    m = value.match(/^対象日:\s*(\S+)\s*\/\s*全([\d,]+)レース\s*\/\s*予測生成:\s*(.+)$/);
    if (m) return {en:"Date: "+m[1]+" / "+m[2]+" races / Generated: "+m[3],"zh-cn":"日期："+m[1]+" / "+m[2]+"场赛事 / 生成时间："+m[3],"zh-tw":"日期："+m[1]+" / "+m[2]+"場賽事 / 產生時間："+m[3],ko:"날짜: "+m[1]+" / 경주 "+m[2]+"개 / 생성: "+m[3]}[lang];
    m = value.match(/^→\s*(.+?)\s+全([\d,]+)レースの予想テーブルを見る$/);
    if (m) return {en:"→ "+m[1]+": view predictions for all "+m[2]+" races","zh-cn":"→ "+m[1]+"：查看全部"+m[2]+"场赛事预测","zh-tw":"→ "+m[1]+"：查看全部"+m[2]+"場賽事預測",ko:"→ "+m[1]+": 전체 "+m[2]+"개 경주 예상 보기"}[lang];
    m = value.match(/^(\d{1,2}\/\d{1,2}\([日月火水木金土]\)) の予想$/);
    if (m) return dynamic(m[1]) + (lang === "en" ? " predictions" : lang === "zh-cn" ? "预测" : lang === "zh-tw" ? "預測" : " 예상");
    m = value.match(/^信頼度\s*(\d+)位$/);
    if (m) return {en:"Confidence #"+m[1],"zh-cn":"信心 第"+m[1]+"名","zh-tw":"信心 第"+m[1]+"名",ko:"신뢰도 "+m[1]+"위"}[lang];
    m = value.match(/^本命\s*(\d+)\s*号艇(.*)$/);
    if (m) return {en:"AI pick: Boat "+m[1]+m[2],"zh-cn":"AI看好："+m[1]+"号艇"+m[2],"zh-tw":"AI看好："+m[1]+"號艇"+m[2],ko:"AI 추천: "+m[1]+"번 보트"+m[2]}[lang];
    m = value.match(/^AI勝率\s*([\d.]+)%$/);
    if (m) return {en:"AI win probability "+m[1]+"%","zh-cn":"AI胜率 "+m[1]+"%","zh-tw":"AI勝率 "+m[1]+"%",ko:"AI 승률 "+m[1]+"%"}[lang];
    m = value.match(/^締切\s*(\d{1,2}:\d{2})$/);
    if (m) return {en:"Cutoff "+m[1],"zh-cn":"截止 "+m[1],"zh-tw":"截止 "+m[1],ko:"마감 "+m[1]}[lang];
    m = value.match(/^風\s*([\d.]+)m\s*\/\s*波\s*([\d.]+)cm$/);
    if (m) return {en:"Wind "+m[1]+" m / Waves "+m[2]+" cm","zh-cn":"风 "+m[1]+"米 / 浪 "+m[2]+"厘米","zh-tw":"風 "+m[1]+"公尺 / 浪 "+m[2]+"公分",ko:"바람 "+m[1]+"m / 파도 "+m[2]+"cm"}[lang];
    m = value.match(/^(\d+) 選手中 (\d+) 名を表示 \(行クリックで詳細\)$/);
    if (m) return {en:m[2]+" of "+m[1]+" racers shown (click a row for details)","zh-cn":"显示 "+m[2]+" / "+m[1]+" 名选手（点击行查看详情）","zh-tw":"顯示 "+m[2]+" / "+m[1]+" 名選手（點擊列查看詳細資料）",ko:m[1]+"명 중 "+m[2]+"명 표시 (행을 클릭해 상세 보기)"}[lang];
    m = value.match(/^集計期間:\s*(\S+)\s*〜\s*(\S+)\s*\/\s*対象\s*(\d+)\s*選手$/);
    if (m) return {en:"Reporting period: "+m[1]+" to "+m[2]+" / "+m[3]+" racers","zh-cn":"统计期间："+m[1]+"至"+m[2]+" / "+m[3]+"名选手","zh-tw":"統計期間："+m[1]+"至"+m[2]+" / "+m[3]+"名選手",ko:"집계 기간: "+m[1]+"~"+m[2]+" / 선수 "+m[3]+"명"}[lang];
    m = value.match(/^（AI勝率\s*([\d.]+)%）[。．]?(.*)$/);
    if (m) {
      const reasonWords = {
        "1コースからのイン逃げが期待できる": ["Lane 1 is favored to lead from the inside", "1号赛道有望以内道领先", "1號航道有望從內側領先", "1코스 인코스 선두가 기대됨"],
        "全国勝率がレース内トップ": ["Highest national win rate in this race", "本场全国胜率最高", "本場全國勝率最高", "이번 경주 전국 승률 1위"],
        "モーター2連率が上位": ["High motor top-two rate", "马达连胜率靠前", "馬達連勝率靠前", "모터 2연대율 상위"],
        "展示タイムが最速": ["Fastest trial time", "试航时间最快", "試航時間最快", "전시 타임 최고"],
        "総合力でわずかに上位": ["Slightly stronger overall", "综合实力略占优势", "綜合實力略佔優勢", "종합 전력이 근소하게 우세"]
      };
      const reason = m[2].replace(/[。．]$/, "").split("・").map(part => reasonWords[part]?.[ix[lang]] || part).filter(Boolean).join("; ");
      const prefix = {en:"AI win probability "+m[1]+"%.","zh-cn":"AI胜率 "+m[1]+"%。","zh-tw":"AI勝率 "+m[1]+"%。",ko:"AI 승률 "+m[1]+"%."}[lang];
      return reason ? prefix + " " + reason + "." : prefix;
    }
    m = value.match(/^(\d+)場\s*\/\s*全(\d+)レース$/);
    if (m) return {en:m[1]+" venues / "+m[2]+" races","zh-cn":m[1]+"个场馆 / "+m[2]+"场比赛","zh-tw":m[1]+"個場館 / "+m[2]+"場比賽",ko:m[1]+"개 경기장 / "+m[2]+"경주"}[lang];
    return null;
  }
  function translateNode(node) {
    const raw = node.nodeValue || "";
    const value = raw.trim().replace(/\s+/g, " ");
    if (!value) return;
    const replacement = dynamic(value);
    if (replacement && replacement !== value) node.nodeValue = splitEdges(raw, replacement);
  }
  function translateTree(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (parent && parent.closest("script,style,noscript,.site-language-control,.site-related-links")) continue;
      translateNode(node);
    }
  }
  translateTree(document.body);
  new MutationObserver(records => records.forEach(record => {
    if (record.type === "characterData") translateNode(record.target);
    else record.addedNodes.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) translateNode(node);
      else if (node.nodeType === Node.ELEMENT_NODE) translateTree(node);
    });
  })).observe(document.body, { childList: true, subtree: true, characterData: true });
})();
