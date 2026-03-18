"""
Parse the generation metadata from an InvokeAI PNG image.
"""

from typing import Annotated, Any, List, Optional, Union

from pydantic import Field, TypeAdapter

from .generation.invoke2metadata import InvokeGenerationMetadata2
from .generation.invoke3metadata import InvokeGenerationMetadata3
from .generation.invoke5metadata import (
    InvokeGenerationMetadata5,
    Image,
    Model,
    RefImage,
    RefImageConfig,
)

InvokeGenerationMetadata = Annotated[
    Union[
        InvokeGenerationMetadata2,
        InvokeGenerationMetadata3,
        InvokeGenerationMetadata5,
    ],
    Field(discriminator="metadata_version"),
]


class InvokeGenerationMetadataAdapter:
    def __init__(self):
        self.adapter = TypeAdapter(InvokeGenerationMetadata)
        self.metadata = None

    def parse(self, json_data: dict[str, Any]) -> InvokeGenerationMetadata:
        """
        Parse JSON data into a InvokeGenerationMetadata object.

        :param json_data: Dictionary containing metadata
        :type json_data: dict[str, Any]
        :return: Parsed generation metadata
        :rtype: InvokeGenerationMetadata
        """
        if "metadata_version" not in json_data:
            if "canvas_v2_metadata" in json_data:
                json_data = {"metadata_version": 5, **json_data}
            elif "app_version" in json_data:
                if any(
                    json_data["app_version"].startswith(x) for x in ["v1.", "2.", "v2."]
                ):
                    json_data = {"metadata_version": 2, **json_data}
                elif json_data["app_version"].startswith("3."):
                    if "model" in json_data and isinstance(json_data["model"], str):
                        json_data = {"metadata_version": 2, **json_data}
                    else:
                        json_data = {"metadata_version": 3, **json_data}
                else:
                    json_data = {"metadata_version": 5, **json_data}
            elif "model_weights" in json_data:
                # v2 metadata has model_weights field
                json_data = {"metadata_version": 2, **json_data}
            else:
                json_data = {"metadata_version": 3, **json_data}

        # MOVE THIS CODE TO THE APPROPRIATE MODEL VALIDATOR
        # Normalize ref_images
        if "ref_images" in json_data and json_data["ref_images"]:
            json_data["ref_images"] = self._normalize_ref_images(
                json_data["ref_images"]
            )

        self.metadata = self.adapter.validate_python(json_data)
        return self.metadata

    def _normalize_ref_images(self, ref_images: Any) -> list[dict[str, Any]]:
        """
        Normalize ref_images structure.

        Handles both flat lists and nested lists (list of lists).
        Flattens nested image structure from config.image.original.image to config.image.

        :param ref_images: Raw ref_images data (may be list or list of lists)
        :type ref_images: Any
        :return: Normalized flat list of reference images
        :rtype: list[dict[str, Any]]
        """
        if not isinstance(ref_images, list) or len(ref_images) == 0:
            return ref_images

        # Flatten if it's a list of lists
        if isinstance(ref_images[0], list):
            ref_images = ref_images[0]

        # Normalize nested image structure in ref_images config
        for ref_image in ref_images:
            if (
                "config" in ref_image
                and "image" in ref_image["config"]
                and isinstance(ref_image["config"]["image"], dict)
            ):
                image_obj = ref_image["config"]["image"]
                # If image has ["original"]["image"] nesting, flatten it
                if "original" in image_obj and isinstance(image_obj["original"], dict):
                    if "image" in image_obj["original"]:
                        ref_image["config"]["image"] = image_obj["original"]["image"]

        return ref_images
