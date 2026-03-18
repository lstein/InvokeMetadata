"""Tests for parsing InvokeAI generation metadata across all format versions."""

import json
from pathlib import Path

import pytest

from invoke_metadata.metadata import InvokeGenerationMetadataAdapter
from invoke_metadata.generation.invoke2metadata import InvokeGenerationMetadata2
from invoke_metadata.generation.invoke3metadata import InvokeGenerationMetadata3
from invoke_metadata.generation.invoke5metadata import InvokeGenerationMetadata5

EXAMPLES_DIR = Path(__file__).parent / "example_jsons"


def load_example(name: str) -> dict:
    with open(EXAMPLES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def adapter():
    return InvokeGenerationMetadataAdapter()


# ─── Version detection ───────────────────────────────────────────────


class TestVersionDetection:
    """Verify that the adapter assigns the correct metadata_version."""

    @pytest.mark.parametrize(
        "filename,expected_version",
        [
            ("example1.json", 5),   # app_version 6.10.0.post1
            ("example2.json", 5),   # app_version 6.11.0.rc1, ref_images
            ("example3.json", 5),   # app_version 6.11.0.post1, loras
            ("example4.json", 3),   # no app_version, old-style model object
            ("example5.json", 5),   # canvas_v2_metadata present
            ("example6.json", 5),   # canvas_v2_metadata + controlLayers
            ("example7.json", 5),   # canvas_v2_metadata + referenceImages
            ("example8.json", 5),   # canvas_v2_metadata, complex regional guidance
            ("example9.json", 3),   # app_version 3.0.2post1, model is object
            ("example10.json", 5),  # app_version 4.2.3, control_layers
            ("example11.json", 2),  # app_version v2.2.4, model_weights
            ("example12.json", 2),  # app_version 2.3.1.post2, model_weights
        ],
    )
    def test_version_detection(self, adapter, filename, expected_version):
        data = load_example(filename)
        result = adapter.parse(data)
        assert result.metadata_version == expected_version


# ─── V2 metadata ─────────────────────────────────────────────────────


class TestV2Metadata:
    """Test parsing of InvokeAI v1.x/v2.x metadata (metadata_version=2)."""

    def test_example11_basic_fields(self, adapter):
        result = adapter.parse(load_example("example11.json"))
        assert isinstance(result, InvokeGenerationMetadata2)
        assert result.model == "stable diffusion"
        assert result.model_weights == "stable-diffusion-1.5"
        assert result.app_id == "invoke-ai/InvokeAI"
        assert result.app_version == "v2.2.4"

    def test_example11_image_with_prompt_list(self, adapter):
        result = adapter.parse(load_example("example11.json"))
        assert result.image is not None
        assert isinstance(result.image.prompt, list)
        assert result.image.prompt[0].prompt == "waitress serving banana sushi [bad anatomy] [extra limbs]"
        assert result.image.prompt[0].weight == 1.0
        assert result.image.steps == 30
        assert result.image.cfg_scale == 7.5
        assert result.image.seed == 2519998931
        assert result.image.width == 576
        assert result.image.height == 704
        assert result.image.sampler == "k_euler_a"

    def test_example12_string_prompt(self, adapter):
        result = adapter.parse(load_example("example12.json"))
        assert isinstance(result, InvokeGenerationMetadata2)
        assert result.model_weights == "realisticVision-1.3"
        assert result.app_version == "2.3.1.post2"
        assert result.image is not None
        assert result.image.prompt == "banana sushi"
        assert result.image.steps == 40
        assert result.image.cfg_scale == 8.5
        assert result.image.seed == 514487059

    def test_v2_roundtrip_serialization(self, adapter):
        """Parsed v2 metadata should serialize without None fields."""
        data = load_example("example11.json")
        result = adapter.parse(data)
        serialized = result.model_dump()
        assert None not in serialized.values()


# ─── V3 metadata ─────────────────────────────────────────────────────


class TestV3Metadata:
    """Test parsing of InvokeAI v3.x metadata (metadata_version=3)."""

    def test_example4_basic_fields(self, adapter):
        result = adapter.parse(load_example("example4.json"))
        assert isinstance(result, InvokeGenerationMetadata3)
        assert result.positive_prompt == "washing machine schematic"
        assert result.negative_prompt == ""
        assert result.width == 1024
        assert result.height == 1024
        assert result.seed == 2833093276
        assert result.cfg_scale == 7.5
        assert result.steps == 24
        assert result.scheduler == "euler"

    def test_example4_old_style_model(self, adapter):
        result = adapter.parse(load_example("example4.json"))
        assert result.model is not None
        assert result.model.name == "miamodelSFWNSFWSDXL_v30"
        assert result.model.base == "sdxl"
        assert result.model.type == "main"

    def test_example4_vae(self, adapter):
        result = adapter.parse(load_example("example4.json"))
        assert result.vae is not None
        assert result.vae.name == "sdxl-vae-fp16-fix"
        assert result.vae.base == "sdxl"

    def test_example4_style_prompts(self, adapter):
        result = adapter.parse(load_example("example4.json"))
        assert result.positive_style_prompt == "washing machine schematic"
        assert result.negative_style_prompt == ""

    def test_example9_with_app_version(self, adapter):
        result = adapter.parse(load_example("example9.json"))
        assert isinstance(result, InvokeGenerationMetadata3)
        assert result.app_version == "3.0.2post1"
        assert result.positive_prompt == "naiad"
        assert result.negative_prompt == "underwater"
        assert result.clip_skip == 0
        assert result.model.name == "miamodelSFWNSFWSDXL_v20"

    def test_example9_empty_lists(self, adapter):
        """Empty controlnets and loras should parse without error."""
        result = adapter.parse(load_example("example9.json"))
        assert result.controlnets == []
        assert result.loras == []

    def test_v3_roundtrip_serialization(self, adapter):
        data = load_example("example9.json")
        result = adapter.parse(data)
        serialized = result.model_dump()
        assert None not in serialized.values()


# ─── V5 metadata ─────────────────────────────────────────────────────


class TestV5Metadata:
    """Test parsing of InvokeAI v4.x/v5.x/v6.x metadata (metadata_version=5)."""

    def test_example1_flux2(self, adapter):
        result = adapter.parse(load_example("example1.json"))
        assert isinstance(result, InvokeGenerationMetadata5)
        assert result.positive_prompt == "banana sushi"
        assert result.generation_mode == "flux2_txt2img"
        assert result.width == 880
        assert result.height == 1184
        assert result.seed == 1838945597
        assert result.steps == 4
        assert result.scheduler == "euler"

    def test_example1_model_object(self, adapter):
        result = adapter.parse(load_example("example1.json"))
        assert result.model is not None
        assert result.model.name == "FLUX.2 Klein 4B (FP8)"
        assert result.model.base == "flux2"

    def test_example1_qwen3_encoder(self, adapter):
        result = adapter.parse(load_example("example1.json"))
        assert result.qwen3_encoder is not None
        assert result.qwen3_encoder.name == "Z-Image Qwen3 Text Encoder (quantized)"

    def test_example2_ref_images_normalization(self, adapter):
        """ref_images with nested original.image structure should be flattened."""
        result = adapter.parse(load_example("example2.json"))
        assert result.ref_images is not None
        assert len(result.ref_images) == 1
        ref = result.ref_images[0]
        assert ref.id == "reference_image:8uqXYADhoU"
        assert ref.isEnabled is True
        assert ref.config.type == "flux2_reference_image"

    def test_example3_loras(self, adapter):
        result = adapter.parse(load_example("example3.json"))
        assert result.loras is not None
        assert len(result.loras) == 2
        assert result.loras[0].model.name == "anime_lora"
        assert result.loras[0].weight == 0.75
        assert result.loras[1].model.name == "color_adjust"

    def test_example3_t5_and_clip(self, adapter):
        result = adapter.parse(load_example("example3.json"))
        assert result.t5_encoder is not None
        assert result.t5_encoder.name == "t5_base_encoder"
        assert result.clip_embed_model is not None
        assert result.clip_embed_model.name == "clip-vit-large-patch14"

    def test_example3_guidance(self, adapter):
        result = adapter.parse(load_example("example3.json"))
        assert result.guidance == 4

    def test_example3_empty_ref_images(self, adapter):
        result = adapter.parse(load_example("example3.json"))
        assert result.ref_images == []

    def test_example10_control_layers(self, adapter):
        result = adapter.parse(load_example("example10.json"))
        assert result.control_layers is not None
        assert len(result.control_layers.layers) == 1
        layer = result.control_layers.layers[0]
        assert layer.type == "ip_adapter_layer"
        assert layer.is_enabled is True

    def test_example10_loras(self, adapter):
        result = adapter.parse(load_example("example10.json"))
        assert result.loras is not None
        assert len(result.loras) == 2
        assert result.loras[0].model.name == "cyborg_style_xl-alpha"
        assert result.loras[0].weight == 2.0
        assert result.loras[1].model.name == "color_adjust"
        assert result.loras[1].weight == 4.0


class TestV5CanvasMetadata:
    """Test parsing of canvas_v2_metadata structures."""

    def test_example5_canvas_inpaint_mask(self, adapter):
        result = adapter.parse(load_example("example5.json"))
        assert result.canvas_v2_metadata is not None
        masks = result.canvas_v2_metadata.inpaint_masks
        assert masks is not None
        assert len(masks) == 1
        assert len(masks[0].objects) > 0

    def test_example5_canvas_raster_layers(self, adapter):
        result = adapter.parse(load_example("example5.json"))
        layers = result.canvas_v2_metadata.raster_layers
        assert layers is not None
        assert len(layers) == 2

    def test_example6_canvas_control_layers(self, adapter):
        result = adapter.parse(load_example("example6.json"))
        layers = result.canvas_v2_metadata.control_layers
        assert layers is not None
        assert len(layers) == 1

    def test_example7_canvas_reference_images(self, adapter):
        result = adapter.parse(load_example("example7.json"))
        refs = result.canvas_v2_metadata.reference_images
        assert refs is not None
        assert len(refs) == 1

    def test_example8_canvas_regional_guidance(self, adapter):
        result = adapter.parse(load_example("example8.json"))
        regions = result.canvas_v2_metadata.regional_guidance
        assert regions is not None
        assert len(regions) == 3


# ─── Serialization ───────────────────────────────────────────────────


class TestSerialization:
    """All parsed metadata should roundtrip through model_dump without None values."""

    @pytest.mark.parametrize("filename", [f"example{i}.json" for i in range(1, 13)])
    def test_no_none_in_serialized(self, adapter, filename):
        data = load_example(filename)
        result = adapter.parse(data)
        serialized = result.model_dump()

        def check_no_none(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert v is not None, f"None value at {path}.{k}"
                    check_no_none(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_no_none(item, f"{path}[{i}]")

        check_no_none(serialized)

    @pytest.mark.parametrize("filename", [f"example{i}.json" for i in range(1, 13)])
    def test_all_examples_parse_successfully(self, adapter, filename):
        """Every example JSON should parse without raising exceptions."""
        data = load_example(filename)
        result = adapter.parse(data)
        assert result is not None
        assert result.metadata_version in (2, 3, 5)
