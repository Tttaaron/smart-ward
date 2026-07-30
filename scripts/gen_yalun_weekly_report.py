# -*- coding: utf-8 -*-
"""亚伦本周工作汇报 docx 生成器（2026-07-21 至 2026-07-27）"""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

FONT = "微软雅黑"
doc = Document()

style = doc.styles["Normal"]
style.font.name = FONT
style.font.size = Pt(11)
style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

for section in doc.sections:
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.9)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

def set_shading(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)

def h1(text):
    h = doc.add_heading(text, level=1)
    for r in h.runs:
        r.font.name = FONT
        r._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        r.font.size = Pt(16)

def h2(text):
    h = doc.add_heading(text, level=2)
    for r in h.runs:
        r.font.name = FONT
        r._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        r.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)
        r.font.size = Pt(13)

def p(text, bold=False, size=11, color=None, align=None):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(6)
    para.paragraph_format.line_spacing = 1.5
    if align == "center":
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(text)
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)
    return para

def bullet(text):
    para = doc.add_paragraph(style="List Bullet")
    para.paragraph_format.space_after = Pt(3)
    run = para.add_run(text)
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(11)

def table(headers, rows, widths=None):
    t = doc.add_table(rows=1+len(rows), cols=len(headers))
    t.style = "Table Grid"
    t.alignment = 1
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.name = FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_shading(cell, "1F4E79")
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.rows[r+1].cells[c]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(val))
            run.font.name = FONT
            run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
            run.font.size = Pt(10)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)

# ===== 封面 =====
for _ in range(4):
    doc.add_paragraph()
p("智慧病房云边协同系统", bold=True, size=22, color=(0x1F,0x4E,0x79), align="center")
p("亚伦本周工作汇报", bold=True, size=18, color=(0x2E,0x75,0xB6), align="center")
doc.add_paragraph()
p("汇报周期：2026-07-21 至 2026-07-27", size=12, color=(0x59,0x59,0x59), align="center")
p("汇报人：唐亚伦（P1 边缘模型选型 + 框架搭建）", size=12, color=(0x59,0x59,0x59), align="center")
doc.add_page_break()

# ===== 一、本周概览 =====
h1("一、本周概览")
p("本周（7/21-7/27）完成 4 个版本迭代（v0.1.1 ~ v0.3.0），合并 4 个 PR，将项目从初始骨架推进至 v0.3.0 稳定状态。核心成果是边缘端功能补全、模型选型文档、技术报告 6 个章节，以及项目规范化（上传规范/版本号/CHANGELOG）。")
table(
    ["指标", "数值"],
    [
        ["版本迭代", "4 个（v0.1.1 / v0.2.0 / v0.2.1 / v0.3.0）"],
        ["合并 PR", "4 个（#1 ~ #4）"],
        ["代码变更", "+4642 / -729 行"],
        ["单元测试", "从 0 项（discover 不可用）增至 30 项全绿"],
        ["技术报告章节", "完成 6 章（第3/4/5/6/7/10章）"],
        ["新增文档", "模型选型对比 + CHANGELOG + 7 份技术报告"],
    ],
    [2.5, 4.0],
)

# ===== 二、本周完成的 PR 清单 =====
h1("二、本周完成的 PR 清单")
table(
    ["PR", "版本", "标题", "变更"],
    [
        ["#1", "v0.1.1", "修复测试可发现性与契约一致性问题", "+1772/-419（19文件）"],
        ["#2", "v0.2.0", "补全边缘端功能 + 模型选型文档 + 技术报告第3/6章", "+1369/-28（14文件）"],
        ["#3", "v0.2.1", "完成技术报告第4/5/7/10章", "+1350/-0（4文件）"],
        ["#4", "v0.3.0", "移除输液监测功能，聚焦三源融合", "+151/-282（34文件）"],
    ],
    [0.5, 0.8, 3.5, 1.7],
)

# ===== 三、按任务分解的完成情况 =====
h1("三、按任务分解的完成情况")

h2("3.1 任务1：边缘识别模型选型 - 已完成")
p("产出 docs/02-边缘模型选型对比.md，完成以下对比维度：")
bullet("视觉模型对比：YOLOv8n-pose vs YOLOv10n vs YOLO11n vs MediaPipe Pose，选定 YOLOv8n-pose（唯一原生姿态+跌倒分双输出）")
bullet("推理运行时对比：ONNX Runtime vs OpenVINO vs TensorRT vs RKNN，选定开发用 OpenVINO + 部署用 RKNN")
bullet("量化方案对比：FP32/FP16/INT8/INT4，选定 INT8（6MB + <2% 精度损失）")
bullet("13 类事件支撑度对照：8 类依赖 YOLO，5 类与 YOLO 无关")
bullet("模型转换流水线：.pt -> .onnx -> .rknn 完整链路")
bullet("后处理算法：关键点几何规则 -> posture/fall_score/tremor_score")
p("注：性能目标值（FPS/精度/延迟）待硬件到货后实测填入，对比文档不基于实测数据。", size=10, color=(0x59,0x59,0x59))

h2("3.2 任务3：搭建整体技术框架 - 已完成并超额")
p("原任务只要求框架搭建，实际超额完成边缘端功能补全、云端联调、契约对齐、规范化等工作：")

p("（1）推理引擎 inference.py 增强：", bold=True)
bullet("predictions 透传字段从 4 个扩展到 8 个（+tremor_score/position_duration/pose_keypoints/bbox）")
bullet("新增 load_model/rollback 模型版本管理（支撑灰度下发闭环）")
bullet("新增 _build_evidence_refs 按风险等级填充脱敏证据指针（image/pose_keypoints）")

p("（2）融合引擎 fusion.py 补全：", bold=True)
bullet("新增规则 nurse_call 透传（P1），补全契约事件类型")
bullet("规则2 bed_leave 增加 bbox 床区多边形双源校验（双源一致 0.92 / 床垫误报 0.50 / 向后兼容 0.85）")
bullet("移除规则3 输液异常，规则编号重排（12->11）")

p("（3）模型下发闭环完整实现：", bold=True)
bullet("main.py handle_model_deploy 调用 load_model/rollback + health 上报新版本")
bullet("修复 mqtt_client model/deploy|rollback 路由 bug（原 3 段判断永不匹配 4 段主题）")

p("（4）测试体系修复与扩充：", bold=True)
bullet("修复 unittest discover 无法发现测试的问题（裸函数改为 TestCase 子类）")
bullet("修复 test_device_fault 导入错误（from src.adapters -> 顶部统一导入）")
bullet("修复 inference.py evidence_ref -> evidence_refs 契约不一致")
bullet("修复 cloud-backend mqtt_handler _on_disconnect 回调线程阻塞")
bullet("测试从 0 项（discover 不可用）增至 30 项全绿（edge 26 + training 4）")

h2("3.3 技术报告撰写 - 完成 6 章")
p("按技术报告骨架分工，亚伦负责 7 个章节，本周完成 6 章（第9章测试待后续与振鑫合写）：")
table(
    ["章节", "标题", "截止", "状态"],
    [
        ["第3章", "系统架构设计", "8/10", "✅ 已完成"],
        ["第4章", "边缘端设计与实现", "8/15", "✅ 已完成"],
        ["第5章", "云端设计与实现（与景彬合写）", "8/15", "✅ 已完成"],
        ["第6章", "通信协议与数据模型", "8/10", "✅ 已完成"],
        ["第7章", "智能功能实现", "8/15", "✅ 已完成"],
        ["第10章", "部署与运维", "8/15", "✅ 已完成"],
        ["第9章", "系统测试与验证（与振鑫合写）", "8/20", "🟡 待成文"],
    ],
    [0.8, 3.5, 0.8, 1.2],
)

h2("3.4 项目规范化建设")
bullet("建立上传规范（docs/12-上传规范.md）：commit 模板、版本号规则、分支策略、PR 流程")
bullet("建立 CHANGELOG.md：记录 v0.1.0 ~ v0.3.0 完整变更与版本规划")
bullet("推行分支 + PR 流程：master 受保护禁止直接 push，4 个 PR 全部走 Squash merge")
bullet("统一 .gitignore：docx 产物不入版本库，改由脚本生成")

# ===== 四、本周关键决策 =====
h1("四、本周关键决策")
table(
    ["决策", "理由", "影响"],
    [
        ["移除输液监测功能", "传感器选型复杂、硬件接入成本高，聚焦三源融合", "事件 14->13 类，适配器 4->3"],
        ["选择 bbox 床区多边形做离床校验", "床垫主导 + 摄像头辅助，降低误报且向后兼容", "双源一致 0.92 / 误报 0.50"],
        ["nurse_call 走边缘透传", "契约定义边缘可透传，补全 P1 人工呼叫能力", "补全契约事件类型"],
        ["模型选型不基于实测", "硬件未到货，先完成对比论证", "性能值留占位待填"],
    ],
    [2.5, 3.0, 1.5],
)

# ===== 五、当前任务完成度 =====
h1("五、当前任务完成度")
table(
    ["任务", "内容", "完成度", "状态"],
    [
        ["任务1", "边缘识别模型选型", "100%", "✅ 对比文档完成"],
        ["任务2", "配合建鸿场景具象化", "30%", "🟡 待推进"],
        ["任务3", "搭建整体技术框架", "100%", "✅ 超额完成"],
        ["技术报告", "负责 7 章完成 6 章", "85%", "🟡 第9章待做"],
        ["真实模型接入", "YOLOv8n-pose 接入", "0%", "🔴 待硬件到货"],
    ],
    [1.2, 3.0, 0.8, 1.5],
)
p("综合完成度约 90%，剩余 10% 依赖硬件到货（真实模型接入 + 实测）和与振鑫合写第9章测试。", size=10, color=(0x59,0x59,0x59))

# ===== 六、下周计划 =====
h1("六、下周计划（7/28-8/3）")
bullet("配合硬件到货：若 Orange Pi 5 到货，接入 YOLOv8n-pose .pt 在 x86 开发机验证全链路")
bullet("完成技术报告第9章测试（与振鑫合写，8/20 截止）")
bullet("配合景彬完成前端缺口（床位可视化接入、环境控制按钮、echarts 图表组件）")
bullet("配合建鸿完成场景需求具象化文档（任务2）")
bullet("若硬件未到：推进 CameraAdapter 的 cv2 读帧实现，为硬件到货做准备")

# ===== 七、风险与需要支持 =====
h1("七、风险与需要支持")
table(
    ["风险", "影响", "需要支持"],
    [
        ["硬件到货延迟", "M3 里程碑（7/30）真实模型接入无法达成", "采购加急，或明确到货时间"],
        ["训练算法滞后", "云边协同创新点无法演示", "振鑫优先 FedAvg 阶段A"],
        ["扩散模型未启动", "困难样本闭环缺失", "烽亮/先伟启动 diffusion-service"],
    ],
    [2.0, 2.5, 2.5],
)

doc.save("亚伦本周工作汇报.docx")
print("✓ 亚伦本周工作汇报.docx 生成成功")
