# Apparel Style Guide Entity Extraction

## Overview
This project leverages **Large Language Models (LLM)** to extract structured data from **Apparel Style Guides**, such as those used by Walmart for product listing guidelines. The goal is to process fashion-related content, including **Photo Direction**, **Copy Standards**, **Grouping Standards**, and **Product Naming Guidelines**, in order to transform unstructured content into structured JSON entities.The idea is to use this as KB which Retreivers can be use in RAG Flow.

The solution extracts key information hierarchically, ensuring that the content maintains its intended structure and meaning.
## Key Features
- **Entity Extraction**: Uses LLM to analyze style guide PDFs and extract structured entities such as product categories, image guidelines, copy standards, grouping rules, and more.
- **Photo Direction and Visual Guidelines**: Captures specific image guidelines for apparel, such as front-facing shots, alternate views, and ghost views.
- **Copy Standards**: Extracts rules for writing product descriptions, including tone, voice, and phrasing guidelines.
- **Grouping Standards**: Identifies criteria for grouping similar items based on attributes like fabric, print, and size.
- **Product Name Guidelines**: Extracts standardized naming conventions for apparel products using formulas provided in the guides.

## How it Works
1. **PDF Conversion**: The system converts PDF pages into images for further processing.
2. **LLM-Based Extraction**: Images are processed by a GPT-based LLM model, which extracts entities in a structured JSON format.
3. **Multi-Threaded Processing**: The solution supports multi-threaded image conversion and LLM processing to handle multiple pages in parallel, increasing efficiency.
4. **JSON Output**: Extracted entities are saved as structured JSON files, which capture the hierarchy and guidelines present on each page.

## Configuration
The system uses a configurable `config.json` file to define key parameters, including the LLM model, threading limits, and custom prompts for entity extraction. Below is a sample configuration:

```json
{
  "gpt4_prompt": "Extract entities from this page image...",
  "api_model": "gpt-4o-mini",
  "image_threads": 6,
  "gpt4_threads": 3
}
```

## File Structure
- **/scripts/**: Python scripts for PDF processing, image extraction, and LLM-based entity extraction.
- **/output/**: Stores the extracted JSON files for each processed page.
- **config.json**: Configuration file to customize the model, threading, and prompt behavior.

## How to Run
1. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Make sure `poppler` is installed for PDF to image conversion:
   ```bash
   brew install poppler  # for MacOS users
   ```
3. Run the main processing script:
   ```bash
   python main.py --pdf_path <path_to_pdf>
   ```
   This will convert the PDF to images, process the images using the LLM, and save the output as JSON files in the `/output/` directory.

## Example Output
```json
{
  "apparel_category": "Women's Swimwear",
  "product_type": "Rash Guards",
  "guidelines": {
    "guideline_type": "Photo Direction",
    "details": [
      {
        "step_name": "Hero (Main) Image",
        "description": "Front facing, cropped above lip to below fingertips."
      },
      {
        "step_name": "1st Alternate",
        "description": "Back facing, cropped above lip to below fingertips."
      },
      {
        "step_name": "2nd Alternate",
        "description": "Ghost view."
      }
    ]
  }
}
```

## Conclusion
By using LLMs for entity extraction, we can ensure that fashion retailers adhere to platform-specific guidelines while streamlining the content upload process.