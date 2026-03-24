# RSS Detector

自动读取学术 RSS，按主题画像打分，并生成三档 RSS：

- high.xml
- mid.xml
- low.xml

项目会读取 [RSS.py](/E:/Codex_Repository/RSS_Detecter/RSS.py) 中配置的 RSS 源，结合 `zotero_profile.json` 里的关键词和短语权重，对新论文标题与摘要打分。

输出文件：

- `docs/high.xml`
- `docs/mid.xml`
- `docs/low.xml`
- `rss_matches.json`
- `seen_items.json`

## 部署到 GitHub

1. 在 GitHub 创建一个新仓库。
2. 把当前项目推送到该仓库。
3. 打开仓库的 `Settings` -> `Actions` -> `General`。
4. 确认 `Workflow permissions` 选择的是 `Read and write permissions`。
5. 进入 `Actions` 页面，手动运行一次 `RSS Scan`，确认首轮结果能生成。

## 定时检索

仓库内置了 GitHub Actions 工作流 [rss.yml](/E:/Codex_Repository/RSS_Detecter/.github/workflows/rss.yml)：

- 支持手动触发
- 每天自动运行一次
- 运行后自动更新仓库中的 RSS 结果文件

当前定时表达式是 UTC `01:00`，对应北京时间每天 `09:00`。

## 结果使用

推送到 GitHub 后，你可以直接通过仓库原始文件链接订阅：

- `docs/high.xml`
- `docs/mid.xml`
- `docs/low.xml`
