# 返回页面恢复辩论任务

用户反馈688012触发后切换选项返回，历史分析中但按钮触发空态。
只读确认deb_fe86a6cecd2d运行，另deb_46b26d9d9797此前已失败。
根因selectDebateView只恢复completed，未恢复running/queued；组件卸载后本地状态丢失。
修复同股活动ID恢复、结果读取、终态失败展示、运行/历史读取期间隐藏初始提示。
显式历史选择优先，身份隔离保留；服务端确认运行期间不以120秒前端次数兜底停止读取。

重要验收副作用：首次全库check的TestClient lifespan访问正式session store，
将当前运行记录标为重启中断。未实际重启正式服务。已明确向用户披露。
修复tests/test_backend/conftest.py autouse临时store隔离；21项生命周期/辩论测试通过，
134项前端测试通过，隔离后再次scripts/check.py通过5/5，git diff --check通过。
浏览器最初成功恢复分析中与等待态；随后实际记录失败，切换技术/流派后显示服务端
失败，不再显示初始触发提示。未伪造恢复状态，未再次提交模型；原请求结果仍未取得。
截图/private/tmp/litchi-debate-resume-fixed.png。
同步README、知识卡59、DEBATE-RESUME-001/TEST-SESSION-001及路由。
引用检索确认只一个selectDebateView消费者，不新增旧实现；无API契约变化。未提交推送。
