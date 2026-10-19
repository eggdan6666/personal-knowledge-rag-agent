# 个人知识库 RAG Agent

把你散落的课程笔记、项目文档、PDF 资料变成一个能问答的知识库。提问后系统只依据库内资料回答，并标注 `[来源N]` 引用，资料没有的会直说，不编造。

命令行程序，本地运行，不需要数据库服务。

## 1. 安装

```bash
cd knowledge-agent
pip install -r requirements.txt
```

## 2. 配置

把 `.env.example` 复制为 `.env`，填三样东西：

| 配置项 | 说明 |
|---|---|
| `LLM_BASE_URL` | 接口地址，见下方两种预设 |
| `LLM_API_KEY` | 你自己的 key |
| `LLM_MODEL` | 模型名或推理接入点 ID |
| `DATA_PATH` | 你的文档文件夹路径，Windows 反斜杠直接写，不要加引号 |
| `DB_PATH` | 向量库目录，默认 `db` |
| `TOP_K` | 每次召回几个文本块，默认 5 |

**用 DeepSeek：**

```
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

**用豆包 / 火山方舟：**

```
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-xxx 或 ep-2025xxxx-xxxxx
```

方舟的 `LLM_MODEL` 到控制台「开通管理」里看已开通的模型 ID，或直接填推理接入点 ID。换提供商只改 `.env`，代码不用动。

`.env` 含密钥，不要提交到 git、不要外传。

## 3. 使用

**第一步：导入文档**

```bash
python ingest.py
```

递归读取 `DATA_PATH` 下的 `.pdf`、`.docx`、`.txt`，解析、分块、向量化后写入向量库，逐个文件打印块数，最后打印库内总条数。

**第二步：提问**

```bash
python query.py
```

输入问题回车即可，输入 `exit` / `quit` / `退出` 结束。每次回答下面会列出引用资料和相似度。

重复运行 `ingest.py` 不会产生重复块（记录 id 含内容哈希），所以往 `DATA_PATH` 里加新文档后重跑一次即可增量入库。

## 4. 想先试跑一下

仓库里带了 `data_test/` 演示数据（变压器绕制 txt、PID 控制 docx、SQL 主键 pdf 各一份，已入库到 `db_test/`）。把 `.env` 里两行换成注释掉的演示值即可立刻提问：

```
DATA_PATH=data_test
DB_PATH=db_test
```

然后 `python query.py`，试着问「EE28 变压器绕制的同名端怎么标记」「PID 参数整定的步骤」「SQL 主键选随机 UUID 有什么问题」。

## 5. 常见问题

**首次运行卡在「加载向量模型」**
正常。第一次要下载 `BAAI/bge-small-zh-v1.5`（约 100MB），之后离线可用。国内网络可先执行 `set HF_ENDPOINT=https://hf-mirror.com` 再运行。

**提问时报「向量库是空的」**
先跑 `python ingest.py`，或检查 `DATA_PATH` 是否指对了文件夹。

**没填 key 就运行 query.py**
会给出友好提示并退出，不会报错崩溃。

**txt 导入后是乱码**
txt 必须是 UTF-8 编码。记事本「另存为」时底部编码选 UTF-8。

**扫描版 PDF（图片转的 PDF）问不到内容**
本版不做 OCR，这类 PDF 提不出文字。可用 WPS/ Acrobat 导出为文本型 PDF 或转成 txt 再导入。

**回答不带 `[来源N]` 或者说得含糊**
把 `TOP_K` 调到 8 再重跑 `query.py`；仍不理想说明相关段落没进库，可查 `ingest.py` 输出的块数是否为 0。

**支持 Excel / PPT / 网页吗**
本版只支持 `.pdf`、`.docx`、`.txt` 三种。

## 6. 电子手册数据与检索测试

项目现已新增8份电子手册，涵盖STM32F103C8、EC600M、TL431、LM2596、MP1584、ADS1115、INA219和BME280，原有3份示例资料保留。

固定检索测试包含24道库内参数或用法题，以及4道库外题。题目和参考答案不参与入库。该测试只验证文档召回及参考关键词覆盖，不代表大模型回答准确率，也未验证库外问题的拒答效果。

在本目录运行 `python evaluation/run_datasheet_eval.py` 可复现。逐题结果、限制和复现说明见 `evaluation/README.md` 与 `evaluation/reports/datasheet_retrieval_latest.md`；实际文档数和文本块数见 `evaluation/extension_result.json`。
