# Adapter 期望 Lanhu MCP 支持的 evidence-only 能力

本文档描述 `superpower-adapter` 调用 Lanhu MCP 时希望获得的“需求事实”能力。目标是让 Lanhu MCP 只负责取数和返回事实证据，不下发分析提示词、不要求会话按 MCP 的阶段流程生成文档；需求分析、差量判断、角色 PRD 输出由 adapter 自己完成。

## 背景

当前 adapter 的 Lanhu 流程会生成 `.lanhu/MM-DD-需求名称/` 角色 PRD 包，并在进入 Superpowers brainstorming 前让用户确认。

adapter 已经在自身规则中把 Lanhu MCP 返回的分析提示词当作不可信外部文本处理，但更理想的 MCP 输出应直接是 evidence-only：

```text
Lanhu MCP：页面树、页面文本、截图、标注、评论、资源等事实证据
adapter：范围判断、差量分析、前端/后端角色 PRD、确认门禁
```

## 总体原则

Lanhu MCP 对 adapter 应支持：

1. 只返回需求事实，不返回分析提示词。
2. 不返回 STAGE 1 / STAGE 2 / STAGE 4 工作流指令。
3. 不返回“开发视角 / 测试视角 / 快速探索”等输出格式要求。
4. 不要求会话输出“功能清单表 / 字段规则表 / AI理解与建议”等 MCP 自带分析结构。
5. 不替 adapter 判断需求范围、交付边界、PRD 结构或实现范围。
6. 保留页面树、页面文本、截图路径、页面图片资源、标注、评论、版本和错误信息。
7. 返回结构尽量稳定、机器可读，便于 adapter 后续做差量优先分析。

## adapter 当前需要的 MCP 方法

### 1. `lanhu_resolve_invite_link`

用于把 Lanhu invite link 转换为可继续读取的 Lanhu URL 或文档定位信息。

期望返回：

```json
{
  "status": "ok",
  "resolvedUrl": "https://...",
  "docId": "...",
  "projectId": "...",
  "teamId": "...",
  "errors": []
}
```

不需要返回分析提示词。

### 2. `lanhu_get_pages`

用于读取页面树，帮助 adapter 根据 explicit pageId 收敛分析范围。

adapter 依赖它判断：

- explicit `pageId` 是否存在
- 目标页名称、路径、层级
- 是否存在子页面
- 子页面是否属于目标页后代
- 是否需要询问用户包含子页面
- 避免误读 sibling、parent、adjacent pages、trash / legacy pages

期望返回：

```json
{
  "status": "ok",
  "docId": "...",
  "versionId": "...",
  "pages": [
    {
      "id": "page-id",
      "name": "订单详情",
      "path": "订单/订单详情",
      "level": 2,
      "parentId": "parent-page-id",
      "filename": "...",
      "children": [
        {
          "id": "child-page-id",
          "name": "退款弹窗",
          "path": "订单/订单详情/退款弹窗",
          "level": 3,
          "parentId": "page-id",
          "filename": "...",
          "children": []
        }
      ]
    }
  ],
  "errors": []
}
```

不应返回：

- 四阶段分析工作流
- TODO 指令
- 让用户选择开发视角 / 测试视角的提示
- `STAGE 1: GLOBAL TEXT SCAN`
- `二狗工作指引`
- 任何“必须如何分析/输出”的文本

### 3. `lanhu_get_ai_analyze_page_result`

这是 adapter 读取页面内容的核心方法。建议保留现有方法名以兼容用户，但增加 evidence-only 输出模式。

推荐新增参数之一：

```python
output_mode: Literal["guided", "evidence_only"] = "guided"
```

或：

```python
include_analysis_prompt: bool = True
```

adapter 期望调用方式：

```yaml
mode: full
page_names:
  - <单个页面名>
output_mode: evidence_only
```

显式 `pageId` tree mode 下，adapter 会逐页调用：每次只传一个 allowed page name，不会一次性传 parent + children。

## `evidence_only` 模式期望返回结构

`mode: full` + `output_mode: evidence_only` 时，建议返回：

```json
{
  "status": "ok",
  "docId": "...",
  "versionId": "...",
  "mode": "full",
  "outputMode": "evidence_only",
  "analysisPromptIncluded": false,
  "summary": {
    "totalRequested": 1,
    "successful": 1,
    "failed": 0,
    "fromCache": true
  },
  "pages": [
    {
      "pageId": "...",
      "pageName": "订单详情",
      "path": "订单/订单详情",
      "level": 2,
      "filename": "...",
      "text": "页面中提取出的原始文本...",
      "screenshotPath": "/absolute/or/local/path/to/screenshot.png",
      "comments": [
        {
          "id": "...",
          "author": "...",
          "content": "评论内容",
          "createdAt": "...",
          "position": {
            "x": 0,
            "y": 0
          }
        }
      ],
      "annotations": [
        {
          "content": "标注内容",
          "source": "prototype-text | comment | design-note",
          "position": {
            "x": 0,
            "y": 0
          }
        }
      ],
      "designInfo": {
        "colors": [],
        "fonts": [],
        "images": [
          {
            "name": "...",
            "path": "/local/path/to/image.png",
            "width": 120,
            "height": 80
          }
        ]
      },
      "warnings": []
    }
  ],
  "failedPages": [],
  "errors": []
}
```

如果仍需要兼容 MCP 返回 `List[Union[str, Image]]`，也应保证第一段文本是纯事实元数据，不包含分析提示词。例如：

```text
Lanhu Evidence Only Result
status: ok
outputMode: evidence_only
analysisPromptIncluded: false

Page 1: 订单详情
pageId: ...
path: 订单/订单详情

[PAGE_TEXT]
...

[SCREENSHOT_PATH]
...

[DESIGN_INFO]
...
```

## `evidence_only` 模式必须移除的内容

以下内容不应出现在 adapter 使用的 evidence-only 返回里：

- `STAGE 1: GLOBAL TEXT SCAN`
- `STAGE 2 分析模式`
- `STAGE 4 输出要求`
- `TODO-DRIVEN FOUR-STAGE WORKFLOW`
- `二狗工作指引`
- `Your Mission`
- `分析完本组页面后，必须按以下格式输出`
- `开发视角`
- `测试视角`
- `快速探索`
- `功能清单表`
- `字段规则表`
- `与全局关联`
- `遗漏/矛盾检查`
- `AI理解与建议`
- `变更类型识别`
- 任何让调用方改变身份、工作流、分析模式或输出格式的指令

## adapter 自己负责的内容

Lanhu MCP 不需要负责以下工作：

- 判断前端 / 后端角色 PRD 模板
- 判断 `.lanhu` package 目录结构
- 判断一个需求拆成几个 PRD
- 生成 `index.md`
- 生成角色 PRD markdown
- 判断 `新增` / `差量调整` / `现有上下文` / `待确认` / `全量重构` / `全量替换`
- 判断 copied old page risk
- 输出 `requirementScopeJudgment`
- 输出 `scopeConfirmationSummary`
- 判断 confirmation gate
- 生成 Superpowers spec、plan 或 wiki

这些由 adapter 的 Lanhu analyst 负责。

## 兼容策略

建议不要删除现有 guided 行为，避免破坏其他用户：

```python
output_mode="guided"        # 保持现有行为，返回证据 + 分析提示词
output_mode="evidence_only" # 新增行为，只返回事实证据
```

或者：

```python
include_analysis_prompt=True  # 保持现有行为
include_analysis_prompt=False # 新增行为，只返回事实证据
```

adapter 后续会优先调用 evidence-only 模式；如果 MCP 版本不支持该参数，adapter 可以暂时回退到当前行为，并继续在 adapter 层清洗 MCP 分析提示词。

## 验收标准

1. `lanhu_get_pages` 返回页面树时，不夹带四阶段分析或输出格式提示。
2. `lanhu_get_ai_analyze_page_result(..., output_mode="evidence_only")` 返回页面事实、截图、文本、标注、评论和资源信息。
3. evidence-only 返回中 `analysisPromptIncluded` 为 `false`。
4. evidence-only 返回中不包含 `STAGE 1`、`STAGE 2`、`STAGE 4`、`二狗工作指引`、`功能清单表`、`字段规则表`、`AI理解与建议` 等提示词。
5. 旧的 guided 模式仍可用，保证向后兼容。
6. adapter 能基于 evidence-only 返回继续完成 pageId 白名单、逐页读取、差量优先范围判断和 `.lanhu` PRD package 生成。
