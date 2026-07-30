const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak } = require("docx");
const B = { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" };
const BD = { top: B, bottom: B, left: B, right: B };
const CM = { top: 60, bottom: 60, left: 100, right: 100 };
const F = "Microsoft YaHei";
function cl(t, w, o={}) { return new TableCell({ borders: BD, width: { size: w, type: WidthType.DXA }, margins: CM, shading: o.h ? { fill: "1F4E79", type: ShadingType.CLEAR } : undefined, children: [new Paragraph({ spacing: { before: 30, after: 30 }, children: [new TextRun({ text: t, size: 20, font: F, bold: !!o.h, color: o.h ? "FFFFFF" : "000000" })] })] }); }
function tb(hs, rows, cw) { const tw = cw.reduce((a,b)=>a+b,0); return new Table({ width: { size: tw, type: WidthType.DXA }, columnWidths: cw, rows: [new TableRow({ children: hs.map((h,i)=>cl(h,cw[i],{h:true})) }), ...rows.map(r=>new TableRow({ children: r.map((c,i)=>cl(c,cw[i])) }))] }); }
function h1(t) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 }, children: [new TextRun({ text: t, font: F })] }); }
function h2(t) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 160 }, children: [new TextRun({ text: t, font: F })] }); }
function h3(t) { return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 }, children: [new TextRun({ text: t, font: F })] }); }
function p(t) { return new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun({ text: t, size: 22, font: F })] }); }
function bp(l, v) { return new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun({ text: l, size: 22, bold: true, font: F }), new TextRun({ text: v, size: 22, font: F })] }); }
function bl(t) { return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { before: 30, after: 30 }, children: [new TextRun({ text: t, size: 22, font: F })] }); }
function nl(t, r="n1") { return new Paragraph({ numbering: { reference: r, level: 0 }, spacing: { before: 30, after: 30 }, children: [new TextRun({ text: t, size: 22, font: F })] }); }
function sp() { return new Paragraph({ spacing: { before: 100, after: 100 }, children: [] }); }
function pb() { return new Paragraph({ children: [new PageBreak()] }); }
const ST = { default: { document: { run: { font: F, size: 22 } } }, paragraphStyles: [
  { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 36, bold: true, font: F, color: "1F4E79" }, paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0 } },
  { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: F, color: "2B579A" }, paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 1 } },
  { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, font: F, color: "404040" }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
]};
const NM = { config: [
  { reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  { reference: "n1", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  { reference: "n2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  { reference: "n3", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
]};
const PG = { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 } } };
const HD = new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "XH-202606 \u9879\u76EE\u4EFB\u52A1\u4E66", size: 16, color: "999999", font: F })] })] });
const FT = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u7B2C ", size: 18 }), new TextRun({ children: [PageNumber.CURRENT], size: 18 }), new TextRun({ text: " \u9875", size: 18 })] })] });

const doc = new Document({ styles: ST, numbering: NM, sections: [{ properties: PG, headers: { default: HD }, footers: { default: FT }, children: [
  // 封面
  new Paragraph({ spacing: { before: 2000 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u9762\u5411\u4E91\u8FB9\u534F\u540C\u573A\u666F\u7684", size: 44, bold: true, color: "1F4E79" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: "\u5206\u5E03\u5F0FAI\u611F\u77E5\u4E0E\u51B3\u7B56\u5173\u952E\u6280\u672F\u7814\u7A76", size: 44, bold: true, color: "1F4E79" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 500, after: 100 }, children: [new TextRun({ text: "\u9879 \u76EE \u4EFB \u52A1 \u4E66", size: 36, bold: true })] }),
  sp(),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u8D5B\u9898\u7F16\u53F7\uFF1AXH-202606", size: 24, color: "555555" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, children: [new TextRun({ text: "\u53D1\u699C\u5355\u4F4D\uFF1A\u5C71\u4E1C\u6D6A\u6F6E\u6570\u636E\u5E93\u6280\u672F\u6709\u9650\u516C\u53F8", size: 24, color: "555555" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, children: [new TextRun({ text: "\u5E94\u7528\u65B9\u5411\uFF1A\u667A\u6167\u533B\u7597\uFF08\u667A\u6167\u75C5\u623F\u5B89\u5168\u76D1\u62A4\uFF09", size: 24, color: "555555" })] }),
  pb(),

  // 一、项目概述
  h1("\u4E00\u3001\u9879\u76EE\u6982\u8FF0"),
  h2("1.1 \u9879\u76EE\u80CC\u666F"),
  p("\u672C\u9879\u76EE\u4EE5\u667A\u6167\u75C5\u623F\u4E3A\u5E94\u7528\u8F7D\u4F53\uFF0C\u6784\u5EFA\u201C\u5206\u5E03\u5F0F\u611F\u77E5 + \u4E91\u8FB9\u534F\u540C\u63A8\u7406 + \u5168\u5C40\u4F18\u5316\u51B3\u7B56\u201D\u6280\u672F\u4F53\u7CFB\uFF0C\u5BF9\u9F50\u8D5B\u9898 XH-202606 \u4E09\u5927\u6838\u5FC3\u80FD\u529B\u3002"),
  h2("1.2 \u6838\u5FC3\u6280\u672F\u4F53\u7CFB"),
  nl("\u8FB9\u7F18\u5B9E\u65F6\u611F\u77E5\u4E0E\u8F7B\u91CF\u5316\u63A8\u7406\uFF1AQwen2.5-1.5B-INT4 \u5728\u8FB9\u7F18\u7AEF\u5B9E\u73B0\u6BEB\u79D2\u7EA7\u611F\u77E5\u4E0E\u521D\u6B65\u51B3\u7B56", "n1"),
  nl("\u4E91\u8FB9\u534F\u540C\u63A8\u7406\u4E0E\u4EFB\u52A1\u8C03\u5EA6\uFF1A\u201C\u8FB9\u7F18\u8F7B\u91CF\u6A21\u578B + \u4E91\u7AEF\u5168\u91CF\u6A21\u578B\u201D\u4E92\u8865\u6846\u67B6\uFF0C\u52A8\u6001\u5BFB\u4F18\u8BA1\u7B97\u8DEF\u5F84", "n1"),
  nl("\u5168\u5C40\u51B3\u7B56\u4F18\u5316\u4E0E\u4E00\u81F4\u6027\u4FDD\u969C\uFF1A\u6A21\u578B\u5206\u53D1\u4E0E\u66F4\u65B0\u673A\u5236\uFF0C\u89E3\u51B3\u8FB9\u7F18\u4FA7\u201C\u5C40\u90E8\u8D2A\u5A6A\u201D\u4E0E\u201C\u5168\u5C40\u6700\u4F18\u201D\u7684\u51B2\u7A81", "n1"),
  pb(),

  // 二、技术攻关
  h1("\u4E8C\u3001\u6280\u672F\u653B\u5173\u4EFB\u52A1\u5206\u89E3"),
  h2("T1\uFF1A\u8FB9\u7F18\u8F7B\u91CF\u5316\u5927\u6A21\u578B\u90E8\u7F72"),
  bp("\u76EE\u6807\uFF1A", "\u90E8\u7F72 Qwen2.5-1.5B-GPTQ-Int4\uFF0C\u5B9E\u73B0\u6BEB\u79D2\u7EA7\u8BED\u4E49\u63A8\u7406"),
  bp("\u786C\u4EF6\uFF1A", "NVIDIA Jetson Orin Nano 8GB (40 TOPS)"),
  h3("\u5DF2\u5B8C\u6210"),
  bl("llm_engine.py - \u53CC\u6A21\u5F0F\u63A8\u7406\u5F15\u64CE\uFF08mock/real\uFF09"),
  bl("llm_advisor.py - \u4E8B\u4EF6\u8BED\u4E49\u589E\u5F3A + \u62A4\u7406\u5EFA\u8BAE + \u79BB\u7EBF\u81EA\u6CBB\u51B3\u7B56"),
  bl("task_router.py - \u4E91\u8FB9\u534F\u540C\u4EFB\u52A1\u8DEF\u7531\u5668"),
  h3("\u5F85\u5B8C\u6210"),
  bl("\u4E0B\u8F7D Qwen2.5-1.5B-Instruct GGUF Q4_K_M \u91CF\u5316\u6A21\u578B"),
  bl("Jetson Orin Nano \u5B9E\u673A\u90E8\u7F72\u9A8C\u8BC1\uFF08TTFT/\u5185\u5B58/\u541E\u5410\uFF09"),
  bl("\u75C5\u623F\u573A\u666F Prompt \u5DE5\u7A0B\u4F18\u5316"),
  bl("\u6027\u80FD\u57FA\u51C6\u6D4B\u8BD5\u62A5\u544A\uFF08TTFT<200ms, \u5185\u5B58<=1.5GB\uFF09"),
  bp("\u8D1F\u8D23\u4EBA\uFF1A", "P1 \u4E9A\u4F26"),
  sp(),

  h2("T2\uFF1A\u4E91\u8FB9\u534F\u540C\u63A8\u7406\u6846\u67B6"),
  bp("\u76EE\u6807\uFF1A", "\u201C\u8FB9\u7F18\u8F7B\u91CF\u6A21\u578B + \u4E91\u7AEF\u5168\u91CF\u6A21\u578B\u201D\u4E92\u8865\u534F\u540C\u63A8\u7406"),
  bp("\u4E91\u7AEF\u786C\u4EF6\uFF1A", "NVIDIA RTX 4090 24GB\uFF08\u8FD0\u884C Qwen2.5-14B\uFF09"),
  h3("\u5DF2\u5B8C\u6210"),
  bl("task_router.py - \u591A\u7EF4\u8DEF\u7531\u51B3\u7B56"),
  bl("mqtt_client.py - inference/request + inference/response \u4E3B\u9898"),
  h3("\u5F85\u5B8C\u6210"),
  bl("\u4E91\u7AEF\u90E8\u7F72 Qwen2.5-14B\uFF08vLLM \u63A8\u7406\u670D\u52A1\uFF09"),
  bl("\u4E91\u7AEF\u63A8\u7406\u8BF7\u6C42\u5904\u7406\u5668"),
  bl("\u7F51\u7EDC\u611F\u77E5\u52A8\u6001\u8C03\u5EA6"),
  bl("\u964D\u7EA7\u7B56\u7565\uFF08\u4E91\u7AEF\u8D85\u65F6 -> \u8FB9\u7F18\u5156\u5E95\uFF09"),
  bl("\u5BF9\u6BD4\u5B9E\u9A8C\uFF1A\u7EAF\u8FB9\u7F18 vs \u534F\u540C vs \u7EAF\u4E91\u7AEF"),
  bp("\u8D1F\u8D23\u4EBA\uFF1A", "P7 \u5F66\u6657 + P1 \u4E9A\u4F26"),
  sp(),

  h2("T3\uFF1A\u591A\u8282\u70B9\u51B3\u7B56\u4E00\u81F4\u6027"),
  bp("\u76EE\u6807\uFF1A", "\u51B2\u7A81\u6BD4\u4F8B<=5%\uFF0C\u89E3\u51B3\u6210\u529F\u7387>=90%"),
  h3("\u5F85\u5B8C\u6210"),
  bl("\u91CD\u53E0\u611F\u77E5\u533A\u57DF\u5904\u7406"),
  bl("\u591A\u8282\u70B9\u6295\u7968/\u4EF2\u88C1\u534F\u8BAE"),
  bl("\u4E91\u7AEF\u5168\u5C40\u4E00\u81F4\u6027\u6821\u9A8C"),
  bl("\u51B2\u7A81\u89E3\u51B3\u65E5\u5FD7\u4E0E\u7EDF\u8BA1"),
  bp("\u8D1F\u8D23\u4EBA\uFF1A", "P4 \u632F\u946B + P3 \u5EFA\u9E3F"),
  sp(),

  h2("T4\uFF1A\u6A21\u578B\u84B8\u998F\u4E0E\u66F4\u65B0\u95ED\u73AF"),
  bp("\u76EE\u6807\uFF1A", "14B\u6559\u5E08 -> 1.5B\u5B66\u751F \u77E5\u8BC6\u84B8\u998F\u95ED\u73AF"),
  h3("\u5F85\u5B8C\u6210"),
  bl("\u75C5\u623FNLU\u4EFB\u52A1\u6570\u636E\u96C6\u6784\u5EFA\uFF08500+\u6761\uFF09"),
  bl("Qwen2.5-14B -> 1.5B LoRA\u5FAE\u8C03 + KD loss"),
  bl("\u84B8\u998F\u540E INT4 \u91CF\u5316 + GGUF \u5BFC\u51FA"),
  bl("\u8BC4\u6D4B\uFF1A\u84B8\u998F\u540E vs \u539F\u59CB 1.5B \u4EFB\u52A1\u51C6\u786E\u7387"),
  bl("\u6A21\u578B\u66F4\u65B0\u95ED\u73AF\u6F14\u793A"),
  bp("\u8D1F\u8D23\u4EBA\uFF1A", "P4 \u632F\u946B + P5 \u5148\u4F1F"),
  sp(),

  h2("T5\uFF1A\u6027\u80FD\u57FA\u51C6\u4E0E\u5BF9\u6BD4\u5B9E\u9A8C"),
  bp("\u76EE\u6807\uFF1A", "\u4EA7\u51FA\u91CF\u5316\u8BC4\u6D4B\u62A5\u544A\uFF0840\u5206\u6700\u5927\u6743\u91CD\uFF09"),
  h3("\u5F85\u5B8C\u6210"),
  bl("\u7AEF\u5230\u7AEF\u65F6\u5EF6\u6D4B\u91CF\uFF08\u76EE\u6807<=0.2s\uFF09"),
  bl("TTFT \u57FA\u51C6\u6D4B\u8BD5\uFF08\u8FB9\u7F18 vs \u4E91\u7AEF\uFF0C\u5C55\u793A75%\u964D\u4F4E\uFF09"),
  bl("\u611F\u77E5\u7CBE\u5EA6\u8BC4\u6D4B\uFF08\u51C6\u786E\u7387/\u53EC\u56DE\u7387/F1\uFF09"),
  bl("\u65AD\u7F51\u4E1A\u52A1\u4FDD\u6301\u7387\u6D4B\u8BD5\uFF08>=90%\uFF09"),
  bl("\u53EF\u6269\u5C55\u6027\u6D4B\u8BD5\uFF083\u8282\u70B9 -> 6 -> 12\uFF09"),
  bl("\u4EA7\u51FA\u5BF9\u6BD4\u5B9E\u9A8C\u62A5\u544A"),
  bp("\u8D1F\u8D23\u4EBA\uFF1A", "P5 \u5148\u4F1F + P2 \u666F\u5F6C"),
  sp(),

  h2("T6\uFF1A\u4F5C\u54C1\u6750\u6599\u4E0E\u6F14\u793A"),
  bp("\u76EE\u6807\uFF1A", "\u5B8C\u6210\u8D5B\u4E8B\u63D0\u4EA4\u5168\u5957\u6750\u6599"),
  h3("\u5F85\u5B8C\u6210"),
  bl("\u4F5C\u54C1\u62A5\u544A\uFF08\u6280\u672F\u65B9\u6848 + \u5B9E\u9A8C\u7ED3\u679C + \u521B\u65B0\u6027\u8BF4\u660E\uFF09"),
  bl("\u8FD0\u884C\u6548\u679C\u89C6\u9891\uFF085-8\u5206\u949F\uFF09"),
  bl("\u4EE3\u7801\u6574\u7406\u4E0E\u6CE8\u91CA\u5B8C\u5584"),
  bl("PPT \u7B54\u8FA9\u6750\u6599"),
  bl("\u521B\u65B0\u70B9\u51DD\u7EC3"),
  bp("\u8D1F\u8D23\u4EBA\uFF1A", "P3 \u5EFA\u9E3F + P6 \u70FD\u4EAE + \u5168\u5458"),
  pb(),

  // 三、团队分工
  h1("\u4E09\u3001\u56E2\u961F\u5206\u5DE5"),
  sp(),
  tb(["\u7F16\u53F7", "\u89D2\u8272", "\u59D3\u540D", "\u6838\u5FC3\u4EFB\u52A1", "\u5173\u952E\u6A21\u5757"],
    [["P1", "\u8FB9\u7F18AI+\u6846\u67B6", "\u4E9A\u4F26", "T1 \u8FB9\u7F18LLM + T2 \u534F\u540C\u63A8\u7406(\u8FB9\u7F18\u4FA7)", "llm_engine, llm_advisor, task_router"],
     ["P2", "\u524D\u7AEF+\u573A\u666F", "\u666F\u5F6C", "\u524D\u7AEF\u7EC4\u4EF6 + T5 \u6027\u80FD\u770B\u677F", "cloud-frontend, ECharts"],
     ["P3", "\u7EDF\u7B79+\u65B9\u6848", "\u5EFA\u9E3F", "T3 \u4E00\u81F4\u6027(\u65B9\u6848) + T6 \u4F5C\u54C1\u62A5\u544A", "docs, \u65B9\u6848\u4E66"],
     ["P4", "\u8BAD\u7EC3+\u4E00\u81F4\u6027", "\u632F\u946B", "T3 \u4E00\u81F4\u6027(\u5B9E\u73B0) + T4 \u84B8\u998F/FedAvg", "training-coordinator"],
     ["P5", "\u6570\u636E+\u6D4B\u8BD5", "\u5148\u4F1F", "T4 \u84B8\u998F\u6570\u636E\u96C6 + T5 \u6027\u80FD\u6D4B\u8BD5", "\u6D4B\u8BD5\u811A\u672C, \u8BC4\u6D4B\u62A5\u544A"],
     ["P6", "\u89C6\u9891+\u90E8\u7F72", "\u70FD\u4EAE", "T6 \u6F14\u793A\u89C6\u9891 + \u4E91\u7AEFLLM\u90E8\u7F72", "cloud-llm-service, \u89C6\u9891"],
     ["P7", "\u4E91\u8FB9\u534F\u540C", "\u5F66\u6657", "T2 \u534F\u540C\u63A8\u7406(\u4E91\u7AEF\u4FA7) + \u94FE\u8DEF\u6253\u901A", "cloud-llm-service, MQTT"]],
    [700, 1400, 800, 3400, 3086]),
  pb(),

  // 四、里程碑
  h1("\u56DB\u3001\u91CC\u7A0B\u7891\u4E0E\u65F6\u95F4\u8282\u70B9"),
  sp(),
  tb(["\u91CC\u7A0B\u7891", "\u65E5\u671F", "\u4EA4\u4ED8\u7269", "\u9A8C\u6536\u6807\u51C6"],
    [["M1: \u9700\u6C42\u51BB\u7ED3+\u67B6\u6784", "7/15 \u2705", "\u65B9\u6848\u4E66+\u6846\u67B6\u9AA8\u67B6", "8\u670D\u52A1\u7AEF\u5230\u7AEF\u8054\u8C03\u901A\u8FC7"],
     ["M2: \u75C5\u623F\u95ED\u73AF", "7/22 \u2705", "10\u9879\u529F\u80FD+26\u6D4B\u8BD5\u5168\u7EFF", "\u4E8B\u4EF6\u878D\u5408+\u4E91\u7AEF\u5904\u7F6E\u95ED\u73AF"],
     ["M3: \u8FB9\u7F18LLM\u96C6\u6210", "8/10", "T1\u5B8C\u6210", "TTFT<200ms, \u5185\u5B58<=1.5GB"],
     ["M4: \u4E91\u8FB9\u534F\u540C\u63A8\u7406", "8/20", "T2\u5B8C\u6210", "\u534F\u540C\u94FE\u8DEF\u8DD1\u901A, \u4FDD\u6301\u7387>=90%"],
     ["M5: \u4E00\u81F4\u6027+\u84B8\u998F", "8/25", "T3+T4\u5B8C\u6210", "\u51B2\u7A81<=5%, \u84B8\u998F\u4FDD\u630180%+"],
     ["M6: \u6027\u80FD\u8BC4\u6D4B", "8/28", "T5\u5B8C\u6210", "\u5168\u90E8\u6307\u6807\u8FBE\u6807, \u5BF9\u6BD4\u62A5\u544A"],
     ["M7: \u8D5B\u4E8B\u4EA4\u4ED8", "8/31", "T6\u5B8C\u6210", "\u5168\u5957\u6750\u6599\u63D0\u4EA4"]],
    [2200, 1100, 2000, 4086]),
  sp(),

  // 五、验收指标
  h1("\u4E94\u3001\u8D5B\u9898\u6307\u6807\u5BF9\u7167\u9A8C\u6536\u8868"),
  sp(),
  tb(["\u8D5B\u9898\u786C\u6307\u6807", "\u76EE\u6807\u503C", "\u6D4B\u91CF\u65B9\u6CD5", "\u8D1F\u8D23"],
    [["\u8FB9\u4FA7\u6A21\u578B\u4FDD\u6301\u6EE1\u8840\u80FD\u529B", "80-90%", "\u75C5\u623FNLU\u4EFB\u52A1\u96C6\u8BC4\u6D4B", "T4"],
     ["TTFT\u51CF\u5C1175%", "\u8FB9\u7F18<200ms vs \u4E91\u7AEF>800ms", "llama.cpp\u8BA1\u65F6", "T1"],
     ["\u5355\u6B21\u63A8\u7406\u5185\u5B58", "<=1.5GB", "psutil/resource\u76D1\u63A7", "T1"],
     ["\u7F51\u7EDC\u6CE2\u52A8\u4E1A\u52A1\u4FDD\u6301\u7387", ">=90%", "tc netem\u6A21\u62DF+\u529F\u80FD\u6D4B\u8BD5", "T2"],
     ["\u7AEF\u5230\u7AEF\u65F6\u5EF6", "<=0.2s", "\u4E8B\u4EF6\u4EA7\u751F->\u524D\u7AEF\u5C55\u793A\u8BA1\u65F6", "T5"],
     ["\u51B3\u7B56\u51B2\u7A81\u6BD4\u4F8B", "<=5%", "\u591A\u8282\u70B9\u77DB\u76FE\u4E8B\u4EF6\u7EDF\u8BA1", "T3"],
     ["\u51B2\u7A81\u89E3\u51B3\u6210\u529F\u7387", ">=90%", "\u4EF2\u88C1\u7ED3\u679C\u6B63\u786E\u6027\u9A8C\u8BC1", "T3"]],
    [2400, 2600, 3186, 1200]),
  pb(),

  // 六、架构
  h1("\u516D\u3001\u7CFB\u7EDF\u67B6\u6784\u6982\u89C8"),
  h2("6.1 \u4E91\u8FB9\u7AEF\u4E09\u5C42\u67B6\u6784"),
  bl("\u4E91\u7AEF\u5C42\uFF1AFastAPI \u4E8B\u4EF6\u4E2D\u5FC3 + Qwen2.5-14B \u5168\u91CF\u63A8\u7406 + vLLM \u670D\u52A1"),
  bl("\u8FB9\u7F18\u5C42\uFF1A3\u4E2A\u8FB9\u7F18\u4EE3\u7406\uFF08Jetson Orin Nano\uFF09+ Qwen2.5-1.5B-INT4 + \u89C4\u5219\u878D\u5408\u5F15\u64CE"),
  bl("\u901A\u4FE1\u5C42\uFF1AMQTT (Mosquitto) QoS 1 + WebSocket \u5B9E\u65F6\u63A8\u9001"),
  bl("\u524D\u7AEF\u5C42\uFF1AVue 3 \u62A4\u58EB\u7AD9\u5DE5\u4F5C\u53F0 + ECharts \u53EF\u89C6\u5316"),
  h2("6.2 \u4E91\u8FB9\u534F\u540C\u63A8\u7406\u6D41\u7A0B"),
  nl("\u8FB9\u7F18\u7AEF\u591A\u6E90\u91C7\u96C6 -> \u89C4\u5219\u878D\u5408 -> LLM\u8BED\u4E49\u589E\u5F3A", "n2"),
  nl("TaskRouter \u591A\u7EF4\u8BC4\u4F30\uFF08\u7F6E\u4FE1\u5EA6/\u590D\u6742\u5EA6/\u7F51\u7EDC\u72B6\u6001\uFF09", "n2"),
  nl("\u9AD8\u7F6E\u4FE1\u5EA6\u4E8B\u4EF6 -> \u8FB9\u7F18\u672C\u5730\u5904\u7406\uFF08<200ms\uFF09", "n2"),
  nl("\u4F4E\u7F6E\u4FE1\u5EA6/\u9AD8\u590D\u6742\u5EA6 -> \u5378\u8F7D\u4E91\u7AEF 14B \u4E8C\u6B21\u7814\u5224", "n2"),
  nl("\u4E91\u7AEF\u7ED3\u679C\u56DE\u4F20 -> \u8FB9\u7F18\u66F4\u65B0\u51B3\u7B56 -> \u62A4\u58EB\u7AD9\u5C55\u793A", "n2"),
  h2("6.3 \u6A21\u578B\u66F4\u65B0\u95ED\u73AF"),
  nl("\u4E91\u7AEF 14B \u6559\u5E08\u6A21\u578B\u5728\u75C5\u623F\u8BED\u6599\u4E0A\u5FAE\u8C03", "n3"),
  nl("\u77E5\u8BC6\u84B8\u998F\uFF1A14B logits -> 1.5B \u5B66\u751F\u6A21\u578B", "n3"),
  nl("INT4 \u91CF\u5316 + GGUF \u5BFC\u51FA", "n3"),
  nl("MQTT \u7070\u5EA6\u4E0B\u53D1\u5230\u8FB9\u7F18\u8282\u70B9", "n3"),
  nl("\u8FB9\u7F18\u52A0\u8F7D\u65B0\u6A21\u578B -> \u4E0A\u62A5 health -> \u4E91\u7AEF\u786E\u8BA4\u95ED\u73AF", "n3"),
  pb(),

  // 七、风险
  h1("\u4E03\u3001\u98CE\u9669\u4E0E\u5E94\u5BF9"),
  sp(),
  tb(["\u98CE\u9669", "\u6982\u7387", "\u5F71\u54CD", "\u5E94\u5BF9\u63AA\u65BD"],
    [["Jetson\u786C\u4EF6\u5230\u8D27\u5EF6\u8FDF", "\u4E2D", "T1\u963B\u585E", "\u5148\u7528x86 CPU + llama.cpp\u9A8C\u8BC1"],
     ["14B\u6A21\u578B\u663E\u5B58\u4E0D\u8DB3", "\u4F4E", "T2\u963B\u585E", "\u964D\u7EA7\u4E3A7B\u6216AWQ 4bit\u91CF\u5316"],
     ["\u84B8\u998F\u6548\u679C\u4E0D\u8FBE\u6807", "\u4E2D", "\u6307\u6807\u98CE\u9669", "\u589E\u5927\u8BED\u6599\uFF0C\u8C03\u6574KD\u6E29\u5EA6"],
     ["\u65F6\u95F4\u7D27\u5F20", "\u9AD8", "\u5168\u5C40", "\u4F18\u5148T1+T2(60\u5206)\uFF0CT3+T4\u6B21\u4E4B"]],
    [2200, 800, 1200, 5186]),
  sp(),

  // 八、创新点
  h1("\u516B\u3001\u521B\u65B0\u70B9\u51DD\u7EC3"),
  nl("\u57FA\u4E8E\u591A\u7EF4\u611F\u77E5\u7684\u4E91\u8FB9\u52A8\u6001\u4EFB\u52A1\u8C03\u5EA6\u7B97\u6CD5\uFF1A\u878D\u5408\u7F6E\u4FE1\u5EA6\u3001\u4EFB\u52A1\u590D\u6742\u5EA6\u3001\u7F51\u7EDC\u72B6\u6001\u4E09\u7EF4\u5EA6\u5B9E\u65F6\u8DEF\u7531", "n1"),
  nl("\u9762\u5411\u533B\u7597\u573A\u666F\u7684\u5927\u6A21\u578B\u77E5\u8BC6\u84B8\u998F\u95ED\u73AF\uFF1A\u201C\u4E91\u7AEF\u5168\u91CF\u5FAE\u8C03 -> \u4EFB\u52A1\u7279\u5B9A\u84B8\u998F -> INT4\u91CF\u5316 -> \u7070\u5EA6\u4E0B\u53D1\u201D\u5168\u94FE\u8DEF", "n1"),
  nl("\u591A\u8FB9\u7F18\u8282\u70B9\u51B3\u7B56\u4E00\u81F4\u6027\u534F\u8BAE\uFF1A\u57FA\u4E8E\u77DB\u76FE\u4E8B\u4EF6\u5BF9\u68C0\u6D4B + \u4E91\u7AEF\u4EF2\u88C1\u7684\u8F7B\u91CF\u7EA7\u51B2\u7A81\u89E3\u51B3\u673A\u5236", "n1"),
  nl("\u8FB9\u7F18LLM\u6301\u7EED\u6D3B\u52A8\u8BED\u4E49\u6C47\u62A5\uFF1A\u4ECE\u201C\u4E8B\u4EF6\u9A71\u52A8\u201D\u5347\u7EA7\u4E3A\u201C\u6301\u7EED\u611F\u77E5+\u81EA\u7136\u8BED\u8A00\u62A4\u7406\u62A5\u544A\u201D", "n1"),
] }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("e:\\CODE\\CODE\\smart classroom\\smart-ward\\\u4EFB\u52A1\u4E66.docx", buf);
  console.log("OK: \u4EFB\u52A1\u4E66.docx (" + (buf.length/1024).toFixed(1) + " KB)");
});
