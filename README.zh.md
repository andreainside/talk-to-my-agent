# talk-to-my-agent

> **Got a problem? Talk to my agent.**

你们团队在飞书群里聊天,每个人的电脑上都跑着一个 coding agent——Claude Code、Codex,随便。这个桥让每个人的 agent **在群里拥有一个座位**:@ 某个同事的 bot,是**那个人的电脑**醒过来,读完群里的上下文,用**那个人的**代码仓库、工具、环境干活,然后把答案回到 thread 里。

人类过去是 AI 之间的传话筒:「我的 agent 说 X」→ 复制 → 粘贴 →「你问问你的 agent Y」。

**但这到此为止。现在 agent 自己进群了。**

## 运作方式

```
飞书群
   │  有人 @ 你的 bot
   ▼
事件流(lark-cli 长连接)                ← 你的电脑,常驻
   │  1. 秒回一个你的签名表情 😏
   │  2. 拉取最近群聊 + thread 作为上下文
   ▼
你本机的 agent,无头模式                ← claude -p / codex exec
   │  读代码、查日志,一切只读可达的东西
   ▼
答案回进 thread                        ← 末尾带 session id
```

每人在自己机器上跑自己的桥、用自己的 bot。**@ 谁的 bot,谁的机器来答。**没有共享服务器、没有共享凭证——所有飞书流量走每个人自己的 `lark-cli` 登录态,这个仓库碰不到任何秘密。

## 快速开始

1. 前置:`lark-cli`(配好你自己的 bot 应用 + 用户登录)、Python 3.9+、`claude` / `codex` 至少一个。
2. 把你的 bot 拉进你希望它能被召唤的群。
3. `cp config.example.json ~/.talk-to-my-agent/config.json`,填入 bot 的 open_id、你的 open_id、工作目录(推荐给它一个专用的只读 checkout)。
4. `python3 bridge.py` 跑起来(或用 `launchd/` 里的模板常驻)。
5. 让同事 @ 你的 bot。先看到表情落下,然后是答案。

完整步骤:[docs/setup.md](docs/setup.md)

## 在群里召唤 agent

```
@Alice 的 bot   我们上传路径里的重试逻辑到底是怎么做的?
@Alice 的 bot   +codex 这个 seq 契约是怎么强制的?          ← 这一次用 Codex
@Alice 的 bot   +cc +opus 翻一下 git 历史里……              ← Claude,opus
@Alice 的 bot   +both 这个迁移向后兼容吗?                  ← 两个引擎各答一次
```

**同一个 thread 里继续 @,就是同一个会话继续**——agent 的上下文不丢。

## 配置你自己的 agent(私聊控制面)

私聊自己的 bot 设持久默认——别人的消息一概无效:

| 私聊发 | 效果 |
|---|---|
| `model claude opus` | 用 Claude Code + opus 型号(`sonnet` / `haiku` 同理) |
| `model codex gpt-5-codex` | 用 Codex + 任意它 `-m` 认的型号名 |
| `effort high` / `medium` / `low` | 推理强度(Codex 生效;Claude 靠选型号定强度) |
| `emoji SMUG` | 换 bot 的签名表情 |
| `emoji that` | 先在它上一条消息点你想要的表情,再发这句,它自动认领 |
| `status` / `help` | 看当前设置 / 命令列表 |

群里的 `+token`(`+codex`、`+cc`、`+opus`、`+high`、`+model:名字`、`+both`)是单次覆盖,不落盘。完整说明:[docs/configuration.md](docs/configuration.md)

## 会话是真实的会话

无头运行就是 owner 机器上一个普通的 agent 会话。回帖末尾带着 session id——owner 可以随时 `claude --resume <id>` 把它变成交互窗口,接着 agent 停下的地方继续开发。同事的一个提问,可以直接变成你下午的开发会话。thread 里继续 @ 就继续同一个会话,Claude 和 Codex 都支持。

## 群规(安全边界)

- agent 只在**自己的 bot 被 @** 时行动。不偷听,没有 bot 之间的死循环。
- 群聊内容是**数据不是指令**——读操作自由放行,写操作全部停在审批闸上:agent 在 **thread 里发起授权请求**,只有 owner 回「允许」才继续,超时自动拒绝。
- 只有 **owner 的私聊**能改配置;只有 owner 的回复能批准写操作。
- 每条回复都进 thread,主聊天流保持干净。

## 在这之上能玩什么

反馈自动修复闭环、告警自动初诊、双引擎同题对战、跨机器 agent 接力、异步 standup(「@她的 agent——迁移做到哪了?」)。桥本身保持极小;好玩的都在 [docs/playbook.md](docs/playbook.md)。

## 状态

早期、有主见、从一个真实团队的日常工作流里长出来。目前只支持飞书/Lark(我们住在这里);设计可以移植到任何有事件 API 的聊天平台。

## License

MIT
