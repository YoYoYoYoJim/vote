# Outlook 邮件投票使用说明

## 目标
让任何收件人都能在 Outlook 邮件里点击按钮，打开投票网页使用。

## 重要限制
Outlook 邮件正文不支持运行复杂 JavaScript 交互页面。

可行方案是：
1. 把投票网页发布到公网 URL。
2. 在邮件中放一个按钮链接到该 URL。

## 已生成文件
- `voting.html`：投票网页
- `outlook_voting_email_template.html`：可用于 Outlook 的邮件 HTML 模板

## 快速发布（推荐：Netlify Drop）
1. 打开 https://app.netlify.com/drop
2. 把 `voting.html` 拖进去
3. 得到一个公网链接，例如：
   - `https://abc123.netlify.app`
4. 将邮件模板中的以下两处链接替换为：
   - `https://abc123.netlify.app`

## Outlook 使用方式
1. 打开 `outlook_voting_email_template.html`
2. 全选并复制页面内容
3. 在 Outlook 新邮件中粘贴
4. 发送给收件人

## 注意
当前投票页是前端单页版本，不含后端数据库：
- 页面刷新后，投票状态会重置。
- 如果需要多人共享同一份实时票数，需要后端服务（如 Firebase / Supabase / 自建 API）。
