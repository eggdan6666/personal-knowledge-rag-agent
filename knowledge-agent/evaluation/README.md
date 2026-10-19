# 电子手册检索测试

本目录保存电子手册扩充脚本、固定测试题和真实运行报告。题目与参考答案放在文档导入目录之外，不参与向量入库。

## 数据范围

从用户已有的 `E:\HD-Agent·分层记忆RAG的电子Dstasheet智能问答\corpus\data\raw_pdf` 中选取8份PDF：

- STM32F103C8
- EC600M系列硬件设计手册
- TL431
- LM2596
- MP1584
- ADS1115
- INA219
- BME280

这些文件覆盖MCU、通信、电源、ADC、电流监测与环境传感器，复制到项目原有文档目录的 `datasheets/` 子目录。原始PDF和原有3份示例资料保留。

`datasheet_manifest.json` 保存每份文件的来源、复制位置、SHA256和PDF页数；`extension_result.json` 保存实际入库统计和索引备份位置。已有索引会在首次写入前备份；重复运行扩充脚本时跳过已有记录。

## 题目与指标

`datasheet_cases.json` 包含24道库内参数或用法题，以及4道库外题。题集由AI辅助编写，参考要点在入库前与指定PDF原文校验。它是小规模固定基线，多数问题显式包含型号，不能代表开放场景表现。

测试直接调用应用现有的 `query.retrieve()`，保留原来的BGE向量模型、分块方式和Top-K=5；没有更换检索算法来追求分数。

- 文档来源命中@1：首条召回来自参考文件。
- 文档来源命中@5：前5条召回包含参考文件。
- 参考要点字符串覆盖@5：正确来源的召回文本匹配预设关键词，仅用于辅助诊断，不是答案正确率。
- 库外题仅保存召回观察。没有调用大模型，因此不报告问答准确率或拒答成功率。

参考页码为PDF物理页码，从1开始。JSON报告保留逐题参考答案、实际召回文本、来源、相似度和耗时；失败记录也保留。

## 运行

使用已安装项目依赖的Python，在 `knowledge-agent` 目录执行：

```powershell
# 复制选定PDF、备份并扩充索引、执行固定测试
python evaluation/extend_datasheets.py

# 对当前索引重新执行同一题集
python evaluation/run_datasheet_eval.py
```

脚本读取现有 `.env` 的数据目录与索引目录，不输出API密钥，不修改原始PDF；仅使用已缓存的本地BGE模型，不调用外部大模型API。

报告位置：`evaluation/reports/datasheet_retrieval_latest.md` 与同名JSON文件。简历中的数量与检索指标应以实际报告为准。
