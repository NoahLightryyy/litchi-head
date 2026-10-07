# 菜单中英语言选择

用户要求菜单栏提供中文和英语选项。当前工作目录/分支：项目整合 codex/integration-project-20261001。

- 侧边栏新增“语言 / Language”原生选择框；支持中文与English，默认中文，不按浏览器猜测偏好。
- LocaleProvider + 显式词典覆盖导航、页头、在线/后端状态、个股面包屑和五个分析页签。保持路由、金融数字、数据请求和已有研究记录不变。
- 语言cookie白名单，仅保存locale，Path=/、SameSite=Lax、一年；根布局服务端读取并设置html lang和标题，避免刷新中文闪回与水合不一致。浏览器拒绝保存时显示仅本页生效。
- 业务模块中的其他说明、新闻、公司名和AI内容尚未翻译，不调用AI翻译，不声称完整英文版；相关覆盖登记FW-I18N-001。
- 验证：真实浏览器中文→English、刷新、Settings往返均保持英文导航；全前端测试新增3项覆盖非法locale、菜单词典和源文本不改写。TypeScript/ESLint、Ruff通过；Pyright与生产构建结果见收尾。
- 学习卡片51新增服务端语言偏好、内容与UI翻译边界；不改后端API契约，无需新增后端冻结。
- 收尾：110项前端测试通过；TypeScript、ESLint、Ruff、Pyright全部通过；生产构建成功。浏览器验证English持久化与路由跳转，最后恢复中文。截图 /private/tmp/litchi-language-english.png。没有新增后端逻辑；未push。
