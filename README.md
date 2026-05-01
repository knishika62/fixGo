# fixGo - OpenCode Go Provider Patch

[Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code) 向けの **OpenCode Go** (OpenAI Chat Completions API 互換) プロバイダー追加パッチです。

このディレクトリ内のファイル群は、upstream リポジトリに OpenCode Go 対応を追加するために必要な差分（新規ファイル + 既存ファイルの変更点）をまとめたものです。

**対応 upstream コミット**: `7d80cc3426fb92e68df152ad42405d0de0cdb798`

Moonshot AI をバックエンドとする OpenCode Go を経由して、Claude Code から `kimi-k2.6` 等のモデルを利用できるようにします。

---

## 適用方法

[Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code) をダウンロード・展開した後、`fixGo/` 内のファイルを以下の通り対応するフォルダへコピーしてください。

```
fixGo/
├── .env.example                   → プロジェクトルートへ上書き
├── .python-version                → プロジェクトルートへ上書き
├── config/
│   ├── provider_catalog.py        → config/ へ上書き
│   └── settings.py                → config/ へ上書き
├── providers/
│   ├── defaults.py                → providers/ へ上書き
│   ├── registry.py                → providers/ へ上書き
│   └── open_code_go/              → providers/ へ新規コピー
│       ├── __init__.py
│       └── client.py
└── tests/
    └── providers/
        └── test_open_code_go.py   → tests/providers/ へ新規コピー
```

### コピー例（bash）

```bash
# free-claude-code のプロジェクトルートで実行
cp -r fixGo/providers/open_code_go providers/
cp fixGo/tests/providers/test_open_code_go.py tests/providers/
cp fixGo/config/provider_catalog.py config/
cp fixGo/config/settings.py config/
cp fixGo/providers/defaults.py providers/
cp fixGo/providers/registry.py providers/
cp fixGo/.env.example .
cp fixGo/.python-version .
```

---

## 変更ファイル一覧

### 新規ファイル

| ファイル | 説明 |
|---------|------|
| `providers/open_code_go/__init__.py` | `OpenCodeGoProvider` をエクスポート |
| `providers/open_code_go/client.py` | **本体**。`OpenAIChatTransport` を継承し、Moonshot AI 固有の `reasoning_content` ワークアラウンドを実装 |
| `tests/providers/test_open_code_go.py` | プロバイダーのユニットテスト |

### 既存ファイルの変更

| ファイル | 変更内容 |
|---------|---------|
| `.env.example` | `OPENCODE_GO_API_KEY=""` とコメントを追加 |
| `.python-version` | `3.14.0` → `3.14`（ローカル環境にないパッチバージョンを避ける） |
| `config/provider_catalog.py` | `OPENCODE_GO_DEFAULT_BASE` 定数と `open_code_go` の `ProviderDescriptor` を追加 |
| `config/settings.py` | `open_code_go_api_key` フィールドを追加 |
| `providers/defaults.py` | `OPENCODE_GO_DEFAULT_BASE` の re-export を追加 |
| `providers/registry.py` | `_create_open_code_go` ファクトリ関数と `PROVIDER_FACTORIES` への登録 |

---

## 使用例

```dotenv
# .env
OPENCODE_GO_API_KEY="your-api-key"
MODEL="open_code_go/kimi-k2.6"
```

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8082
```

```bash
ANTHROPIC_AUTH_TOKEN="freecc" ANTHROPIC_BASE_URL="http://localhost:8082" claude
```

---

## ワークアラウンドの詳細

Moonshot AI（OpenCode Go の裏側）は `thinking` 有効時に、**`tool_calls` を持つ assistant message に `reasoning_content` フィールドがないと 400 を返します**。

対処として、`client.py` では以下を行っています：

1. `ReasoningReplayMode.THINK_TAGS` を使用し、thinking 内容を `<think>` タグとして通常の text に埋め込む
2. `tool_calls` を持つ assistant message に `reasoning_content=" "`（空白1文字）を強制的に注入

これにより標準外の `reasoning_content` キーを回避しつつ、Moonshot AI の厳格なバリデーションを通過します。

---

## モデル階層の振り分け例

```dotenv
# OpenCode Go 設定（フォールバック）
OPENCODE_GO_API_KEY="your-api-key"
MODEL="open_code_go/kimi-k2.6"

# LM Studio 設定（sonnet / haiku 用）
LM_STUDIO_BASE_URL="http://192.168.11.100:8888/v1"
MODEL_SONNET="lmstudio/sakamakismile/Huihui-Qwen3.6-27B-abliterated-NVFP4-MTP"
MODEL_HAIKU="lmstudio/sakamakismile/Huihui-Qwen3.6-27B-abliterated-NVFP4-MTP"
MODEL_OPUS="open_code_go/kimi-k2.6"  # 将来強いモデルが出たら書き換え
```

Claude Code の `/model` で sonnet を選ぶと Qwen、それ以外は kimi-k2.6 が使われます。

---

## 検証

```bash
uv run ruff format
uv run ruff check
uv run ty check
uv run pytest
```

すべてパスしています（1175 tests passed）。
