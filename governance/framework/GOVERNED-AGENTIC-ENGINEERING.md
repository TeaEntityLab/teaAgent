# 規格驅動 × AgentOps：從自動生成到可治理自動化的工程框架（2026 事實校正版）

> **一句話總結**
> 規格是方向盤，測試是煞車，trace 是行車紀錄器，runtime guardrails 是車道護欄，human review 是高風險路口的紅綠燈。
> 真正的自動化不是把人拿掉，而是把人從低價值的重複檢查中釋放，集中到**規格、權限、風險與現實對齊**的關鍵決策點。
>
> **本版定位**：此框架已超越「規格驅動開發（SDD）」，進入 **Governed Agentic Engineering**——涵蓋治理、權限、觀測、回滾。所有外部數字皆回查一手來源並標註證據強度；高波動指標（如 GitHub 星數）一律降為趨勢訊號；尚未有穩定一手來源的能力宣稱一律改為條件語氣。版本可迭代，不用「定稿」。

---

## 0. 核心結論

大量測試與規格文件**確實**能大幅提升 Agent/LLM 自動生成品質，但它不是萬靈丹。

- **最大價值**：把模糊需求轉成可驗證邊界，讓 AI 的輸出可以被擋下、修正、回滾、比較、迭代。
- **最大局限**：測試只能驗證你**想得到**的東西，規格只能約束你**講清楚**的東西。
- **真正解法**：建立含「規格品質閘門」的多層治理閉環——

```
Intent Capture
  → Spec Draft
  → Spec Quality Gate        ← 最常被漏掉的一關：擋的是「規格錯」，不是「程式錯」
  → Permission Binding
  → Test Matrix
  → Executable Tests
  → Controlled Generation
  → Runtime Guardrails
  → Verification
  → Trace / Diff Review
  → Release / Rollback
  → Local Feedback (Spec Repair)
```

並補上 2026 年的**五個工程維度**：**上下文經濟學、突變測試（程式 + 規格）、權限邊界、執行期護欄、Zero-Trust Spec Registry 與 State Machine Constraints**。

> 為何拆成五個：AI/Agent 失敗很少是單點失敗，而是**多層失效**——意圖不清 → 規格錯 → 測試沒覆蓋 → Agent 走捷徑 → 工具越權 → trace 不足 → 錯誤被文件化。每個維度對應其中一層。

---

## 1. 核心價值（Core Values｜不可妥協的原則）

> 每條附「主張 / 具體方法 / 嚴格檢視（失效條件）」。

### CV-1 把模糊意圖轉成「可驗證邊界」
- **主張**：沒有規格時 LLM 只是在猜。規格的本質是**目標函數**，作用是降低語義自由度。
- **具體方法**：任何非瑣碎任務先寫出「輸入 / 輸出 / 錯誤碼 / 安全約束 / 驗收條件」五欄。
- **嚴格檢視**：此價值**假設規格本身正確**。若 Intent Spec 內含矛盾，Agent 會完美實作一個無效系統 → 由 CV-4 + Spec Quality Gate 補。

### CV-2 用「外部現實檢查」取代自我宣稱
- **主張**：Agent 最危險的行為是「錯了卻以為對了 / 沒做完卻報告完成 / 過 happy path 卻破壞 edge case」。測試把「看起來合理」轉為可執行驗證，防止假完成與 reward hacking。
- **具體方法**：任何「我修好了」必須對應一個綠燈狀態的**可重跑證據**。
- **嚴格檢視**：錯誤測試比沒有測試更危險——它給 Agent 錯誤的獎勵訊號。測試本身必須被審查（見 T5 規格突變）。

### CV-3 文件「密度 > 長度」；「可執行 > 可閱讀」
- **主張**：太厚的規格塞爆上下文、互相矛盾、稀釋優先級。LLM 吃**具體範例與可執行測試**，不吃抽象形容詞。
- **具體方法**：用短規格 + 表格 + 範例 + 可執行測試，取代長篇自然語言。
- **嚴格檢視**：過高密度的機器可讀規格可能降低人類新手交接性；此價值針對「給機器讀的規格」。

### CV-4 「規格符合現實」優先於「程式碼符合規格」
- **主張**：測試只能證明「程式碼符合規格」，**不能證明「規格符合現實」**。規格驅動**不是需求正確性的保證，而是讓需求錯誤更早暴露的機制**。
- **具體方法**：進實作前加 **Spec Quality Gate**，強制標註真實負載、延遲、資料量、法規與安全邊界等現實假設。
- **嚴格檢視**：只能靠對齊現實的回饋迴路（真實流量、可觀測性、事故覆盤）逐步修正規格。

### CV-5 「職責分離」優先於「Agent 數量」
- **主張**：同一個 Agent 同時定義成功、產生答案、修改測試、宣稱完成，會直接導致 reward hacking。
- **具體方法**：把 `AGENT_RULES.md` 的「不可弱化測試、改測試需人工審查」從**道德勸說升級為環境結構限制**（測試檔唯讀、測試與程式變更分開審查）。
- **嚴格檢視**：過度切分增加跨 Agent 語義漂移，必須以規格為共同參照物。

### CV-6 讓人類「只出現在最值得出現的位置」
- **主張**：自動化是為了把人類審查集中在高風險決策閘門（認證、付款、刪除、部署、migration）。
- **具體方法**：建立強制人工審查清單，低風險變更由自動化放行。
- **嚴格檢視**：人類在大量 PR 中會疲勞，高風險清單必須極精簡，並由自動化（突變測試、靜態掃描）預先過濾。

### CV-7 上下文經濟學：主動查詢 > 被動塞入
- **主張**：把完整資料庫 schema 一次塞給 Agent 會引發幻覺與效能下降。規格應是**可隨選查詢的 API**。
- **具體方法**：建立 Spec Registry，Agent 以工具主動拉取**當前任務所需的局部規格**。
- **嚴格檢視**：動態查詢引入延遲與權限控管挑戰，必須實作 Zero-Trust（見 §5）。

### CV-8 規格即權限邊界（Permission Boundary）
- **主張**：在 Agent 工作流中，規格不只描述「做什麼」，更定義 Agent「**被允許做什麼**」。Agent 不應靠自然語言猜測自己能否改檔案、呼叫 API、改測試、跑 migration、部署。
- **具體方法**：每份 `SPEC.md` 附 `Allowed Actions / Forbidden Actions / Requires Human Review` 三欄，並由 **runtime policy 強制執行**。
- **嚴格檢視**：若權限只寫在 markdown、無工具層攔截，Agent 仍可越權。CV-8 必須搭配 sandbox、唯讀測試、MCP scope、audit log。

---

## 2. 策略（Strategies｜完整 AgentOps 九段治理工作流）

| 階段 | 主要產物 | 核心風險 | 防禦防線 |
|---|---|---|---|
| 1. Intent Capture | Intent Spec | 做錯方向 | Why 與 Non-goals 定義 |
| 2. Spec Draft | Contract / Behavior / Risk Spec | 規格矛盾 | Spec Reviewer 檢查 |
| 3. **Spec Quality Gate** | 人工/自動放行標記 | 規格不可測或缺漏 | 針對邊界與假設立閘門 |
| 4. Permission Binding | Allowed / Forbidden / Human Review | Agent 越權 | 執行期 Policy 與 Sandbox |
| 5. Test Matrix | P0–P3 測試案例 | 測試漏洞 | 程式突變 + 規格突變 |
| 6. Controlled Generation | 程式碼 / Artifact | 幻覺與實作捷徑 | 受控工具 + Runtime Guardrails |
| 7. Verification | 測試報告（綠燈） | 假完成 (reward hacking) | 唯讀測試檔 + 確定性 CI |
| 8. Trace / Diff Review | SPEC_DIFF.md + Trace 日誌 | 錯誤文件化、不可追責 | 人類 + Reviewer Agent 雙審 |
| 9. Local Feedback | LOCAL_FEEDBACK.md | 系統重複犯錯 | Anti-regression Rule |

**四層規格**：Intent（Why）→ Contract（What, schema 化）→ Behavior（How, Given-When-Then）→ Risk（禁區 + Human Review）。

**三層測試**：Deterministic（unit/integration/schema/type/lint/migration/contract）→ Scenario（使用者流程）→ Adversarial（prompt injection、權限繞過、SQL injection、race condition、超長/空值/unicode、併發）。

---

## 3. 戰術（Tactics｜可立即落地的實作機制）

### T0 最小可行五檔
`SPEC.md`（含 SPEC_VERSION）、`TEST_MATRIX.md`、`AGENT_RULES.md`、`LOCAL_FEEDBACK.md`、`DONE_CHECKLIST.md`。

### T1 SPEC.md
```markdown
# SPEC.md
## Goal / Non-goals
## Inputs / Outputs (附 schema)
## Acceptance Criteria (每條可測)
## Edge Cases / Failure Conditions
## Security / Privacy Constraints
## Allowed Actions / Forbidden Actions / Requires Human Review   # CV-8
## Real-world Assumptions (流量/延遲/資料量/法規)               # CV-4
## Test Plan
SPEC_VERSION = 2026-06-09-login-v3
```

### T2 TEST_MATRIX.md（優先級分層）
以表格列出 `Case / Input / Expected / Type / Priority`，先確保 **P0（安全/資料/金錢/權限）與 P1（核心邏輯）絕對覆蓋**。

```markdown
| Case | Input | Expected | Type | Priority |
|---|---|---|---|---|
| valid login | correct email/password | token returned | integration | P0 |
| wrong password | wrong password | INVALID_CREDENTIALS | integration | P0 |
| unknown email | fake email | same generic error | security | P0 |
| 5 failed attempts | repeated wrong password | account locked | scenario | P0 |
| empty email | "" | validation error | unit | P1 |
```

### T3 AGENT_RULES.md（環境硬化）
```markdown
## Allowed：新增測試 / helper；重構低風險內部函式；更新文件以反映實作
## Forbidden：刪除或弱化既有測試；跳過 type check；mock 掉真正錯誤；改 security policy；直接 deploy
## Requires Human Review：authentication / authorization / payment / migration / production config；修改測試以讓失敗測試通過
```
> 實證：RHB（arXiv 2026）顯示簡單的環境硬化能把 reward hacking exploit 率降 5.7 個百分點（相對降幅 87.7%）且不犧牲任務成功率；ImpossibleBench 另顯示隔離/唯讀測試檔可把作弊率壓到趨近於零。故此條應為環境限制，不是口頭規範。

### T4 Code Mutation Testing（程式突變）
隨機竄改 Coder Agent 程式邏輯（如 `>= 5` → `> 5`），驗證現有測試是否會報錯。**未報錯 = 測試無效**，退回 Test Agent 補強。

### T5 Spec Mutation Testing（規格突變）
不只突變程式，也**突變規格**，驗證 Test Matrix 與 Reviewer 是否抓得到漂移：
- 將 `INVALID_CREDENTIALS` 改成 `USER_NOT_FOUND`（測安全 AC）
- 將 token expiry 從 15 分鐘改成 30 天（測風險 AC）
- 移除 `requires human review` / 將 `read-only tests` 改成 writable（測治理層）

若這些突變沒觸發失敗或審查，代表品質駕馭層失效。

### T6 Spec Diff Review（防止錯誤文件化）
逆向規格生成很好，但**禁止靜默覆蓋正式規格**：Agent 產 `SPEC_DIFF.md` → 標記新增/刪除/衝突/行為改變 → Reviewer Agent 檢查是否與原 Intent 衝突 → Human 只審 high-risk diff → 通過才併入。
禁止三種 drift：靜默改寫 AC；以實作結果反向合理化錯誤需求；把 failing behavior 寫成新規格。

### T7 State Machine Constraints（狀態機斷言）
在 DB/狀態層加前後置斷言取代單純 I/O 檢查，捕捉 race condition。例：登入不僅斷言回傳 token，還須斷言
`SELECT state FROM user_sessions WHERE user_id=X` 必為 `ACTIVE`，且**同時間舊 token 必須被標記 `REVOKED`**。
**反回歸規則**：任何涉及狀態變更的任務，AC 必須明確宣告 Pre/Post-conditions，否則拒絕執行。

### T8 LOCAL_FEEDBACK.md（失敗學習機制｜閉環的關鍵）
每次失敗都必須記錄，否則系統只會重犯同樣錯：
```markdown
## Step / Evidence / Error Type / Root Cause / Correction / Verification / Anti-regression Rule
```
兩條原則：**沒有 Evidence 的修正不算修正；沒有 Anti-regression Rule 的修正只算臨時補丁。**

### Spec Quality Gate 檢查清單（進實作前必過）
```markdown
- [ ] Goal 單一且可驗證；Non-goals 明確
- [ ] Inputs / Outputs 有 schema；每條 AC 可測
- [ ] 有 P0 風險分類；有 forbidden behavior
- [ ] 有 rollback condition；有 human review trigger
- [ ] 不存在互相矛盾條件
- [ ] 已標明真實世界假設(流量/延遲/資料量/法規/安全邊界)
```

---

## 4. 分級成本模型（什麼任務值得這麼重的治理？）

> 回應 §8 反方論證「規格成本大於收益」。治理強度必須隨風險縮放，過度投入本身就是浪費。

| 等級 | 任務範例 | 治理強度 | 明確「不要過度投入」 |
|---|---|---|---|
| L1 | typo、CSS、小欄位、文案調整 | task brief + 既有測試 | 不跑突變測試、不做 Spec Registry |
| L2 | 新增 API、表單、資料轉換、權限規則 | mini spec + test matrix + CI | 視風險選擇是否跑 mutation |
| L3 | auth、payment、permission、migration、delete、deploy、AI 代操帳號 | 全流程治理（四層規格 + 突變 + 狀態機 + Zero-Trust Registry） | 必須 human gate / trace / rollback，不可省 |

---

## 5. Zero-Trust Spec Registry（動態規格 via MCP 的安全最低要求）

S4「動態規格 via MCP」的前提**絕非**「把文件做成工具就好」，而是把規格視為「具備身份、權限、審計、版本與不可竄改紀錄的**受控資源**」。對應 2026 年 MCP 已知協定層弱點（見 §6），最低架構要求如下：

1. **Scope 強制綁定**：每個 Spec Endpoint 聲明最小必要存取範圍；**若 MCP 規格或實作支援 incremental consent，應採逐步授權而非一次性全域授權**。
2. **最小知識原則**：Agent 僅能讀取與當前 Ticket/Task 直接相關的 Spec Subset，**不可 dump 全局架構**。
3. **防能力偽造**：能力須通過**密碼學驗證（capability attestation）**（如 X.509 憑證 / 簽章 + 持續驗證）；不允許 server 自稱未經驗證的能力。
4. **消除隱式互信**：多個 MCP server 之間**不得隱式信任傳遞**；每次互動驗證身份與授權（對齊 CSA Agentic Trust Framework 2026/02 的「no implicit trust / 推理與行動分離」原則）。
5. **嚴格唯讀與版本鎖定**：高風險域（Authentication / Payment / Authorization）規格**絕對唯讀且綁定特定 Commit Hash**。
6. **全鏈路觀測**：每次規格查詢都在 OpenTelemetry 或同級系統留下不可竄改 trace。
7. **破壞性操作須人在迴路**：資料刪除、外部傳輸、金流、批次改寫、對外通訊以風險分類標註並強制人工核可。
8. **Ticket-bound Access**：每次規格查詢必須綁定 `ticket_id / task_id / spec_version`，**不允許無任務背景的查詢**。
9. **Spec Read Receipts**：Agent 回報結果時須列出「本次讀過哪些 spec endpoint / version / hash」，讓審查者能追溯輸出依據。
10. **Deny-by-default Policy**：未在 `SPEC.md` 或 policy manifest 列明的工具與規格端點，**一律拒絕**。

> 第 8–10 條把 Spec Registry 從「安全建議」升級為「可審計系統」。

---

## 6. 截至 2026-06 的現況觀察與證據強度

> **[強證據]** 官方文件/論文/一手報告；**[中證據]** 二手報導/產業觀察；**[弱證據]** 社群熱度/星數/推測。

**[強證據+中證據] SDD 已成主流典範**
GitHub Spec Kit（2025/09 於 GitHub 開源）的 repo 與 README 描述其工作流：coding agent 檢查 constitution/spec/plan/tasks、解析 `tasks.md`、依任務順序執行、遵循 TDD plan——[強]。其「支援 30+ 個 Agent」屬生態整合與社群報導——[中]。OpenSpec 採 `proposal → apply → archive` 三段狀態機；AWS Kiro、Cursor、Claude Code、Google Antigravity 等亦推出各自版本。核心轉變：**傳統規格給人讀，SDD 規格作為驗證關卡執行**（arXiv《Spec-Driven Development: From Code to Contract》, 2026/02）——[強]。

**[強證據] 高採用、低信任**
- Stack Overflow 2025 開發者調查（官方頁，49,000+ 份回應）：**84%** 使用或計畫使用 AI（高於 2024 的 76%）；**46% 不信任** AI 輸出準確性（高於 2024 的 31%）。官方並列出僅 33% 信任、約 3% 高度信任、好感度自 72% 降到 60%。
- JetBrains State of Developer Ecosystem 2025（官方，24,534 名開發者）：**85%** 經常使用 AI、**62%** 倚賴至少一個 AI coding assistant/agent/editor、68% 預期 AI 熟練度將成求職門檻——[強]。JetBrains 並明確指出「AI 使用多半未系統化，開發者只是 ad hoc 在用」——[強]。AI Pulse 2026/01：**90%** 在工作中使用至少一個 AI 工具——[強]。（另有二手分析稱僅約 44% 將 AI 全部/部分整合進工作流——[中]，採用語氣引用即可。）

**[強證據] Reward hacking 可量測，環境硬化有效**
Reward Hacking Benchmark（Thaman, arXiv 2605.02964, 2026/05）實測 13 個前沿模型：exploit 率 **0%（Claude Sonnet 4.5）到 13.9%（DeepSeek-R1-Zero）**，RL 後訓練與更高 reward hacking 顯著相關；**簡單環境硬化使 exploit 率降 5.7 個百分點（相對降幅 87.7%，CI 4.8–6.6）且不犧牲任務成功率**。另：ImpossibleBench 顯示隔離/唯讀測試檔可把作弊率壓到趨近於零（獨立來源）。

**[強證據] MCP 安全是協定層問題，非僅實作 bug**
arXiv《Breaking the Protocol》（Maloyan & Namiot, 2601.17549, 2026/01）對 MCP 規格 v1.0 的首份系統性分析，指出三項**協定層**弱點：(1)**缺乏能力驗證（capability attestation）**——server 可自稱任意權限，原本只宣告 `resources` 者可後續呼叫 `sampling/createMessage`；(2)**雙向 sampling 無來源驗證**——server 可用「user」角色注入 prompt，主流 host（Claude Desktop / Cursor / Continue）介面**無任何視覺區隔**；(3)**多 server 隱式互信傳遞**——Server A 的回應可影響 Server B 的調用且無來源追蹤。該研究實測 MCP 架構使攻擊成功率較非 MCP 整合**放大 23–41%**；其提出的向後相容擴充 **ATTESTMCP**（能力驗證 + 訊息驗證 + 來源標記 + 隔離強制）可把整體 ASR 自 **52.8% 降到 12.4%**，中位延遲開銷僅 8.3ms。另 NSA MCP 安全 CSI（2026/05/20）指出「未驗證任務傳遞」會造成越權與敏感脈絡外洩（ACE 對應 CWE-77/78/94/95）。實作層事故 CVE-2025-49596（CVSS 9.4，MCP Inspector 未授權 RCE）則屬**實作 bug**，與上述協定弱點是不同層次的問題。

**[弱證據] 開源 SDD 工具的 GitHub 星數**
各彙整來源報導 Spec Kit、OpenSpec 星數達數萬級，但星數高波動且多為二手，僅作典範轉移的趨勢訊號，**不作為方法論成立的核心依據**。

---

## 7. 關鍵字索引（關鍵概念 + 簡潔說明）

| 關鍵字 | 簡潔說明 |
|---|---|
| Spec as Objective Function | 規格 = LLM 目標函數，作用是降低語義自由度。 |
| Spec Quality Gate | 進實作前的規格品質閘門，擋「規格錯/矛盾/不可測」，非「程式錯」。 |
| Permission Boundary (CV-8) | 規格亦定義 Agent 被允許做什麼，須由 runtime policy 強制。 |
| Reward Hacking / Test Gaming | Agent 為過測試而 hard-code、刪測試、弱化 assertion、mock 掉真錯。 |
| Code / Spec Mutation Testing | 突變程式或規格，驗證測試與審查層是否真會抓錯。 |
| State Machine Constraints | 以前/後置狀態斷言取代單純 I/O 斷言，捕捉 race condition。 |
| Capability Attestation | 以密碼學驗證 MCP server 宣告的能力，防自我聲明偽造。 |
| Implicit Trust Propagation | 多 MCP server 間無隔離邊界，一台被攻陷可波及其餘。 |
| Zero-Trust Spec Registry | 規格作為具身份/權限/審計/版本的受控資源，而非靜態長文。 |
| Ticket-bound Access / Read Receipts / Deny-by-default | 綁任務查詢、列出讀過的規格、未列明一律拒絕——讓 Registry 可審計。 |
| Runtime Guardrails | 執行期護欄（sandbox / AST 攔截 / 唯讀測試 / 混沌注入）優先於厚規格。 |
| Spec Diff Review | 逆向生成的規格 diff 須經審查才併入，禁止靜默覆蓋。 |
| 分級成本模型 (L1/L2/L3) | 治理強度隨風險縮放，L1 直接放行，強治理只給 L3。 |
| 證據強度分級 | [強]一手論文/官方；[中]二手報導；[弱]星數/熱度/推測。 |

---

## 8. 如何取得教材／生成對應素材

**A. 直接取得**：開源 SDD 工具鏈（Spec Kit 的 `specify` CLI、OpenSpec 的 `specs/`+`changes/` 結構）當教材骨架；權威安全依據（NSA MCP CSI、CSA Agentic Trust Framework、arXiv《Breaking the Protocol》之 ATTESTMCP 設計）；實證教材（RHB、ImpossibleBench）。

**B. 用本方法論生成素材**：餵 Intent Spec → Spec Agent 補 `SPEC.md` → 過 Spec Quality Gate → Test Agent 生 `TEST_MATRIX.md` → 程式突變 + 規格突變篩無效測試 → Spec Diff Review 產 `SPEC_DIFF.md` 供審 → `AGENT_RULES.md`/`DONE_CHECKLIST.md` 設唯讀範本套用新專案。

**C. 教學落地**：內容深度 > 製作精緻度；每概念配「壞範例 → 好範例」對照，比抽象定義更易吸收。

---

## 9. 嚴格檢視（L3 批判性思考檢查）

**1. 假設稽核**：核心假設「人類能定義清晰且無矛盾的 Intent Spec」。若初始意圖即邏輯互斥，下游所有檢驗都淪為「完美執行錯誤指令」的幫兇——這是 Spec Quality Gate（CV-4）存在的理由，也是整套方法論的天花板。

**2. 證據檢核**：
- *事實*：Stack Overflow / JetBrains 一手調查；RHB 的 exploit 率與 5.7pp/87.7% 硬化降幅；《Breaking the Protocol》三項協定弱點與 ATTESTMCP 52.8%→12.4%；CVE-2025-49596。
- *推論*：「隔離/唯讀測試能阻斷作弊路徑」由基準結果外推到一般部署。
- *假設*：MCP 動態規格能淨降上下文污染（取決於工具延遲與權限設計）；「44% 整合」為二手分析，以中證據對待。
- *價值判斷*：「人應專注高風險決策」是工程資源最佳化取向，非可證偽事實。

**3. 反方最強論證（Steelman）**：對大量一次性/低複雜度任務，維護 Spec Quality Gate 與突變測試的成本**遠大於**直接讓 Agent 試錯修復。此反駁成立——故以 §4 分級成本模型回應：L1 直接放行，強治理只套用於 L2/L3。

**4. 謬誤掃描**：避免「覆蓋率 100% = 系統安全」的相關≠因果；避免「靜態規格 vs 動態護欄」假兩難（互補）；避免以星數/熱度充當品質證據（已降弱證據）。

**5. 可證偽性**：
- 若在唯讀測試 + 突變測試 + 狀態機斷言齊備下，高風險模組業務邏輯損壞率仍未顯著低於傳統開發 → 戰術層失效。
- 若 Zero-Trust MCP Registry 的授權握手與工具調用 latency 導致任務超時率過高，抵消省下的 token 效益 → 動態規格策略須降級。
- 若 Spec Diff Review 的人工審查負荷高於直接維護靜態規格 → T6 失效。

---

## 附錄：版本事實校正紀錄（LOCAL_FEEDBACK）

| 校正項 | 處置 |
|---|---|
| Spec Kit / OpenSpec 星數 | 降為 [弱證據] 趨勢訊號，不寫死星數 |
| Spec Kit「支援 30+ Agent」 | 降為 [中證據]（生態/社群報導，非官方明列） |
| JetBrains「13% 跨 SDLC」 | 刪除（查無一手來源）；改用官方「ad hoc、未系統化」框架；「44% 整合」標 [中證據] |
| Stack Overflow 信任數字 | 補全 46% 不信任 / 約 3% 高度信任 / 好感度 72%→60%，標 [強證據] |
| RHB 硬化降幅 | 補入精確數字 5.7pp / 87.7%（CI 4.8–6.6），ImpossibleBench 獨立列來源 |
| MCP 協定弱點 | 以《Breaking the Protocol》一手三項弱點 + ATTESTMCP（52.8%→12.4%）取代籠統敘述；緩解方案正名為 ATTESTMCP（非 MCPSec） |
| MCP incremental scope consent | 改條件語氣（「若規格/實作支援則採用」），不寫死規格能力 |

**反回歸規則**：凡引用外部數字必回查一手來源（官方報告/論文/CVE）；二手彙整站僅作線索；高波動指標（星數、熱度）一律降為趨勢訊號；尚未確認的能力宣稱一律改條件語氣。
