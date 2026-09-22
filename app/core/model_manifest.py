"""Pinned Laya checkpoint manifests shared by every artifact source."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactFile:
    path: str
    sha256: str
    size: int
    runtime_sha256: str | None = None
    runtime_size: int | None = None


@dataclass(frozen=True)
class ModelArtifactSpec:
    name: str
    huggingface_repo: str
    huggingface_revision: str
    modelscope_repo: str
    modelscope_revision: str
    files: tuple[ArtifactFile, ...]


def _file(
    path: str,
    sha256: str,
    size: int,
    *,
    runtime_sha256: str | None = None,
    runtime_size: int | None = None,
) -> ArtifactFile:
    return ArtifactFile(
        path=path,
        sha256=sha256,
        size=size,
        runtime_sha256=runtime_sha256,
        runtime_size=runtime_size,
    )


MODEL_ARTIFACTS: dict[str, ModelArtifactSpec] = {
    "english": ModelArtifactSpec(
        name="english",
        huggingface_repo="convaiinnovations/laya",
        huggingface_revision="1c5edc17a7acd8701df6fc341c0d179f1c62c982",
        modelscope_repo="convaiinnovations/laya",
        modelscope_revision="0d52b645226dc836d8efdb7e9dc197ddca7b98c9",
        files=(
            _file(
                "rl_agent_config.json",
                "ae287b56bbcf5f8c4f4541ae9dfd00c914c4c48b940b8398c3058af37ba92bbd",
                745,
            ),
            _file(
                "model.safetensors",
                "891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c",
                842609210,
            ),
            _file(
                "tokenizer/tokenizer.json",
                "6c8aaa9a542084f2457eab775d4eeb51f92a70c0fd9de28d5edb0ddec3c08d30",
                3583228,
            ),
            _file(
                "tokenizer/tokenizer_config.json",
                "50044de60daaa73df97d262e15a40d4faf0160e7d742df64b377877a1320dd12",
                308,
            ),
            _file(
                "encoder/config.json",
                "bf3ab80598fdccf414855a2ce80f22859e4492d06ca8a62ddd1cfb63972f8979",
                2083,
            ),
        ),
    ),
    "multilingual": ModelArtifactSpec(
        name="multilingual",
        huggingface_repo="convaiinnovations/laya-multilingual",
        huggingface_revision="052592a15d198d9ad47da779604259b10b47b7aa",
        modelscope_repo="convaiinnovations/laya-multilingual",
        modelscope_revision="5ad6e84d70d70edde0d5a3241c5233d0b11cd6b8",
        files=(
            _file(
                "rl_agent_config.json",
                "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6",
                472,
            ),
            _file(
                "model.safetensors",
                "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204",
                643835514,
            ),
            _file(
                "tokenizer/tokenizer.json",
                "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
                34363188,
            ),
            _file(
                "tokenizer/tokenizer_config.json",
                "424b69444bf7b5809dc2cd2e36d0bd71b8055124dd24274d6db3c655d38205e7",
                502,
                runtime_sha256="6c6b2d8e3c84ce0e671c129cd6b374b235d6f9863042a5836358d00a89bbb5a1",
                runtime_size=524,
            ),
            _file(
                "encoder/config.json",
                "83f6916d13ef0f556ac461f28308dc2bffa7ebeadee8ec9e2db5812020ea5bb4",
                1938,
            ),
        ),
    ),
    "typed-decisions": ModelArtifactSpec(
        name="typed-decisions",
        huggingface_repo="convaiinnovations/laya-typed-decisions",
        huggingface_revision="f9ab0b228f0fc0f14d873dbc99038f135c2da1b2",
        modelscope_repo="convaiinnovations/laya-typed-decisions",
        modelscope_revision="9407bd3545af9115f4799f4f4e11801e05b0600b",
        files=(
            _file(
                "rl_agent_config.json",
                "ebf0cd524d92342a6be5e48e9fca3d7c2babfb5a56ccd79d2171ef5d8c7f7be8",
                847,
            ),
            _file(
                "model.safetensors",
                "4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e",
                842609220,
            ),
            _file(
                "tokenizer/tokenizer.json",
                "6c8aaa9a542084f2457eab775d4eeb51f92a70c0fd9de28d5edb0ddec3c08d30",
                3583228,
            ),
            _file(
                "tokenizer/tokenizer_config.json",
                "08d4cf3ac4dca381759441b85b91a6d40e688471dcd33d15d6649eb0a9a854d1",
                337,
            ),
            _file(
                "encoder/config.json",
                "5268d24ad3b77c8151de5dcb0762ba4391619aad9ab0bda33e36fb083cfeae6d",
                2084,
            ),
        ),
    ),
}
