# Third-party components

Speech screening downloads [Silero VAD](https://github.com/snakers4/silero-vad), MIT licensed by Silero Team, from commit `867c2aa692646a1f1de3e94a15c9dd9f614c0acb`. Its [license](https://github.com/snakers4/silero-vad/blob/867c2aa692646a1f1de3e94a15c9dd9f614c0acb/LICENSE) applies to the model. No model binary is distributed in this repository.

The ONNX input/state/context contract follows the upstream documentation. The local runner uses ONNX Runtime (MIT) and numpy (BSD), installed separately through PyPI. Their packages include their own license notices.
