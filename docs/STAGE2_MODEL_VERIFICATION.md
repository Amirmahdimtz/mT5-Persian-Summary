# Stage 2 — Model Verification and Runtime Contract

Verified on 2026-10-24 (repository metadata only; **real inference not verified**).

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
- Runtime dependencies: transformers>=4.48,<5; torch>=2.6,<3; sentencepiece>=0.2,<0.3. No direct accelerate/huggingface_hub/safetensors requirement. Windows/Python 3.12 to be verified on user machine.

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
