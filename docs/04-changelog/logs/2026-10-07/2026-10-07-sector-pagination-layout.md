# 分页板块表格取消内部纵向滚动

用户要求：行业研究的板块表已有分页，不需要每页内部滑块。
独立分支 codex/sector-map-generation 修改共享 SectorRanking：移除 max-h-[32rem]，
overflow-auto 改为 overflow-x-auto。分页改为滚动外层页面至表头，搜索只重置页码。
首页与行业研究复用该组件，来源不区分；窄屏横向滚动保留以防列裁切。

验证：3项现有分页测试通过；TypeScript、组件ESLint、全仓Ruff与src Pyright通过。
浏览器3046/industries使用真实1000条历史板块数据，第一页10行、容器高度650等于内容高度650、
maxHeight=none；点击下一页后显示11–20行和第2/100页。未增加镜像实现的样式单测。
旧内部scrollTo引用已替换；frontend README与学习卡片51同步，无新增技术债务。

仅改独立工作树，尚未合并到用户3000主预览；本轮未修改或重启主线程服务。
