语音合成服务（TTS） 负责将大模型生成的文本转换为自然流畅的语音。

<div data-tips="true" data-tips-type="warning" data-tips-is-title="true">Warning</div>


<div data-tips="true" data-tips-type="warning">若通过 <code>S2SConfig</code> 参数启用了端到端语音模型，本章节描述的 <code>TTSConfig</code> 配置将自动失效，系统的语音合成能力由端到端模型内部处理。关于端到端模型的配置，请参见<a href="https://www.volcengine.com/docs/6348/1902994">接入端到端实时语音大模型</a>。</div>


<span id="选择语音合成服务"></span>
## 支持的 TTS 服务


| 模型类型         | 支持的模型         | 特性                                                         |
| ---------------- | ------------------ | ------------------------------------------------------------ |
| 火山引擎 TTS     | 语音合成大模型     | 语音合成情感更强，支持流式和非流式输入。流式输入支持 Markdown 过滤和朗读 Latex 公式。 |
|                  | 语音合成（小模型） | 生成速度快，仅支持非流式输入，满足常规语音播报需求，适合短语或标准回复（如提醒、系统反馈）。 |
|                  | 声音复刻大模型     | 支持复刻真人音色、流式和非流式输入。                         |
| 第三方自定义 TTS | MiniMax 语音合成   | 支持多语言、混合音色和特殊发音标注。详细功能特性，参看 [MiniMax 语音生成](https://platform.minimaxi.com/document/T2A%20V2?key=66719005a427f0c8a5701643)。 |
|                  | 自定义 TTS         | 接入自定义或私有化部署的 TTS 服务，实现自定义需求。          |


<span id="f8552fdb"></span>
## 火山语音合成大模型

支持流式输入（推荐）和非流式输入两种模式。流式输入模式下支持**参数透传**和**参数直传**。

<span id="9ad5dfe5"></span>
### 流式输入流式输出

<span id="d19ba80e"></span>
#### 参数透传

此方式支持通过 JSON 字符串传入豆包语音合成大模型服务的全部配置参数，相较于直传配置更灵活、功能更全面。

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。



<Tabs>
<Tab zoneid="Ge0TTusly2" title="AI 音视频互动方案-StartVoiceChat（2025-06-01）">
<TabTitle>AI 音视频互动方案-StartVoiceChat（2025-06-01）</TabTitle>

* `VolcanoTTSParameters`：参见[VolcanoTTSParameters 说明](https://www.volcengine.com/docs/6348/1581713#a7435134)。

* `ResourceId`：指定模型版本。同时支持语音合成大模型 2.0 和 1.0 版本，推荐使用 2.0，通过参数 `ResourceId` 来指定。

* `voice_type`：需与 ResourceId（模型版本）匹配，语音合成大模型 1.0 仅支持使用 1.0 音色，大模型 2.0 仅支持使用 2.0 音色。详情可参见[音色列表](https://www.volcengine.com/docs/6561/1257544)。


```JSON
{
    "TTSConfig": {
        "Provider": "volcano_bidirection",  // 必填：固定值
        "ProviderParams": {
            // 鉴权配置
            "Credential": {
                "ResourceId": "seed-tts-2.0" // 模型版本
            },
            "VolcanoTTSParameters": "{\"req_params\":{\"speaker\":\"zh_female_vv_uranus_bigtts\",\"additions\":{\"disable_markdown_filter\":true}}}"    // 必填，【参数透传】压缩并转义后的 JSON 字符串          
        }
    }
}
```



</Tab>
<Tab zoneid="VH0ugQg1UQ" title="实时对话式 AI-StartVoiceChat（2024-12-01）">
<TabTitle>实时对话式 AI-StartVoiceChat（2024-12-01）</TabTitle>

* `VolcanoTTSParameters`：参见[VolcanoTTSParameters 说明](https://www.volcengine.com/docs/6348/1581713#a7435134)。

* `ResourceId`：指定模型版本。同时支持语音合成大模型 2.0 和 1.0 版本，推荐使用 2.0，通过参数 `ResourceId` 来指定。

* `voice_type`：需与 ResourceId（模型版本）匹配，语音合成大模型 1.0 仅支持使用 1.0 音色，大模型 2.0 仅支持使用 2.0 音色。详情可参见[音色列表](https://www.volcengine.com/docs/6561/1257544)。


```JSON
{
    "TTSConfig": {
        "Provider": "volcano_bidirection",  // 必填：固定值
        "ProviderParams": {
            // 鉴权配置
            "Credential": {
                "AppId": "94****11",         // 必填：豆包语音控制台获取的 AppID
                "Token": "OaO****ws1",       // 必填：App ID 对应的 AccessToken
                "ResourceId": "seed-tts-2.0" // 选填，资源 ID
            },
            "VolcanoTTSParameters": "{\"req_params\":{\"speaker\":\"zh_female_vv_uranus_bigtts\",\"audio_params\":{\"speech_rate\":0,\"loudness_rate\":0}}}"    // 必填，一个 JSON 字符串，参见下方说明
                   
        }
    }
}
```



</Tab>
</Tabs>


<span id="0dce015f"></span>
#### 参数直传

此方式封装了语音合成大模型的部分配置参数，接入简单，但无法使用该服务的全部功能。

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。



<Tabs>
<Tab zoneid="LgsqmsORAq" title="AI 音视频互动方案-StartVoiceChat（2025-06-01）">
<TabTitle>AI 音视频互动方案-StartVoiceChat（2025-06-01）</TabTitle>

* `ResourceId`：指定模型版本。同时支持语音合成大模型 2.0 和 1.0 版本，推荐使用 2.0，通过参数 `ResourceId` 来指定。

* `voice_type`（音色）需与 ResourceId（模型版本）匹配，即语音合成大模型 1.0 仅支持使用 1.0 音色，大模型 2.0 仅支持使用 2.0 音色。详情可参见[音色列表](https://www.volcengine.com/docs/6561/1257544)。

* `enable_latex_tn`（播报 LaTeX 公式）：使用语音合成大模型 2.0 或声音复刻大模型 2.0 时，该功能与 `SubtitleConfig.SubtitleMode:0`（对齐音频时间戳）不可同时启用。


```JSON
{
    "TTSConfig": {
        "Provider": "volcano_bidirection",   // 必填：固定值
        "ProviderParams": {
            "audio": {
                "voice_type": "zh_female_vv_uranus_bigtts", // 必填，音色
                "speech_rate": 0            // 选填：语速
            },
            "ResourceId": "seed-tts-2.0", // 模型版本，示例为 2.0 版本
            "Additions": {
                "enable_latex_tn": true,           // 选填：开启 Latex 公式播报
                "disable_markdown_filter": true,   // 选填：开启 Markdown 符号过滤（如加粗、标题符不读出）
                "enable_language_detector": false  // 选填：自动语种识别
            }
        }
    }
}
```



</Tab>
<Tab zoneid="usm4hrg13A" title="实时对话式 AI-StartVoiceChat（2024-12-01）">
<TabTitle>实时对话式 AI-StartVoiceChat（2024-12-01）</TabTitle>

* `ResourceId`：指定模型版本。同时支持语音合成大模型 2.0 和 1.0 版本，推荐使用 2.0，通过参数 `ResourceId` 来指定。

* `voice_type`（音色）需与 ResourceId（模型版本）匹配，语音合成大模型 1.0 仅支持使用 1.0 音色，大模型 2.0 仅支持使用 2.0 音色。详情可参见[音色列表](https://www.volcengine.com/docs/6561/1257544)。

* `enable_latex_tn`（播报 LaTeX 公式）：使用语音合成大模型 2.0 或声音复刻大模型 2.0 时，该功能与 `SubtitleConfig.SubtitleMode:0`（对齐音频时间戳）不可同时启用。


```JSON
{
    "TTSConfig": {
        "Provider": "volcano_bidirection",   // 必填：固定值
        "ProviderParams": {
            "app": {
                "appid": "94****11",        // 必填：豆包语音控制台获取的 AppID
                "token": "OaO****ws1"       // 必填：App ID 对应的 AccessToken
            },
            "audio": {
                "voice_type": "zh_female_vv_uranus_bigtts", // 必填，音色
                "speech_rate": 0            // 选填：语速
            },
            "ResourceId": "seed-tts-2.0", // 选填：资源 ID，区分并发版或字符版
            "Additions": {
                "enable_latex_tn": true,           // 选填：开启 Latex 公式播报
                "disable_markdown_filter": true,   // 选填：开启 Markdown 符号过滤（如加粗、标题符不读出）
                "enable_language_detector": false  // 选填：自动语种识别
            }
        }
    }
}
```



</Tab>
</Tabs>


<span id="7f20a353"></span>
### 非流式输入流式输出

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。



<Tabs>
<Tab zoneid="udsq7PAGa1" title="AI 音视频互动方案-StartVoiceChat（2025-06-01）">
<TabTitle>AI 音视频互动方案-StartVoiceChat（2025-06-01）</TabTitle>

`voice_type`：仅支持使用语音合成大模型 1.0 支持的音色，具体 `voice_type` 值参见[音色列表](https://www.volcengine.com/docs/6561/1257544?lang=zh#%E8%B1%86%E5%8C%85%E8%AF%AD%E9%9F%B3%E5%90%88%E6%88%90%E6%A8%A1%E5%9E%8B1-0-%E9%9F%B3%E8%89%B2%E5%88%97%E8%A1%A8)。

```JSON
{
  "TTSConfig": {
    "Provider": "volcano", // 必填：固定值
    "ProviderParams": {
      "audio": {
        "voice_type": "ICL_zh_female_yry_tob", // 必填：大模型音色
        "speed_ratio": 1.0, // 选填：语速
      }
    }
  }
}
```



</Tab>
<Tab zoneid="P5TJcKxcjl" title="实时对话式 AI-StartVoiceChat（2024-12-01）">
<TabTitle>实时对话式 AI-StartVoiceChat（2024-12-01）</TabTitle>

* `appid`：前往[豆包语音控制台-语音合成大模型](https://console.volcengine.com/speech/service/10007?)获取。

* `voice_type`：仅支持使用语音合成大模型 1.0 的音色，具体 `voice_type` 值参见[音色列表](https://www.volcengine.com/docs/6561/1257544?lang=zh#%E8%B1%86%E5%8C%85%E8%AF%AD%E9%9F%B3%E5%90%88%E6%88%90%E6%A8%A1%E5%9E%8B1-0-%E9%9F%B3%E8%89%B2%E5%88%97%E8%A1%A8)。


```JSON
{
  "TTSConfig": {
    "Provider": "volcano", // 必填：固定值
    "ProviderParams": {
      "app": {
        "appid": "94****11", // 必填：豆包语音控制台获取的 AppID
      },
      "audio": {
        "voice_type": "ICL_zh_female_yry_tob", // 必填：大模型音色
        "speed_ratio": 1.0, // 选填：语速
      }
    }
  }
}
```



</Tab>
</Tabs>


<span id="27ddba1f"></span>
## 火山语音合成（小模型）

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。



<Tabs>
<Tab zoneid="Jgr6gtaUk1" title="AI 音视频互动方案-StartVoiceChat（2025-06-01）">
<TabTitle>AI 音视频互动方案-StartVoiceChat（2025-06-01）</TabTitle>

`voice_type`：仅支持取值 `BV001_streaming`（通用女生）、`BV002_streaming`（通用男生）。

```JSON
{
    "TTSConfig": {
        "Provider": "volcano",             // 必填，固定值
        "ProviderParams": {
            "app": {
                "appid": "94****11"       // 必填：豆包语音控制台获取的 AppID
            },
            "audio": {
                "voice_type": "BV001_streaming", // 必填：音色 ID
                "speed_ratio": 1.0,           // 选填：语速
                "volume_ratio": 1.0,          // 选填：音量
                "pitch_ratio": 1.0            // 选填：音高
            }
        }
    }
}
```



</Tab>
<Tab zoneid="ILxBvM4Bx5" title="实时对话式 AI-StartVoiceChat（2024-12-01）">
<TabTitle>实时对话式 AI-StartVoiceChat（2024-12-01）</TabTitle>

`appid`、`voice_type`：前往[豆包语音控制台-语音合成](https://console.volcengine.com/speech/service/8?)获取。

```JSON
{
    "TTSConfig": {
        "Provider": "volcano",             // 必填，固定值
        "ProviderParams": {
            "app": {
                "appid": "94****11"       // 必填：豆包语音控制台获取的 AppID
            },
            "audio": {
                "voice_type": "BV001_streaming", // 必填：音色 ID
                "speed_ratio": 1.0,           // 选填：语速
                "volume_ratio": 1.0,          // 选填：音量
                "pitch_ratio": 1.0            // 选填：音高
            }
        }
    }
}
```



</Tab>
</Tabs>


<span id="e37c7a7f"></span>
## 火山声音复刻大模型

<span id="0507b19b"></span>
### 流式输入流式输出

<span id="d0e9560a"></span>
#### 参数透传

此方式支持通过 JSON 字符串传入豆包语音合成大模型服务的全部配置参数，相较于直传配置更灵活、功能更全面。

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。



<Tabs>
<Tab zoneid="SiaGkHBci3" title="AI 音视频互动方案-StartVoiceChat（2025-06-01）">
<TabTitle>AI 音视频互动方案-StartVoiceChat（2025-06-01）</TabTitle>

1. 使用前，先购买音色资源并复刻音色。具体操作，参见[AI 音视频互动方案](https://www.volcengine.com/docs/6348/2137637#43a79c5c)。

2. 配置 `StartVoiceChat`：

   * `ResourceId`：需与 `voice_type` 购买的音色资源版本一致。

   * `VolcanoTTSParameters`：参见[VolcanoTTSParameters 说明](https://www.volcengine.com/docs/6348/1581713#a7435134)。

   ```JSON
   {
     "TTSConfig": {
       "Provider": "volcano_bidirection", // 必填：固定值
       "ProviderParams": {
         "VolcanoTTSParameters": "{\"req_params\":{\"speaker\":\"S_N****T7k1\",\"audio_params\":{\"speech_rate\":0}}}",   //必填，透传压缩并转义后的 JSON 字符串
         "Credential": {
           "ResourceId": "seed-icl-2.0" // 必填：需与音色资源版本一致
       }
     }
   }
   ```
   


</Tab>
<Tab zoneid="TfZZc7PdZD" title="实时对话式 AI-StartVoiceChat（2024-12-01）">
<TabTitle>实时对话式 AI-StartVoiceChat（2024-12-01）</TabTitle>

1. 使用前，先复刻音色并获取 ID。具体操作，参见[实时对话式 AI](https://www.volcengine.com/docs/6348/2137637#faba5a25)。

2. 配置 `StartVoiceChat`：

* `ResourceId`：需与 `voice_type` 购买的音色资源版本一致。

* `VolcanoTTSParameters`：参见[VolcanoTTSParameters 说明](https://www.volcengine.com/docs/6348/1581713#a7435134)。


> 其中，`req_params.speaker` 为已复刻声音 ID。


```JSON
{
    "TTSConfig": {
        "Provider": "volcano_bidirection",   // 必填：固定值
        "ProviderParams": {
            "Credential": {
                "AppId": "94****11",        // 必填：豆包语音控制台获取的 AppID
                "Token": "OaO****ws1",      // 必填：App ID 对应的 AccessToken
                "ResourceId": "seed-icl-2.0" //选填：模型版本
            },
            "VolcanoTTSParameters": "{\"req_params\":{\"speaker\":\"S_N****T7k1\",\"audio_params\":{\"speech_rate\":0}}}"     //必填，透传压缩并转义后的 JSON 字符串
        }
    }
}
```



</Tab>
</Tabs>


<span id="738d9c86"></span>
#### 参数直传

此方式封装了语音合成大模型的部分配置参数，接入简单，但无法使用该服务的全部功能。

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。



<Tabs>
<Tab zoneid="wDQpy3perR" title="AI 音视频互动方案-StartVoiceChat（2025-06-01）">
<TabTitle>AI 音视频互动方案-StartVoiceChat（2025-06-01）</TabTitle>

1. 使用前，先购买音色资源并复刻音色。具体操作，参见[AI 音视频互动方案](https://www.volcengine.com/docs/6348/2137637#43a79c5c)。

2. 配置 `StartVoiceChat`：

   * `voice_type`：已复刻声音 ID。

   * `ResourceId`：需与 `voice_type` 购买的音色资源版本一致。

   ```JSON
   {
     "TTSConfig": {
       "Provider": "volcano_bidirection", // 必填：固定值
       "ProviderParams": {
         "audio": {
           "voice_type": "S_N****T7k1", // 必填：已复刻声音 ID
           "speech_rate": 0 // 选填：语速
         },
         "ResourceId": "seed-icl-2.0", //必填：需与音色资源版本一致
         "Additions": {
           "enable_latex_tn": true, // 选填：开启 Latex 公式播报
           "disable_markdown_filter": true, // 选填：开启 Markdown 符号过滤（如加粗、标题符不读出）
           "enable_language_detector": false // 选填：自动语种识别
         }
       }
     }
   }
   ```
   


</Tab>
<Tab zoneid="fiDPOqNWzL" title="实时对话式 AI-StartVoiceChat（2024-12-01）">
<TabTitle>实时对话式 AI-StartVoiceChat（2024-12-01）</TabTitle>

1. 使用前，先复刻音色并获取 ID。具体操作，参见[实时对话式 AI](https://www.volcengine.com/docs/6348/2137637#faba5a25)。

2. 配置 `StartVoiceChat`：

   ```JSON
   {
     "TTSConfig": {
       "Provider": "volcano_bidirection", // 必填：固定值
       "ProviderParams": {
         "app": {
           "appid": "94****11", // 必填：豆包语音控制台获取的 AppID
           "token": "OaO****ws1", // 必填：App ID 对应的 AccessToken
         },
         "audio": {
           "voice_type": "S_N****T7k1", // 必填：复刻音色 ID
           "speech_rate": 0 // 选填：语速
         },
         "ResourceId": "seed-icl-2.0", //选填：模型版本
         "Additions": {
           "enable_latex_tn": true, // 选填：开启 Latex 公式播报
           "disable_markdown_filter": true, // 选填：开启 Markdown 符号过滤（如加粗、标题符不读出）
           "enable_language_detector": false // 选填：自动语种识别
         }
       }
     }
   }
   ```
   


</Tab>
</Tabs>


<span id="4b5ac925"></span>
### 非流式输入流式输出

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。



<Tabs>
<Tab zoneid="C9FE7puGJZ" title="AI 音视频互动方案-StartVoiceChat（2025-06-01）">
<TabTitle>AI 音视频互动方案-StartVoiceChat（2025-06-01）</TabTitle>

1. 使用前，先购买**音色 1.0 ** 并复刻音色。具体操作，参见[AI 音视频互动方案](https://www.volcengine.com/docs/6348/2137637#43a79c5c)。

2. 配置 `StartVoiceChat`：

   `voice_type`：传入您购买的音色 1.0 的声音 ID。可[在控制台的音色卡片](https://console.volcengine.com/conversational-ai/myVoice/voiceCloning)上获取。

   ```JSON
   {
     "TTSConfig": {
       "Provider": "volcano", // 必填：固定值
       "ProviderParams": {
         "audio": {
           "voice_type": "S_U****t1", // 必填：音色 1.0 的声音 ID
           "speed_ratio": 1.0, // 选填：语速
         }
       }
     }
   }
   ```
   


</Tab>
<Tab zoneid="qWz8VskGzu" title="实时对话式 AI-StartVoiceChat（2024-12-01）">
<TabTitle>实时对话式 AI-StartVoiceChat（2024-12-01）</TabTitle>

1. 使用前，先复刻音色并获取 ID。具体操作，参见[实时对话式 AI](https://www.volcengine.com/docs/6348/2137637#faba5a25)。

2. 配置 `StartVoiceChat`：

   ```JSON
   {
     "TTSConfig": {
       "Provider": "volcano", // 必填：固定值
       "ProviderParams": {
         "app": {
           "appid": "94****11", // 必填：豆包语音控制台获取的 AppID
           "cluster": "volcano_icl" // 必填：固定值
         },
         "audio": {
           "voice_type": "S_N****T7k1", // 必填：训练好的复刻音色 ID
           "speed_ratio": 1.0 // 选填：语速
         }
       }
     }
   }
   ```
   


</Tab>
</Tabs>


<span id="minimax-语音合成"></span>
## MiniMax 语音合成

您可参看以下示例，使用 MiniMax 语音合成进行语音合成：

> 完整参数参见对应接口文档：[AI 音视频互动方案-StartVoiceChat（2025-06-01）](https://www.volcengine.com/docs/6348/1558163)、[实时对话式 AI-StartVoiceChat（2024-12-01）](https://www.volcengine.com/docs/6348/1558163)。


```JSON
{
    "TTSConfig": {
        "Provider": "minimax",                    // 必填：固定值
        "ProviderParams": {
            "Authorization": "eyJhbG****SUzI1N",  // 必填：API Key
            "Groupid": "983*****669",             // 必填：用户组 ID
            "model": "speech-01-turbo",           // 必填：模型版本
            "URL": "https://api.minimax.chat/v1/t2a_v2", // 必填：固定地址
            "stream": true,                       // 选填：是否开启流式
            "voice_setting": {
                "speed": 1.0,                     // 选填：语速
                "voice_id": "male-qn-jingying",   // 选填：主音色 ID，voice_id 和timber_weights 必须设置其中一个
                                    
                "vol": 1.0,                       // 选填：音量
                "pitch": 0                        // 选填：语调
            },
            "timber_weights": [                   // 选填：音色混合权重，voice_id 和timber_weights 必须设置其中一个
                { "voice_id": "male-qn-jingying", "weight": 70 },
                { "voice_id": "wumei_yujie", "weight": 30 }
            ]
        }
    }
}
```


<span id="自定义语音合成"></span>
## 自定义 TTS

将自定义语音合成服务接入边缘大模型网关后，即可在实时对话式 AI 方案中使用该服务进行语音合成。

具体接入方式和说明可参看 [自定义语音合成](https://www.volcengine.com/docs/6348/1798100)。

<span id="faq"></span>
## 附录

<span id="如何更换音色？"></span>
### 如何更换 TTS 配置，例如音色？

启动任务后，可调用 `UpdateVoiceChat` 接口，更换 `TTSConfig` 配置。例如更换音色（ `voice_type` ）。配置更新后不影响正在进行的回答，会在下一次提问的时候生效。

<span id="8d1df132"></span>
### TTS 服务是否支持返回口型？

当前不支持返回口型数据。因此，您无法通过配置直接获取与合成语音相对应的口型动画参数。

<span id="a7435134"></span>
### VolcanoTTSParameters 说明


* **数据格式**：必须是一个经过 JSON 压缩并转义后的字符串。

* **参数来源**：需遵循 [豆包语音：双向流式 TTS API](https://www.volcengine.com/docs/6561/1329505) 的 `Payload` 请求参数规范。

* **构造方法**

   在[双向流式 TTS API 文档](https://www.volcengine.com/docs/6561/1329505)中，选取参数构建原始 JSON 对象，并将其转为 JSON 字符串。参数需满足下述要求：

   * **必传参数**：必须包含参数 `req_params.speaker`（音色 ID）。

      * 语音合成大模型：音色需与 `Credential.ResourceId` 中配置的模型版本匹配，语音合成大模型 1.0 仅支持使用 1.0 音色，2.0 仅支持使用 2.0 音色。可使用音色，参见[音色列表](https://www.volcengine.com/docs/6561/1257544)。

      * 声音复刻大模型：`speaker` 为已复刻声音 ID。

   * **业务所需参数**：按需选择（例如 `audio_params.speech_rate`、`additions`等）。

   * **不可传入的参数**：

      * user

      * event

      * namespace

      * req_params.text

      * req_params.audio_params.format

      * req_params.audio_params.enable_timestamp

      * req_params.additions.max_length_to_filter_parenthesis

      * req_params.additions.cache_config、req_params.additions.enable_latex_tn：当使用语音合成大模型 2.0（`ResourceId` 为 `seed-tts-2.0`）时，若启用了对齐时间戳的字幕（`SubtitleMode: 0`），这两个配置不可启用。


**示例**：以设置音色（必填）并开启 Markdown 过滤（按需）为例：


1. 先构建 JSON 对象：

   ```JSON
   {
     "req_params": {
       "speaker": "zh_female_linjianvhai_moon_bigtts",
       "additions": {
         "disable_markdown_filter": true
       }
     }
   }
   ```
   
2. 然后将其转换为 JSON 字符串：`"{\"req_params\":{\"speaker\":\"zh_female_linjianvhai_moon_bigtts\",\"additions\":{\"disable_markdown_filter\":true}}}"`。