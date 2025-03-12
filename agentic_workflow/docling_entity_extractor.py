"""
Docling-based Entity Extraction Agent

This module implements entity extraction using Docling, which provides better
document processing capabilities, especially for PDFs with complex layouts.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

# Import standard modules - these will be available in any Python environment
import re
import requests
from PIL import Image
import io
import base64

# Optional imports - these may not be available if Docling isn't installed
try:
    from docling.document_converter import DocumentConverter
    from docling.formats import InputFormat, PdfFormatOption
    from docling.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DoclingEntityExtractor:
    """
    Entity extraction agent using Docling for PDF processing.
    
    This class provides enhanced document understanding by leveraging Docling's
    ability to preserve structure, perform OCR, and handle complex layouts.
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize the Docling-based entity extractor.
        
        Args:
            api_key: OpenAI API key (optional, used as fallback if Docling fails)
            model: OpenAI model name (optional, used as fallback)
        """
        self.api_key = api_key
        self.model = model
        
        # Check if Docling is available
        if not DOCLING_AVAILABLE:
            logger.warning("Docling is not available. Install with: pip install docling")
            logger.warning("Falling back to OpenAI-based extraction when needed")
        
        # Initialize Docling converter with OCR options if available
        if DOCLING_AVAILABLE:
            # Configure pipeline options for PDFs
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True  # Ensure OCR is applied when needed
            
            # Set up OCR options using Tesseract
            pipeline_options.ocr_options = TesseractCliOcrOptions()
            
            # Create the document converter with the PDF options
            self.converter = DocumentConverter(format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            })
        else:
            self.converter = None
        
        # Initialize spaCy for entity recognition if available
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("SpaCy NER model loaded successfully")
            except:
                logger.warning("Could not load spaCy model. Run: python -m spacy download en_core_web_sm")
                self.nlp = None
        else:
            self.nlp = None
    
    def extract_entities_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract entities from a PDF file using Docling.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted entities
        """
        if not DOCLING_AVAILABLE or self.converter is None:
            logger.warning("Docling not available. Using fallback method.")
            return self.fallback_extract_entities(pdf_path)
        
        try:
            # Convert the PDF to Docling's internal representation
            result = self.converter.convert(pdf_path)
            docling_doc = result.document
            
            # Extract text content
            text_content = docling_doc.export_to_text()
            
            # Process the text with spaCy for named entity recognition
            if SPACY_AVAILABLE and self.nlp is not None:
                entities = self._extract_entities_with_spacy(text_content)
            else:
                entities = self._extract_entities_manually(text_content)
            
            # Get document structure information
            structure = self._extract_document_structure(docling_doc)
            
            return {
                "text": text_content,
                "entities": entities,
                "structure": structure
            }
            
        except Exception as e:
            logger.error(f"Error extracting entities with Docling: {str(e)}")
            return self.fallback_extract_entities(pdf_path)
    
    def extract_entities_from_image(self, image_data: str, classification: str = "REGULAR") -> Dict[str, Any]:
        """
        Extract entities from a base64-encoded image.
        
        Args:
            image_data: Base64-encoded image data
            classification: Page classification (TOC, REGULAR, HYBRID)
            
        Returns:
            Dictionary containing extracted entities
        """
        # Save image to a temporary file for Docling processing
        temp_image_path = self._save_temp_image(image_data)
        
        try:
            if DOCLING_AVAILABLE and self.converter is not None:
                # Process the image with Docling
                result = self.converter.convert(temp_image_path)
                docling_doc = result.document
                
                # Extract text content
                text_content = docling_doc.export_to_text()
                
                # Process differently based on classification
                if classification in ["FULL_TOC", "HYBRID"]:
                    return self._process_toc_content(text_content, docling_doc)
                else:
                    return self._process_regular_content(text_content, docling_doc)
            else:
                # Fall back to the OpenAI-based extraction
                return self.fallback_extract_from_image(image_data, classification)
                
        except Exception as e:
            logger.error(f"Error extracting entities from image: {str(e)}")
            return self.fallback_extract_from_image(image_data, classification)
        finally:
            # Clean up temporary file
            if os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except:
                    pass
    
    def _save_temp_image(self, base64_image: str) -> str:
        """Save a base64 image to a temporary file."""
        try:
            # Decode the base64 image
            image_data = base64.b64decode(base64_image)
            image = Image.open(io.BytesIO(image_data))
            
            # Create a temporary file
            temp_path = "temp_image.png"
            image.save(temp_path)
            
            return temp_path
        except Exception as e:
            logger.error(f"Error saving temporary image: {str(e)}")
            return ""
    
    def _extract_entities_with_spacy(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities using spaCy."""
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char
            })
        
        return entities
    
    def _extract_entities_manually(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using regex patterns when spaCy is not available."""
        entities = []
        
        # Extract potential product categories with simple patterns
        category_patterns = [
            r"(?:^|\n)\s*[•\-*]\s*(.+?)(?:$|\n)",  # Bullet points
            r"(?:^|\n)([A-Z][A-Za-z\s&\-:]{3,})(?:$|\n)",  # Capitalized lines
        ]
        
        for pattern in category_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.strip():
                    entities.append({
                        "text": match.strip(),
                        "label": "PRODUCT_CATEGORY",
                        "start": text.find(match),
                        "end": text.find(match) + len(match)
                    })
        
        return entities
    
    def _extract_document_structure(self, docling_doc) -> Dict[str, Any]:
        """Extract document structure information from Docling document."""
        try:
            structure = {
                "page_count": len(docling_doc.pages),
                "sections": [],
                "tables": []
            }
            
            # Extract section information
            for section in docling_doc.sections:
                structure["sections"].append({
                    "title": section.title if hasattr(section, "title") else "",
                    "level": section.level if hasattr(section, "level") else 0,
                    "text": section.text if hasattr(section, "text") else ""
                })
            
            # Extract table information if available
            for page in docling_doc.pages:
                for table in getattr(page, "tables", []):
                    structure["tables"].append({
                        "page": page.page_number,
                        "rows": len(getattr(table, "rows", [])),
                        "columns": len(getattr(table, "columns", []))
                    })
            
            return structure
        except:
            return {"page_count": 0, "sections": [], "tables": []}
    
    def _process_toc_content(self, text_content: str, docling_doc) -> Dict[str, Any]:
        """Process Table of Contents content."""
        # Extract bullet points or list items
        bullet_points = []
        
        # Look for bullet points in the text (different patterns)
        patterns = [
            r"(?:^|\n)\s*[•\-*]\s*(.+?)(?:$|\n)",  # Standard bullet points
            r"(?:^|\n)(\d+\.\s+.+?)(?:$|\n)",      # Numbered items
            r"(?:^|\n)([A-Z][A-Za-z\s&\-:]{3,})(?:$|\n)"  # Capitalized lines (potential categories)
        ]
        
        # Try each pattern
        for pattern in patterns:
            matches = re.findall(pattern, text_content)
            for match in matches:
                if match.strip() and len(match.strip()) > 3:  # Skip very short items
                    bullet_points.append(match.strip())
        
        # If Docling document has section info, use it
        try:
            for section in docling_doc.sections:
                if hasattr(section, "title") and section.title and section.title not in bullet_points:
                    bullet_points.append(section.title)
        except:
            pass
            
        # Ensure unique items while preserving order
        seen = set()
        unique_bullet_points = []
        for item in bullet_points:
            if item not in seen:
                seen.add(item)
                unique_bullet_points.append(item)
        
        # Return in the expected format for TOC extraction
        return {
            "offensive_content_category": "Firearms & Accessories",
            "sub_categories": unique_bullet_points,
            "guidelines": [],
            "rules": []
        }
    
    def _process_regular_content(self, text_content: str, docling_doc) -> Dict[str, Any]:
        """Process regular page content."""
        # Extract key entities
        sub_categories = []
        guidelines = []
        rules = []
        
        # Use spaCy for entity extraction if available
        if SPACY_AVAILABLE and self.nlp is not None:
            doc = self.nlp(text_content)
            
            # Look for potential categories/subcategories
            for ent in doc.ents:
                if ent.label_ in ["PRODUCT", "ORG", "WORK_OF_ART"]:
                    sub_categories.append(ent.text)
        
        # Use regex patterns to find potential guidelines and rules
        guideline_pattern = r"(?:^|\n)(?:Guidelines?|Note|Important)(?::|\.)\s*(.+?)(?:$|\n)"
        rule_pattern = r"(?:^|\n)(?:Rule|Regulation|Prohibition|Policy)(?::|\.)\s*(.+?)(?:$|\n)"
        
        guideline_matches = re.findall(guideline_pattern, text_content, re.IGNORECASE)
        for match in guideline_matches:
            if match.strip():
                guidelines.append({"description": match.strip()})
        
        rule_matches = re.findall(rule_pattern, text_content, re.IGNORECASE)
        for match in rule_matches:
            if match.strip():
                rules.append({
                    "type": "policy_rule",
                    "description": match.strip(),
                    "status": "PROHIBITS"  # Default to prohibits
                })
        
        # If no subcategories were found, try extracting from section titles
        if not sub_categories:
            try:
                for section in docling_doc.sections:
                    if hasattr(section, "title") and section.title:
                        sub_categories.append(section.title)
            except:
                pass
        
        # Return in the expected format for regular page extraction
        return {
            "offensive_content_category": "Firearms & Accessories",
            "sub_categories": sub_categories,
            "guidelines": guidelines,
            "rules": rules
        }
    
    def fallback_extract_entities(self, pdf_path: str) -> Dict[str, Any]:
        """Fallback method when Docling is not available."""
        logger.warning(f"Using fallback extraction for PDF: {pdf_path}")
        return {
            "text": "Extraction failed - Docling not available",
            "entities": [],
            "structure": {"page_count": 0, "sections": [], "tables": []}
        }
    
    def fallback_extract_from_image(self, image_data: str, classification: str) -> Dict[str, Any]:
        """Fallback to OpenAI extraction when Docling is not available."""
        logger.warning("Using OpenAI fallback for image extraction")
        
        # Check if we have API key for OpenAI
        if not self.api_key or not self.model:
            return {
                "offensive_content_category": "Firearms & Accessories",
                "sub_categories": [],
                "guidelines": [],
                "rules": []
            }
        
        # Import the existing EntityExtractorAgent for fallback
        try:
            from entity_extractor import EntityExtractorAgent
            
            # We need to load prompts
            with open("toc_system_prompt.txt", "r") as f:
                toc_system_prompt = f.read()
            with open("toc_extraction_prompt.txt", "r") as f:
                toc_user_prompt = f.read()
            with open("entity_system_prompt.txt", "r") as f:
                std_system_prompt = f.read()
            with open("entity_extraction_prompt.txt", "r") as f:
                std_user_prompt = f.read()
                
            # Create the fallback extractor
            fallback_extractor = EntityExtractorAgent(
                api_key=self.api_key,
                model=self.model,
                toc_prompt_system=toc_system_prompt,
                toc_prompt_user=toc_user_prompt,
                std_prompt_system=std_system_prompt,
                std_prompt_user=std_user_prompt
            )
            
            # Use the fallback extractor
            return fallback_extractor.extract_entities(classification, image_data)
            
        except Exception as e:
            logger.error(f"Fallback extraction failed: {str(e)}")
            return {
                "offensive_content_category": "Firearms & Accessories",
                "sub_categories": [],
                "guidelines": [],
                "rules": [],
                "error": str(e)
            }