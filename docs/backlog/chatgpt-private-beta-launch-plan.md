# Fastest Viable Launch: ChatGPT Private Beta on AWS Lambda

## Summary

Ship a **ChatGPT-first private beta**, not a public store listing, using a **single AWS Lambda container image** that exposes a **remote MCP server** and runs `kaivra` directly. Keep the first release intentionally narrow:

- ChatGPT only
- Private beta via direct connect, not public directory submission
- No end-user auth or billing in v1
- `mp4` and `png` output only
- Silent renders by default, with optional attachment of caller-supplied audio and timing sidecars
- No built-in TTS or voice providers in v1
- Minimal AWS: `Lambda + Function URL + S3 + ECR + CloudWatch`, all via Terraform

This is the quickest path because the current render path is already fast enough for synchronous handling. Two real examples were benchmarked locally and completed in about **7.6s** and **8.3s**, so a Lambda-based synchronous render is a reasonable MVP.

## Key Changes

### 1. Backend architecture

Build one new service layer in the existing repo that wraps `kaivra` as a remote MCP server for ChatGPT.

- Use one **Lambda container image** with:
  - Python app server for MCP
  - `kaivra`
  - `ffmpeg`
  - Cairo/system font deps
- Expose it with a **Lambda Function URL** for the private beta.
- Store artifacts in **S3** and return **presigned URLs**.
- Set S3 lifecycle cleanup to **7 days**.
- Use **CloudWatch logs and alarms** only; no DB, Redis, queue, or OAuth in v1.

Lambda defaults for v1:

- timeout: **120 seconds**
- memory: **4096 MB**
- ephemeral storage: **4096 MB**
- reserved concurrency: **2**
- region: **one region only**
- image source: **ECR**
- IaC: **Terraform only**

### 2. Product surface and MCP tools

Expose exactly **two tools** in v1.

#### `validate_animation`

Purpose: let ChatGPT repair DSL before spending render time.

Input:

- `dsl_json: string`

Output:

- `valid: boolean`
- `summary: string`
- `errors: string[]`
- `warnings: string[]`
- `audit_findings: string[]`
- `normalized_dsl_json: string | null`

Behavior:

- Parse with the existing DSL parser.
- Run the existing audit pass.
- Return structured findings.
- Never render.

#### `render_animation`

Purpose: produce a final artifact.

Input:

- `dsl_json: string`
- `format: "mp4" | "png"`
- `audio_url: string | null`
- `audio_timings_json: string | null`

Output:

- `status: "ok" | "error"`
- `artifact_url: string | null`
- `preview_image_url: string | null`
- `warnings: string[]`
- `duration_seconds: number | null`
- `expires_at: string | null`
- `error: string | null`

Behavior:

- Re-validate before render.
- Reject if validation or audit returns blocking errors.
- For `png`, render first frame only and reject audio-related inputs.
- For `mp4` without `audio_url`, use the current silent render path.
- For `mp4` with `audio_url` and without `audio_timings_json`, render with authored timings and mux the supplied audio.
- For `mp4` with both `audio_url` and `audio_timings_json`:
  - parse the supplied timing sidecar
  - retime with the existing audio-timing path
  - render video
  - mux the supplied audio
  - upload final artifact to S3
- Never synthesize speech or derive timing data from narration text.

### 3. Hard product limits

These limits are part of v1 and should be enforced server-side.

- max DSL payload: **64 KB**
- max scenes: **12**
- max authored duration before optional audio retime: **90 seconds**
- max output resolution: **1280x720**
- fps: **24**
- artifact retention: **7 days**

If the request exceeds limits, return a structured tool error and do not render.

### 4. ChatGPT app packaging

Use ChatGPT as the generation layer and the service as the execution layer.

- Build a **tool-only app** first. Do not add a custom iframe/UI component in v1.
- Use **direct connect/private beta** first. Do not submit to the public store yet.
- The ChatGPT app instructions should tell the model to:
  - translate the user’s request into the DSL
  - stay within semantic layouts only
  - keep scenes short and compact
  - call `validate_animation` first
  - repair once if validation fails
  - call `render_animation` only after the DSL is valid
  - default to silent output unless the user explicitly supplies external audio to attach
  - pass through caller-supplied audio timing metadata when available
  - never promise built-in voice generation
- Bundle a short DSL guide plus **2-3 small examples** from the existing repo into the app instructions/resources.

This keeps the backend simple and cheap: ChatGPT does prompt-to-DSL, and the service only validates and renders.

### 5. Cost and abuse control

Because this is a private beta and v1 has no speech-synthesis cost, keep abuse protection coarse.

- no end-user auth
- no per-user quotas
- no billing
- no OAuth in v1
- rely on:
  - private beta distribution only
  - reserved concurrency cap
  - hard request caps
  - CloudWatch alarms on invocation count, duration, throttles, and errors

Do **not** implement monthly per-user quotas in v1. That is not worth the complexity before public launch.

### 6. Explicitly out of v1

Do not include these in the first release plan:

- public ChatGPT store submission
- Claude marketplace packaging
- speech synthesis
- ElevenLabs integration
- user accounts or entitlements
- DynamoDB quota tracking
- async queue/job orchestration
- custom web preview UI
- multiple voice providers
- custom domain

## Test Plan

### Automated

- existing `kaivra` validate/render/audit checks still pass
- tool-level tests for:
  - valid silent `mp4` render
  - valid `png` render
  - valid `mp4` render with supplied audio only
  - valid `mp4` render with supplied audio plus explicit timing sidecar
  - malformed JSON
  - schema-valid but audit-failing DSL
  - malformed timing sidecar
  - missing or invalid supplied audio URL
  - over-limit scene count
  - over-limit duration
  - S3 upload + presigned URL generation
  - Lambda handler returns structured errors instead of stack traces

### Manual acceptance

- Connect the app in ChatGPT and ask for a short animation like bubble sort.
- ChatGPT produces valid DSL, renders, and returns a working artifact URL.
- Ask for the same animation with an external audio track and receive a muxed `mp4`.
- Give an invalid or underspecified request and confirm the model self-repairs through `validate_animation`.
- Confirm output arrives comfortably within the Lambda timeout budget.
- Confirm artifacts expire and are deleted by lifecycle policy.

## Assumptions and Defaults

- Audio, when requested, is supplied externally by the caller.
- Timing sidecars are optional and explicit; Kaivra does not synthesize or infer them from narration.
- Private beta uses the **AWS Function URL** domain; custom domain is deferred.
- The current render performance is good enough for synchronous v1 handling.
- Public store submission happens only after the private beta proves the prompt/tool loop is reliable.
- Claude support is a later packaging step because the backend will already be a generic remote MCP service.

## References

- OpenAI Apps SDK deploy/auth/security docs: [developers.openai.com/apps-sdk](https://developers.openai.com/apps-sdk/)
- AWS Lambda container image limits: [AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- AWS Lambda timeout: [AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html)
- AWS Lambda ephemeral storage: [AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-ephemeral-storage.html)
- AWS Lambda quotas: [AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
