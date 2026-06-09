# Firebase 实时共享配置

目标：让所有人看到同一份投票选项和票数（实时同步）。

## 1) 创建 Firebase 项目
1. 打开 https://console.firebase.google.com/
2. 新建项目
3. 添加 Web App，复制配置对象

## 2) 开启 Realtime Database
1. 进入 Build -> Realtime Database
2. 创建数据库（选最近区域）
3. 先用测试规则（开发阶段）

建议测试规则（仅开发调试）：
{
  "rules": {
    ".read": true,
    ".write": true
  }
}

## 3) 填写页面配置
打开 voting.html，找到 firebaseConfig，把以下字段填上：
- apiKey
- authDomain
- databaseURL
- projectId
- storageBucket
- messagingSenderId
- appId

## 4) 发布并访问
你已启用 GitHub Pages 后，访问：
- https://yoyoyoyojim.github.io/vote/

## 5) 说明
- 现在是实时共享模式：Admin 改选项，Guest 会立即看到。
- Admin 口令仍是 jim（前端口令，仅用于界面权限，不是强安全机制）。
