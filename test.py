# from transformers import AutoModel

# model = AutoModel.from_pretrained("HuggingFaceTB/SmolVLM-256M-Instruct")

from docling.datamodel.pipeline_options import PdfPipelineOptions
desc_opts = PdfPipelineOptions().picture_description_options

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.models.factories import get_picture_description_factory
factory = get_picture_description_factory()
desc_model = factory.create_instance(
    options=desc_opts,
    enabled=True,
    artifacts_path=None,
    accelerator_options=AcceleratorOptions(),
    enable_remote_services=False,
)
