# fixGo - OpenCode Go Provider Patch + Image Block Conversion Patch

[Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code) 向けの **OpenCode Go** (OpenAI Chat Completions API 互換) プロバイダー追加パッチ **+ 画像ブロック変換パッチ** です。

このディレクトリ内のファイル群は、upstream リポジトリに OpenCode Go 対応と、Anthropic 画像ブロックの OpenAI `image_url` 変換を追加するために必要な差分（新規ファイル + 既存ファイルの変更点）をまとめたものです。

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
├── core/
│   └── anthropic/
│       └── conversion.py          → core/anthropic/ へ上書き
├── providers/
│   ├── defaults.py                → providers/ へ上書き
│   ├── registry.py                → providers/ へ上書き
│   └── open_code_go/              → providers/ へ新規コピー
│       ├── __init__.py
│       └── client.py
└── tests/
    └── providers/
        ├── test_converter.py      → tests/providers/ へ上書き
        └── test_open_code_go.py   → tests/providers/ へ新規コピー
```

### コピー例（bash）

```bash
# free-claude-code のプロジェクトルートで実行
cp -r fixGo/providers/open_code_go providers/
cp fixGo/tests/providers/test_open_code_go.py tests/providers/
cp fixGo/tests/providers/test_converter.py tests/providers/
cp fixGo/config/provider_catalog.py config/
cp fixGo/config/settings.py config/
cp fixGo/providers/defaults.py providers/
cp fixGo/providers/registry.py providers/
cp fixGo/core/anthropic/conversion.py core/anthropic/
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
| `core/anthropic/conversion.py` | **画像ブロック変換パッチ**。Anthropic `image` ブロックを OpenAI `image_url` に変換する `_anthropic_image_to_openai()` を追加。`_convert_user_message()` / `_convert_user_message_with_injection()` を修正して画像ブロックを受け入れる |
| `providers/defaults.py` | `OPENCODE_GO_DEFAULT_BASE` の re-export を追加 |
| `providers/registry.py` | `_create_open_code_go` ファクトリ関数と `PROVIDER_FACTORIES` への登録 |
| `tests/providers/test_converter.py` | **画像ブロック変換パッチ**。`test_convert_user_message_image_raises` を削除し、代わりに `test_convert_user_message_image_base64` / `test_convert_user_message_image_url` / `test_convert_user_message_text_and_image` / `test_convert_user_message_image_unsupported_source_type_raises` を追加 |

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

## 画像ブロック変換パッチ（2026-05-03）

元々このプロキシの変換器は vision（画像）に対応しておらず、`type: image` ブロックを完全に拒否していました。
画像付きリクエストを送信すると、以下のエラーが発生していました：

```
API Error: 400 {"type":"error","error":{"type":"invalid_request_error",
"message":"User message image blocks are not supported for OpenAI chat conversion;
use a vision-capable native Anthropic provider or extend the converter."}}
```

### 根本原因

`core/anthropic/conversion.py` の `_convert_user_message()` と `_convert_user_message_with_injection()` で、`type: image` ブロックが完全に拒否されていました。OpenAI Chat Completions API は `image_url` コンテンツブロックで vision をサポートしているのに、変換器が対応していませんでした。

### 修正内容

`core/anthropic/conversion.py` に `_anthropic_image_to_openai()` 関数を追加し、以下の変換を実装しました：

- `source.type == "base64"` → `data:{media_type};base64,{data}` 形式の URL
- `source.type == "url"` → そのまま URL を渡す
- テキストのみのメッセージは従来通り**文字列形式**を維持（互換性確保）
- テキスト＋画像の混在時は OpenAI vision 形式の**配列形式**で出力

`tests/providers/test_converter.py` では、画像ブロックで例外が出る旧テスト `test_convert_user_message_image_raises` を削除し、代わりに以下のテストを追加しています：

- `test_convert_user_message_image_base64` — base64 画像の変換確認
- `test_convert_user_message_image_url` — URL 画像の変換確認
- `test_convert_user_message_text_and_image` — テキスト＋画像混在の変換確認
- `test_convert_user_message_image_unsupported_source_type_raises` — 未対応 source type での例外確認

### 検証

`tests/providers/test_converter.py` 全 56 件がパス。`uv run ruff format` / `uv run ruff check` / `uv run ty check` / `uv run pytest` もすべて通過しています。

---

## 注意：upstream とのコンフリクト

**本家（Alishahryar1/free-claude-code）から `git pull` すると、`core/anthropic/conversion.py` と `tests/providers/test_converter.py` で必ずコンフリクトが発生します。**

### なぜコンフリクトするのか

- `core/anthropic/conversion.py` は upstream の**中央変換モジュール**です。本家で OpenAI chat 変換に変更が入るたびに、このファイルは修正対象になります。
- 今回のパッチでは、`_anthropic_image_to_openai()` 関数の追加と、`_convert_user_message()` / `_convert_user_message_with_injection()` の変更を行っています。

### 解決方法

`git pull` でコンフリクトが発生した場合、以下の変更を手動でマージしてください：

1. `_anthropic_image_to_openai()` 関数（`_think_tag_content()` の直後に追加）
2. `_convert_user_message()` の画像ブロック処理（`elif block_type == "image":` の部分）
3. `_convert_user_message_with_injection()` の画像ブロック処理（同上）

コンフリクト解決後は必ず `uv run pytest tests/providers/test_converter.py` を実行し、テストが通ることを確認してください。

---

## モデル階層の振り分け例

```dotenv
# OpenCode Go 設定（フォールバック）
OPENCODE_GO_API_KEY="your-api-key"
MODEL="open_code_go/kimi-k2.6"

# LM Studio 設定（haiku 用）
LM_STUDIO_BASE_URL="http://192.168.11.100:8888/v1"
MODEL_SONNET=
MODEL_HAIKU="lmstudio/sakamakismile/Huihui-Qwen3.6-27B-abliterated-NVFP4-MTP"
MODEL_OPUS="open_code_go/kimi-k2.6"  # 将来強いモデルが出たら書き換え
```

Claude Code の `/model` で haiku を選ぶと Qwen、sonnet / opus / その他は kimi-k2.6 が使われます。

---

## 検証

```bash
uv run ruff format
uv run ruff check
uv run ty check
uv run pytest
```

すべてパスしています（1175 tests passed）。
