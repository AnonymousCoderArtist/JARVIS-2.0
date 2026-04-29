"""Document processing tools"""

import os

from .base import BaseTool, ToolInput, ToolOutput


class ReadPDFTool(BaseTool):
    """Tool for reading PDF files (OpenClaude style)"""

    name = "read_pdf"
    description = """Extract text from a PDF file. Use this for processing PDF documents, research papers, and other PDF content.

Usage:
- Provide the absolute or relative path to the PDF file
- Use the pages parameter to control which pages to extract:
  - 'all' for entire document (default)
  - '1-5' for page range
  - '3' for single page
- For large PDFs (more than 10 pages), use the pages parameter to read specific ranges
- Maximum 20 pages per request for performance
- Returns extracted text content from the specified pages
- Useful for document analysis, research, and information extraction"""
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the PDF file to read",
                "minLength": 1
            },
            "pages": {
                "type": "string",
                "description": "Page range to extract: 'all' for entire document, '1-5' for range, or '3' for single page",
                "default": "all",
                "pattern": r"^(all|\d+(-\d+)?)$"
            }
        },
        "required": ["path"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            path = getattr(input_data, "path", None)
            pages = getattr(input_data, "pages", "all")

            if not isinstance(path, str) or not path:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid PDF path",
                )

            if not isinstance(pages, str):
                pages = "all"

            if not os.path.exists(path):
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"PDF file not found: {path}"
                )

            # Try to use PyPDF2
            try:
                import PyPDF2

                with open(path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    total_pages = len(pdf_reader.pages)

                    if pages == "all":
                        page_range = range(total_pages)
                    else:
                        # Parse page range (e.g., "1-5")
                        if "-" in pages:
                            start, end = map(int, pages.split("-"))
                            page_range = range(start - 1, min(end, total_pages))
                        else:
                            page_num = int(pages) - 1
                            page_range = [page_num] if page_num < total_pages else []

                    text = ""
                    for page_num in page_range:
                        page = pdf_reader.pages[page_num]
                        text += page.extract_text() + "\n"

                    return ToolOutput(
                        success=True,
                        result=text,
                        metadata={"path": path, "pages_extracted": len(page_range)}
                    )

            except ImportError:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="PyPDF2 not installed. Install with: pip install PyPDF2"
                )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to read PDF: {str(e)}"
            )
