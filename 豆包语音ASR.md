<span id="d4caf38f"></span>

# 豆包语音ASR

**语音识别模块 - 基于LAS ASR服务的录音转写解决方案**
<span id="3bd3abc9"></span>

## **使用限制**

* 暂只支持单个语音文件传入
* 语音识别为异步接口，您需要先创建语音识别任务，再通过语音识别任务的 ID 去查询语音识别结果
* 目前支持的音频格式为 raw, wav, mp3, ogg。

<span id="c602b991"></span>
## 核心功能

* 接入火山引擎LAS ASR接口
* 支持自动断句、数字规整、说话人或通道分离（可选）
* 并发处理多个音频文件，提供结构化 JSON 与可读文本两种输出
* 适合转写最长2小时的录音文件，支持标点补全、智能断句、说话人分离等高级功能。

<span id="d7ee2c78"></span>
# 计费说明
* 计费标准
  
   | | | \
   | <div style="width:200px">细分项</div> | <div style="width:720px">计费标准说明</div>             |
   | ------------------------------------- | ------------------------------------------------------- |
   |                                       |                                                         |
   | 计费项                                | 基于**输入音频的时长**统计用量进行计费。                |
   |                                       |                                                         |
   | 计费类型                              | 按量计费，单位：`元/小时`，按实际的计费用量每小时出账。 |
   |                                       |                                                         |
   | 单价                                  | 与选择使用的模型有关。                                  |

* 计费详情
   计费公式：`总费用 =  单价 * 用量 `
   
   | | | \
   | <div style="width:200px">细分场景</div> | <div style="width:720px">单价</div> |
   | --------------------------------------- | ----------------------------------- |
   |                                         |                                     |
   | *  模型：Seed-ASR 2.0                   | 0.8 元/小时                         |
   |                                         |                                     |
   | *  模型：Seed-ASR 1.0                   | 2.3 元/小时                         |




<span id="a7b4e748"></span>
# 注意与前提

| | | \
| 细分项          | 注意与前提                                                   |
| --------------- | ------------------------------------------------------------ |
|                 |                                                              |
| 开通 LAS        | * 如果您是一个全新的火山引擎用户，此前未开通过 LAS 产品，您可先开通 LAS，不使用 LAS 的计费功能仅开通 LAS 产品不会产生费用。开通操作请参见[准备工作](/docs/6492/1264537)。 |
|                 | * 开通完成后可查看算子介绍文档，了解算子能力、上手引导等，详情可参见：[LAS 智能数据处理算子](/docs/6492/1798368)。 |
|                 |                                                              |
| 费用            | 调用算子前，您需先了解使用算子时的模型调用费用，详情请参见[大模型调用计费](https://www.volcengine.com/docs/6492/1544808)。 |
|                 |                                                              |
| 鉴权（API Key） | 调用算子前，您需要先生成算子调用的API Key，并建议将API Key配置为环境变量，便于更安全地调用算子，详情请参见[获取 API Key 并配置](/docs/6492/2191994)。 |
|                 |                                                              |
| BaseURL         | 调用算子前，您需要先根据您当前使用的LAS服务所在地域，了解算子调用的BaseURL，用于配置算子调用路径参数取值。 |
|                 | 详情请参见[获取 Base URL](/docs/6492/2191993)，下文中的调用示例仅作为参考，实际调用时需替换为您对应地域的路径取值。 |



<span id="2bb7bb0a"></span>
# 在线体验
LAS 为您提供了“在线体验”的能力，并为您提供了一定的免费体验额度，您无需任何配置，即可在在线体验 LAS 算子的数据处理效果。
:::warning
当前算子在线体验可免费解析 5 分钟的音频文件，超出部分会依据算子的计费项进行计费，各算子的计费项及计费逻辑请参见[大模型调用计费](/docs/6492/1544808)。
:::

<div style="display: flex;">
<div style="flex-shrink: 0;width: calc((100% - 16px) * 0.5);">

<div style="text-align: center">在线体验入口</div>


---


登录并进入 [LAS  控制台](https://console.volcengine.com/las/region:las+cn-beijing/next/home)[LAS 控制台](https://console.byteplus.com/las/region:las+ap-southeast-1/next/home?) 后，查找到当前算子卡片，鼠标悬浮于算子卡片上，单击“在线体验”按钮。
![Image](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/3a8eeb9e08524b808b64ef51b265a310~tplv-goo7wpa0wc-image.image =1574x)



</div>
<div style="flex-shrink: 0;width: calc((100% - 16px) * 0.5);margin-left: 16px;">

<div style="text-align: center">在线体验操作演示</div>


---


<BytedReactXgplayer config={{ url: 'https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/fcab99e75bbc4d1fb5492ef76c39fbcd~tplv-goo7wpa0wc-image.image', poster: 'https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/fcab99e75bbc4d1fb5492ef76c39fbcd~tplv-goo7wpa0wc-video-poster.jpeg' }} ></BytedReactXgplayer>

* LAS 为您提供了多个示例音频文件，您也可以删除示例文件，手动上传。
* 在线体验时，可灵活设置算子的处理参数。


</div>
</div>

<span id="0a37462e"></span>
# Rest API 调用
<span id="d4896613"></span>
## Submit
<span id="1791b648"></span>
### 接口说明
提交 ASR 识别任务。
<span id="659e5d64"></span>
### 请求参数

```mixin-react
const properties = ({defaultExpandAllRows: true,
  "columns": [
    { "title": "参数", "dataIndex": "column_0", "width": 300 },
    { "title": "类型", "dataIndex": "column_1", "width": 150 },
    { "title": "必填", "dataIndex": "column_2", "width": 100 },
    { "title": "示例值", "dataIndex": "column_3", "width": 150 },
    { "title": "说明", "dataIndex": "column_4" }
  ],
  "data": [
    {
      "key": 0,
      "children": [],
      "column_0": "operator_id",
      "column_1": "string",
      "column_2": "是",
      "column_3": "las_asr",
      "column_4": "算子Id"
    },
    {
      "key": 1,
      "children": [],
      "column_0": "operator_version",
      "column_1": "string",
      "column_2": "是",
      "column_3": "v2",
      "column_4": "算子版本"
    },
    {
      "key": 2,
      "children": [
        {
          "key": 3,
          "children": [
             {
                "key": 4,
                "children": [],
                "column_0": "uid",
                "column_1": "string",
                "column_2": "否",
                "column_3": "",
                "column_4": "用户标识"
             }
          ],
          "column_0": "user",
          "column_1": "UserConfig",
          "column_2": "否",
          "column_3": "",
          "column_4": "用户相关配置"
        },
        {
          "key": 5,
          "children": [
            {
              "key": 6,
              "children": [],
              "column_0": "url",
              "column_1": "string",
              "column_2": "是",
              "column_3": "",
              "column_4": "音频链接"
            },
            {
              "key": 7,
              "children": [],
              "column_0": "language",
              "column_1": "string",
              "column_2": "否",
              "column_3": "en-US",
              "column_4": <div>当该键为空时，该模型支持中英文、上海话、闽南语，四川、陕西、粤语识别。当将其设置为下方特定键时，它可以识别指定语言。<ul><li>英语：en-US</li><li>日语：ja-JP</li><li>印尼语：id-ID</li><li>西班牙语：es-MX</li><li>葡萄牙语：pt-BR</li><li>德语：de-DE</li><li>法语：fr-FR</li><li>韩语：ko-KR</li><li>菲律宾语：fil-PH</li><li>马来语：ms-MY</li><li>泰语：th-TH</li><li>阿拉伯语：ar-SA</li></ul></div>
            },
            {
              "key": 8,
              "children": [],
              "column_0": "format",
              "column_1": "string",
              "column_2": "是",
              "column_3": "mp3",
              "column_4": "音频容器格式，目前支持 raw/wav/mp3/ogg 格式"
            },
            {
              "key": 9,
              "children": [],
              "column_0": "codec",
              "column_1": "string",
              "column_2": "否",
              "column_3": "raw",
              "column_4": "音频编码格式，目前支持 raw / opus，默认为 raw(pcm)"
            },
            {
              "key": 10,
              "children": [],
              "column_0": "rate",
              "column_1": "integer",
              "column_2": "否",
              "column_3": "16000",
              "column_4": "音频采样率，默认为16000"
            },
            {
              "key": 11,
              "children": [],
              "column_0": "bits",
              "column_1": "integer",
              "column_2": "否",
              "column_3": "16",
              "column_4": "音频采样点位数，默认为16，暂只支持16bits"
            },
            {
              "key": 12,
              "children": [],
              "column_0": "channel",
              "column_1": "integer",
              "column_2": "否",
              "column_3": "1",
              "column_4": "音频声道数，1(mono) / 2(stereo)，默认为1。"
            }
          ],
          "column_0": "audio",
          "column_1": "Audio",
          "column_2": "是",
          "column_3": "",
          "column_4": "音频相关配置"
        },
        {
          "key": 13,
          "children": [],
          "column_0": "resource",
          "column_1": "string",
          "column_2": "否",
          "column_3": "bigasr",
          "column_4": "可选值为 bigasr 与 seedasr，其中默认值为bigasr。"
        },
        {
          "key": 14,
          "children": [
            {
              "key": 15,
              "children": [],
              "column_0": "model_name",
              "column_1": "string",
              "column_2": "是",
              "column_3": "bigmodel",
              "column_4": "模型名称，目前只有bigmodel"
            },
            {
              "key": 16,
              "children": [],
              "column_0": "model_version",
              "column_1": "string",
              "column_2": "是",
              "column_3": "bigmodel",
              "column_4": <div>当 resource 指定为 bigasr 时，传model_version = 400 使用400模型效果，不传时为默认310模型效果。400模型性能略有提升，且ITN有较大优化。<br/>当 resource 指定为 seedasr 时，请勿传该参数。</div>
            },
            {
              "key": 17,
              "children": [],
              "column_0": "enable_itn",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "true",
              "column_4": <div>默认为true。<br/>文本规范化 (ITN) 是自动语音识别 (ASR) 后处理管道的一部分。 ITN 的任务是将 ASR 模型的原始语音输出转换为书面形式，以提高文本的可读性。<br/>例如，“一九七零年”-》“1970年”和“一百二十三美元”-》“$123”。</div>
            },
            {
              "key": 18,
              "children": [],
              "column_0": "enable_punc",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": "默认为false。"
            },
            {
              "key": 19,
              "children": [],
              "column_0": "enable_ddc",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": "默认为false。语义顺滑是一种技术，旨在提高自动语音识别（ASR）结果的文本可读性和流畅性。这项技术通过删除或修改ASR结果中的不流畅部分，如停顿词、语气词、语义重复词等，使得文本更加易于阅读和理解。"
            },
            {
              "key": 20,
              "children": [],
              "column_0": "enable_speaker_info",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>默认为 false，开启后可返回说话人的信息，10人以内，效果较好。<br/>（如果音频存在音量、远近等明显变化，无法保证区分效果）</div>
            },
            {
              "key": 21,
              "children": [],
              "column_0": "enable_channel_split",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>默认为false。<br/>如果设为 True，则会在返回结果中使用channel_id标记，1为左声道，2为右声道。默认 False。</div>
            },
            {
              "key": 22,
              "children": [],
              "column_0": "show_utterances",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": "输出语音停顿、分句、分词信息"
            },
            {
              "key": 23,
              "children": [],
              "column_0": "show_speech_rate",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>分句信息携带语速。<br/>如果设为 true，则会在分句additions信息中使用speech_rate标记，单位为 token/s。默认 false</div>
            },
            {
              "key": 24,
              "children": [],
              "column_0": "show_volume",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>默认 false<br/>如果设为 true，则会在分句additions信息中使用volume标记，单位为 分贝。</div>
            },
            {
              "key": 25,
              "children": [],
              "column_0": "enable_lid",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>启用语种识别。<br/>目前支持语种：普通话、英语、上海话、闽南语，四川话、陕西话、粤语</div>
            },
            {
              "key": 26,
              "children": [],
              "column_0": "enable_emotion_detection",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>默认 false。<br/>如果设为 true，则会在分句additions信息中使用emotion标记, 返回对应的情绪标签。<br/>支持的情绪标签包括：<ul><li>angry：表示情绪为生气</li><li>happy：表示情绪为开心</li><li>neutral：表示情绪为平静或中性</li><li>sad：表示情绪为悲伤</li><li>surprise：表示情绪为惊讶</li></ul></div>
            },
            {
              "key": 27,
              "children": [],
              "column_0": "enable_gender_detection",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>默认 false。<br/>如果设为 true，则会在分句additions信息中使用gender标记, 返回对应的性别标签（male/female）。</div>
            },
            {
              "key": 28,
              "children": [],
              "column_0": "vad_segment",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>默认为false，默认是语义分句。<br/>打开双声道识别时，通常需要使用vad分句，可同时打开此参数</div>
            },
            {
              "key": 29,
              "children": [],
              "column_0": "end_window_size",
              "column_1": "integer",
              "column_2": "否",
              "column_3": "800",
              "column_4": <div>范围300 - 5000ms，建议设置800ms或者1000ms，比较敏感的场景可以配置500ms或者更小。（如果配置的过小，则会导致分句过碎，配置过大会导致不容易将说话内容分开。建议依照自身场景按需配置）<br/>配置该值，不使用语义分句，根据静音时长来分句。</div>
            },
            {
              "key": 30,
              "children": [],
              "column_0": "sensitive_words_filter",
              "column_1": "string",
              "column_2": "否",
              "column_3": "",
              "column_4": "敏感词过滤功能,支持开启或关闭,支持自定义敏感词。该参数可实现：不处理(默认,即展示原文)、过滤、替换为*。 示例： system_reserved_filter //是否使用系统敏感词，会替换成*(默认系统敏感词主要包含一些限制级词汇） filter_with_empty // 想要替换成空的敏感词 filter_with_signed // 想要替换成 * 的敏感词"
            },
            {
              "key": 31,
              "children": [],
              "column_0": "enable_poi_fc",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": <div>对于语音识别困难的词语，能调用专业的地图领域推荐词服务辅助识别。<br/>其中loc_info字段可选，传入该字段结果相对更精准，city_name单位为地级市。</div>
            },
            {
              "key": 32,
              "children": [],
              "column_0": "enable_music_fc",
              "column_1": "boolean",
              "column_2": "否",
              "column_3": "false",
              "column_4": "对于语音识别困难的词语，能调用专业的音领域推荐词服务辅助识别。"
            },
            {
              "key": 33,
              "children": [
                {
                  "key": 34,
                  "children": [],
                  "column_0": "context",
                  "column_1": "string",
                  "column_2": "否",
                  "column_3": "",
                  "column_4": <div>热词直传，支持5000个热词 context:&#123;"hotwords":[&#123;"word":"热词1号"&#125;, &#123;"word":"热词2号"&#125;]&#125; 上下文，限制800 tokens及20轮（含）内，超出会按照时间顺序从新到旧截断，优先保留更新的对话 context_data字段按照从新到旧的顺序排列，以下是反序列化后的例子，传入需要序列化为jsonstring（转义引号）上下文:可以加入对话历史、聊天所在bot信息、个性化信息、业务场景信息等,如:<ul><li>a.对话历史:把最近几轮的对话历史传进来</li><li>b.聊天所在bot信息:如 我在和林黛玉聊天, 我在使用A助手和手机对话</li><li>c.个性化信息: 我当前在北京市海淀区, 我有四川口音, 我喜欢音乐</li><li>d.业务场景信息: 当前是中国平安的营销人员针对外部客户采访的录音,可能涉及...</li></ul></div>
                }
              ],
              "column_0": "corpus",
              "column_1": "Corpus",
              "column_2": "否",
              "column_3": "",
              "column_4": "语料/干预词等"
            },
            {
              "key": 35,
              "children": [],
              "column_0": "callback",
              "column_1": "string",
              "column_2": "否",
              "column_3": "",
              "column_4": "callback 地址，请传入公网可访问的回调地址"
            },
            {
              "key": 36,
              "children": [],
              "column_0": "callback_data",
              "column_1": "string",
              "column_2": "否",
              "column_3": "",
              "column_4": "callback data"
            }
          ],
          "column_0": "request",
          "column_1": "RequestConfig",
          "column_2": "是",
          "column_3": "",
          "column_4": "请求相关配置"
        }
      ],
      "column_0": "data",
      "column_1": "SpeechRecognition",
      "column_2": "是",
      "column_3": "",
      "column_4": "请求数据"
    }
  ]
}); 
return <Table border={{ cell: true, wrapper: true }} pagination={false} {...properties} />;
```

<span id="3a5f71d7"></span>
### 返回数据

```mixin-react
const properties = ({
defaultExpandAllRows: true,
  "columns": [
    { "title": "参数", "dataIndex": "column_0", "width": 300 },
    { "title": "类型", "dataIndex": "column_1", "width": 150 },
    { "title": "示例值", "dataIndex": "column_2", "width": 150 },
    { "title": "说明", "dataIndex": "column_3" }
  ],
  "data": [
    {
      "key": 0,
      "children": [
        {
          "key": 1,
          "children": [],
          "column_0": "task_id",
          "column_1": "string",
          "column_2": "",
          "column_3": "异步模式下的任务id。"
        },
        {
          "key": 2,
          "children": [],
          "column_0": "task_status",
          "column_1": "string",
          "column_2": "",
          "column_3": "异步模式下的任务状态。"
        },
        {
          "key": 3,
          "children": [],
          "column_0": "business_code",
          "column_1": "string",
          "column_2": "",
          "column_3": "业务码"
        },
        {
          "key": 4,
          "children": [],
          "column_0": "error_msg",
          "column_1": "string",
          "column_2": "",
          "column_3": "如有异常，会返回详细的异常信息。"
        },
        {
          "key": 5,
          "children": [],
          "column_0": "request_id",
          "column_1": "string",
          "column_2": "",
          "column_3": "请求requestid"
        }
      ],
      "column_0": "metadata",
      "column_1": "Metadata",
      "column_2": "",
      "column_3": "请求元信息"
    }
  ]
}); 
return <Table border={{ cell: true, wrapper: true }} pagination={false} {...properties} />;
```

<span id="4343cb78"></span>
### 示例
<span id="67139228"></span>
#### 请求示例
```Bash
curl --location "https://operator.las.cn-beijing.volces.com/api/v1/submit" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer $LAS_API_KEY" \
--data '
{
    "operator_id": "las_asr",
    "operator_version": "v2",
    "data": {
        "audio": {
            "url": "https://las-ai-cn-beijing-baseline.tos-cn-beijing.volces.com/operator_cards_serving/public/baseline/las_asr/badaling.wav",
            "format": "mp3"
        },
        "request": {
            "model_name": "bigmodel"
        }
    }
}'
```

<span id="dc788feb"></span>
#### 返回示例
```JSON
{
    "metadata": {
        "task_id": "xxxxx123ef24ea40546c-las-asr",
        "task_status": "ACCEPTED",
        "business_code": "0",
        "error_msg": "",
        "request_id": "494022a8a0fc3eadb758cf8b0e8b20ef"
    }
}
```

<span id="cefaa140"></span>
## Poll
<span id="eac2568a"></span>
### 接口说明
查询 ASR 识别任务状态。
<span id="da5a8413"></span>
### 请求参数

| | | | | | \
| 参数             | 类型   | 必填 | 示例值  | 说明       |
| ---------------- | ------ | ---- | ------- | ---------- |
|                  |        |      |         |            |
| operator_id      | \      |      |         |            |
|                  | string | \    |         |            |
|                  |        | 是   | las_asr | 算子Id     |
|                  |        |      |         |            |
| operator_version | \      |      |         |            |
|                  | string | \    |         |            |
|                  |        | 是   | v2      | 算子版本   |
|                  |        |      |         |            |
| task_id          | \      |      |         |            |
|                  | string | \    |         |            |
|                  |        | 是   |         | 异步任务Id |

<span id="f1a81b72"></span>
### 返回数据

```mixin-react
const properties = ({
defaultExpandAllRows: true,
  "columns": [
    { "title": "参数", "dataIndex": "column_0", "width": 300 },
    { "title": "类型", "dataIndex": "column_1", "width": 150 },
    { "title": "示例值", "dataIndex": "column_2", "width": 150 },
    { "title": "说明", "dataIndex": "column_3" }
  ],
  "data": [
    {
      "key": 0,
      "children": [
        {
          "key": 1,
          "children": [],
          "column_0": "task_id",
          "column_1": "string",
          "column_2": "",
          "column_3": "异步模式下的任务id。"
        },
        {
          "key": 2,
          "children": [],
          "column_0": "task_status",
          "column_1": "string",
          "column_2": "",
          "column_3": "异步模式下的任务状态。"
        },
        {
          "key": 3,
          "children": [],
          "column_0": "business_code",
          "column_1": "string",
          "column_2": "",
          "column_3": "业务码"
        },
        {
          "key": 4,
          "children": [],
          "column_0": "error_msg",
          "column_1": "string",
          "column_2": "",
          "column_3": "如有异常，会返回详细的异常信息。"
        },
        {
          "key": 5,
          "children": [],
          "column_0": "request_id",
          "column_1": "string",
          "column_2": "",
          "column_3": "请求requestid"
        }
      ],
      "column_0": "metadata",
      "column_1": "Metadata",
      "column_2": "",
      "column_3": "请求的元信息，异步任务的id在其中的task_id字段下。"
    },
    {
      "key": 6,
      "children": [
        {
          "key": 7,
          "children": [
            {
              "key": 8,
              "children": [],
              "column_0": "duration",
              "column_1": "integer",
              "column_2": "",
              "column_3": "音频时长，单位秒"
            }
          ],
          "column_0": "audio_info",
          "column_1": "AudioInfo",
          "column_2": "",
          "column_3": "音频信息"
        },
        {
          "key": 9,
          "children": [
            {
              "key": 10,
              "children": [],
              "column_0": "text",
              "column_1": "string",
              "column_2": "",
              "column_3": "识别出的文本内容"
            },
            {
              "key": 11,
              "children": [
                 {
                    "key": 12,
                    "children": [],
                    "column_0": "text",
                    "column_1": "string",
                    "column_2": "",
                    "column_3": "该部分文本内容"
                 },
                 {
                    "key": 13,
                    "children": [],
                    "column_0": "start_time",
                    "column_1": "integer",
                    "column_2": "",
                    "column_3": "起始时间"
                 },
                 {
                    "key": 14,
                    "children": [],
                    "column_0": "end_time",
                    "column_1": "integer",
                    "column_2": "",
                    "column_3": "结束时间"
                 },
                 {
                    "key": 15,
                    "children": [],
                    "column_0": "confidence",
                    "column_1": "integer",
                    "column_2": "",
                    "column_3": "置信度"
                 },
                 {
                    "key": 16,
                    "children": [
                       {
                          "key": 17,
                          "children": [],
                          "column_0": "text",
                          "column_1": "string",
                          "column_2": "",
                          "column_3": "单词文本"
                       },
                       {
                          "key": 18,
                          "children": [],
                          "column_0": "start_time",
                          "column_1": "integer",
                          "column_2": "",
                          "column_3": "单词起始时间"
                       },
                       {
                          "key": 19,
                          "children": [],
                          "column_0": "end_time",
                          "column_1": "integer",
                          "column_2": "",
                          "column_3": "单词结束时间"
                       },
                       {
                          "key": 20,
                          "children": [],
                          "column_0": "blank_duration",
                          "column_1": "integer",
                          "column_2": "",
                          "column_3": "空白时长"
                       },
                       {
                          "key": 21,
                          "children": [],
                          "column_0": "confidence",
                          "column_1": "integer",
                          "column_2": "",
                          "column_3": "置信度"
                       }
                    ],
                    "column_0": "words",
                    "column_1": "list of Word",
                    "column_2": "",
                    "column_3": "单词相关信息"
                 },
                 {
                    "key": 22,
                    "children": [
                        {
                            "key": 23,
                            "children": [],
                            "column_0": "duration",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "音频时长"
                        },
                        {
                            "key": 24,
                            "children": [],
                            "column_0": "lid_lang",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "语种"
                        },
                        {
                            "key": 25,
                            "children": [],
                            "column_0": "channel_id",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "声道编号"
                        },
                        {
                            "key": 26,
                            "children": [],
                            "column_0": "speaker",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "说话人"
                        },
                        {
                            "key": 27,
                            "children": [],
                            "column_0": "volume",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "音量"
                        },
                        {
                            "key": 28,
                            "children": [],
                            "column_0": "speech_rate",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "说话频率"
                        },
                        {
                            "key": 29,
                            "children": [],
                            "column_0": "gender_score",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "性别得分"
                        },
                        {
                            "key": 30,
                            "children": [],
                            "column_0": "gender",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "性别"
                        },
                        {
                            "key": 31,
                            "children": [],
                            "column_0": "emotion_score",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "情感类型得分"
                        },
                        {
                            "key": 32,
                            "children": [],
                            "column_0": "emotion",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "情感类型"
                        },
                        {
                            "key": 33,
                            "children": [],
                            "column_0": "emotion_degree_score",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "情感强度得分"
                        },
                        {
                            "key": 34,
                            "children": [],
                            "column_0": "emotion_degree",
                            "column_1": "string",
                            "column_2": "",
                            "column_3": "情感强度"
                        }
                    ],
                    "column_0": "additions",
                    "column_1": "Additions",
                    "column_2": "",
                    "column_3": "额外信息，如说话人等"
                 }
              ],
              "column_0": "utterances",
              "column_1": "list of Utterance",
              "column_2": "",
              "column_3": "语音停顿、分句、分词信息"
            },
            {
              "key": 35,
              "children": [],
              "column_0": "additions",
              "column_1": "RequestAdditions",
              "column_2": "",
              "column_3": "额外信息"
            }
          ],
          "column_0": "result",
          "column_1": "AudioResult",
          "column_2": "",
          "column_3": "音频识别结果"
        }
      ],
      "column_0": "data",
      "column_1": "AudioResponse",
      "column_2": "",
      "column_3": "返回的音频识别结果。"
    }
  ]
}); 
return <Table border={{ cell: true, wrapper: true }} pagination={false} {...properties} />;
```

<span id="b72f1645"></span>
### 示例
<span id="23ed65e1"></span>
#### 请求示例
```Bash
curl --location "https://operator.las.cn-beijing.volces.com/api/v1/poll" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer $LAS_API_KEY" \
--data '
{
    "operator_id": "las_asr",
    "operator_version": "v2",
    "task_id": "xxxxx123ef24ea40546c-las-asr"
}'
```

<span id="5a5d51db"></span>
#### 返回示例
```JSON
{
    "metadata": {
        "task_id": "xxxxx123ef24ea40546c-las-asr",
        "task_status": "COMPLETED",
        "business_code": "0",
        "error_msg": "",
        "request_id": "d204c21f5c7c8f8cfeb85d211b9c20ac"
    },
    "data": {
        "audio_info": {
            "duration": 3575
        },
        "result": {
            "additions": {
                "duration": "3575"
            },
            "text": "参观达*长城。",
            "utterances": [
                {
                    "additions": {
                        "channel_id": "1"
                    },
                    "end_time": 2320,
                    "start_time": 640,
                    "text": "参观达*长城。",
                    "words": [
                        {
                            "confidence": 0,
                            "end_time": 920,
                            "start_time": 640,
                            "text": "参"
                        },
                        {
                            "confidence": 0,
                            "end_time": 1120,
                            "start_time": 920,
                            "text": "观"
                        },
                        {
                            "confidence": 0,
                            "end_time": 1480,
                            "start_time": 1440,
                            "text": "达"
                        },
                        {
                            "confidence": 0,
                            "end_time": 1720,
                            "start_time": 1680,
                            "text": "*"
                        },
                        {
                            "confidence": 0,
                            "end_time": 2080,
                            "start_time": 1880,
                            "text": "长"
                        },
                        {
                            "confidence": 0,
                            "end_time": 2320,
                            "start_time": 2080,
                            "text": "城"
                        }
                    ]
                }
            ]
        }
    }
}
```

<span id="a0a98276"></span>
## 错误码

| | | | | \
| HttpCode | 错误码                | 错误信息                                | 说明           |
| -------- | --------------------- | --------------------------------------- | -------------- |
|          |                       |                                         |                |
| 400      | Parameter.Invalid     | The parameter is invalid.               | 参数不合法     |
|          |                       |                                         |                |
| 401      | Authorization.Missing | Missing Authorization.                  | 缺少鉴权       |
|          |                       |                                         |                |
| 401      | ApiKey.Invalid        | The api key is invalid.                 | API不合法      |
|          |                       |                                         |                |
| 429      | Server.Busy           | Server is Busy, please try again later. | 服务端繁忙限流 |
|          |                       |                                         |                |
| 500      | Server.InternalError  | 根据具体异常而定                        | 业务异常       |

<span id="00cc255f"></span>
# **Daft 调用**
<span id="c0c7b1a2"></span>
## 算子参数
<span id="6e75de2f"></span>
### 输入

| | | \
| 输入列名    | 说明                                                         |
| ----------- | ------------------------------------------------------------ |
|             |                                                              |
| audio_urls  | 存放音频路径的列                                             |
|             |                                                              |
| audio_metas | 存放音频的元数据，Dict形式，支持language，codec，rate，bits，channel，format，corpus等参数 |

<span id="c1ed7577"></span>
### 输出

<span id="ed4ccde4"></span>
### 参数
如参数没有默认值，则为必填参数

| | | | | \
| 参数名称             | 类型        | 默认值  | 描述                                                         |
| -------------------- | ----------- | ------- | ------------------------------------------------------------ |
|                      |             |         |                                                              |
| api_key              | str         |         | LAS服务 API Key。                                            |
|                      |             |         |                                                              |
| endpoint             | str or None |         | LAS服务 API Endpoint。                                       |
|                      |             |         |                                                              |
| version              | str         | v1      | LAS服务 API Version，默认值: "v1"。                          |
|                      |             |         |                                                              |
| operator_id          | str         | las_asr | LAS ASR服务ID，默认值: "las_asr"。                           |
|                      |             |         |                                                              |
| resource             | str         | bigasr  | 进行ASR的资源类型，默认值: "bigasr"。可选值: "bigasr"，"seedasr"。 |
|                      |             |         |                                                              |
| operator_version     | str         | v1      | LAS ASR服务版本，默认值: "v1"。                              |
|                      |             |         |                                                              |
| num_coroutines       | int         | 20      | 单个实例并发处理音频的最大数量，默认值: 20。                 |
|                      |             |         |                                                              |
| max_retries          | int         | 3       | 单次API请求最大重试次数，默认值：3。                         |
|                      |             |         |                                                              |
| enable_idempotent    | bool        | False   | 用于判断是否重试处理数据，为True时，每次都会重新处理，默认值：False。 |
|                      |             |         |                                                              |
| enable_punc          | bool        | False   | 文本标点，将原始语音输出转换为带标点的形式，以提高文本的可读性，默认值：False。 |
|                      |             |         |                                                              |
| enable_ddc           | bool        | False   | 语义顺滑，旨在提高自动语音识别（ASR）结果的文本可读性和流畅性。这项技术通过删除或修改ASR结果中的不流畅部分，如停顿词、语气词、语义重复词等，使得文本更加易于阅读和理解，默认值：False。 |
|                      |             |         |                                                              |
| enable_speaker_info  | bool        | False   | 语音角色信息，开启后可返回说话人的信息，10人以内，效果较好，默认值：False。 |
|                      |             |         |                                                              |
| enable_itn           | bool        | True    | 文本规范化，将原始语音输出转换为书面形式，以提高文本的可读性，默认值：True。 |
|                      |             |         |                                                              |
| enable_channel_split | bool        | False   | 语音分轨，开启后会在返回结果中使用channel_id标记，1为左声道，2为右声道，默认值：False。 |
|                      |             |         |                                                              |
| enable_lid           | bool        | False   | 语言识别，目前支持语种：中英文、上海话、闽南语，四川、陕西、粤语，开启后会在additions信息中使用lid_lang标记, 返回对应的语种标签，默认值：False。 |
|                      |             |         |                                                              |
| show_speech_rate     | bool        | False   | 语速信息，开启后会在分句additions信息中使用speech_rate标记，单位为 token/s，默认值：False。 |
|                      |             |         |                                                              |
| show_volume          | bool        | False   | 音量信息，开启后可在分句additions信息中使用volume标记，单位为 分贝，默认值：False。 |

<span id="fbc21b66"></span>
## 调用示例
下面的代码展示了如何使用 daft 运行算子将语音转换为文字。
```Python
from __future__ import annotations

import logging
import os

import daft
from daft import col
from daft.las.functions.audio.audio_asr_las import LasAsrPoller, LasAsrSubmitter
from daft.las.functions.udf import las_udf

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S.%s".format(),
    )
    logging.getLogger("tracing.span").setLevel(logging.WARNING)
    logging.getLogger("daft_io.stats").setLevel(logging.WARNING)
    logging.getLogger("DaftStatisticsManager").setLevel(logging.WARNING)
    logging.getLogger("DaftFlotillaScheduler").setLevel(logging.WARNING)
    logging.getLogger("DaftFlotillaDispatcher").setLevel(logging.WARNING)

configure_logging()

if __name__ == "__main__":
    # 需配置环境变量 LAS_API_KEY ： LAS_API_KEY 通过在 LAS 服务页面上创建获取
    las_api_key = os.getenv("LAS_API_KEY")
    endpoint = os.getenv("LAS_SERVICE_ENDPOINT", "https://operator.las.cn-beijing.volces.com")
    TOS_INPUT_DIR_URL = os.getenv("TOS_INPUT_DIR_URL", "las-cn-beijing-public-online.tos-cn-beijing.volces.com")
    samples = {"audio_path": [os.path.join(f"https://{TOS_INPUT_DIR_URL}", "public/shared_audio_dataset/参观八达岭长城。.wav")]}

    df = daft.from_pydict(samples)
    df = df.with_column(
        "task_id",
        las_udf(
            LasAsrSubmitter,
            construct_args={
                "api_key": las_api_key,
                "max_retries": 10,
                "endpoint": endpoint,
            },
            num_cpus=1,
            concurrency=1,
            batch_size=2,
        )(col("audio_path")),
    )

    df = df.with_column(
        "asr_result",
        las_udf(
            LasAsrPoller,
            construct_args={
                "api_key": las_api_key,
                "endpoint": endpoint,
            },
            num_cpus=1,
            concurrency=1,
            batch_size=2,
        )(col("audio_path"), col("task_id")),
    ).exclude("task_id")

    df = df.with_columns(
        {
            "asr_result_raw": col("asr_result")["asr_result_raw"],
            "asr_result_text": col("asr_result")["asr_result_text"],
            "failed_reason": col("asr_result")["failed_reason"],
        }
    ).exclude("asr_result")

    df.show()
    # ╭────────────────────────────────┬────────────────────────────────┬──────────────────┬───────────────╮
    # │ audio_path                     ┆ asr_result_raw                 ┆ asr_result_text  ┆ failed_reason │
    # │ ---                            ┆ ---                            ┆ ---              ┆ ---           │
    # │ String                         ┆ String                         ┆ String           ┆ String        │
    # ╞════════════════════════════════╪════════════════════════════════╪══════════════════╪═══════════════╡
    # │ https://las-cn-beijing-public… ┆ {"additions": {"duration": "3… ┆ 参观八达岭长城。    ┆ None          │
    # ╰────────────────────────────────┴────────────────────────────────┴──────────────────┴───────────────╯
```