# Stage 2 — Model Verification and Runtime Contract

Model metadata verified on 2026-10-24. **Real CPU inference subsequently verified by the user on Windows/Python 3.12.10 (2026-10-24).**

## Selected checkpoint

- Hugging Face model: nafisehNik/mt5-persian-summary
- Revision: b575560ad967050e77a40f907abb1ebbeefb9a15 (full pinned commit SHA)
- License declared by model card: MIT. Check downstream training-data rights separately.
- Architecture: MT5ForConditionalGeneration / model_type mt5, encoder-decoder, d_model=512, 8 encoder layers and 8 decoder layers. Roughly 300M parameters inferred from the ~1.2 GB FP32 weights, not an audited count.
- Tokenizer: SentencePiece spiece.model (4.31 MB), MT5Tokenizer per model card; AutoTokenizer(use_fast=False).
- Training claimed: Persian news summary using pn_summary and csebuetnlp/xlsum. No guaranteed quality outside this domain.
- Main branch weights: pytorch_model.bin (~1.2 GB); **no merged safetensors checkpoint**. A safetensors conversion exists only in an unmerged PR.
- Max source: model-card example tokenizes at max_length=1000; this is **not an architecture-confirmed maximum**. Stage 2 caps to 1000 input tokens including special tokens, plus 20,000 input characters before tokenization; over-limit input is rejected without truncation.
- Prefix: no special task prefix specified by author; pass plain Persian text.
- Generation: max_length=120 (decoder total tokens), num_beams=2, repetition_penalty=1.0, length_penalty=2.0, early_stopping=True, do_sample=False. Model-card defaults, not validated for every domain.
- Device/lifecycle: CPU default; auto/cuda configurable; float32 model, DI per-process singleton, lazy load, initialization and inference locks, cached initialization failure, model.eval(), torch.inference_mode(), asyncio.to_thread wrapper.
- Resource estimate: >=8 GB free RAM recommended for the first CPU run (engineering estimate, NOT measured). Loading may need substantially more RAM than the 1.2 GB on-disk weights; one worker initially.
- Security: pinned revision, trust_remote_code=False, weights_only=True, no secrets checked in. Pickle-based weights retain supply-chain risk despite restricted unpickling. Published SHA-256: 68308d3bc96137d5a76d457e292400c581b74432a654dc00dfec8926539d57ee.
- Runtime dependencies: transformers>=4.48,<5; torch>=2.6,<3; sentencepiece>=0.2,<0.3. No direct accelerate/huggingface_hub/safetensors requirement. Windows/Python 3.12.10 installed and tested on the user's machine (real CPU smoke passed).

## Alternative evaluated

hosseinmhmdkhani/mt5-small-finetuned-persian-news-summarization has Apache-2.0 metadata, safetensors and reported ROUGE, but its model card lacks training-data and intended-use detail and lists Transformers v5. The verified original candidate was kept for Stage 2. Reassess use of a safetensors-only checkpoint before high-trust production deployment.

## Primary sources

- https://huggingface.co/nafisehNik/mt5-persian-summary
- https://huggingface.co/nafisehNik/mt5-persian-summary/blob/main/config.json
- https://huggingface.co/nafisehNik/mt5-persian-summary/tree/main
- https://huggingface.co/nafisehNik/mt5-persian-summary/commit/b575560ad967050e77a40f907abb1ebbeefb9a15
- https://huggingface.co/nafisehNik/mt5-persian-summary/discussions
- https://huggingface.co/hosseinmhmdkhani/mt5-small-finetuned-persian-news-summarization
- https://huggingface.co/docs/transformers/v4.57.2/en/main_classes/model
- https://pytorch.org/get-started/locally/
- https://docs.pytorch.org/docs/stable/notes/serialization.html

## Verification gate

Python 3.13.5 reconstructed workspace: compileall passed, pytest **36 passed, 0 failed** (20 new model test cases using mocks; 16 Stage-1 regressions). The smoke script was attempted, but **blocked** at dependency import: transformers is not available and the sandbox has restricted networking. Model weights were not downloaded or executed. Windows/Python 3.12 real inference remains **Not Run**; do not mark Stage 2 Completed until a non-empty Persian summary has been produced on the user's machine.

## Windows Real-Model Verification — 2026-10-24

User-supplied PowerShell run against Stage 2 implementation commit `fd6b2a87c66f425133c649caddd594a49b9238a3`:

- Python 3.12.10; PyTorch 2.14.1+cpu; Transformers 4.57.6; SentencePiece 0.2.2.
- `python -m pip check`: no broken requirements.
- `python -m compileall -q src tests`: passed.
- `python -m pytest -q`: **36 passed, one non-fatal third-party deprecation warning**.
- Constructor DI singleton test: `True`.
- `python -m src.infrastructure.ml.smoke_mt5_model`: **Passed — real model and tokenizer downloaded and generated nonempty Persian text:**
  `اعلام کرد که در روزهای آینده در مناطق شمالی کشور بارش باران پیش بینی می شود.`
- The `pytorch_model.bin` download completed (~1.20 GB); cache directory exists. Actual peak RAM and latency were not measured.
- A separate `model.safetensors` progress display reached 13% after the output; do not interpret that as model inference failure or as evidence of a complete safetensors checkpoint. Investigate only if it recurs or consumes unexpected disk bandwidth.
- Health check manual request to `127.0.0.1:8001` could not connect, with no Uvicorn startup shown in this terminal transcript; run `python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001` in a separate shell before testing.
- **Stage 2 acceptance: Completed** for the short-text model integration scope. Production quality, memory profiling and more extensive concurrency stress tests remain within the later hardening stage.
