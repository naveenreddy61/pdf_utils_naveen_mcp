# PDF MCP Server

A powerful Model Context Protocol (MCP) server that enables AI assistants like Claude to interact with PDF documents using PyMuPDF. This server provides tools for extracting table of contents, page ranges, and other PDF manipulation capabilities.

## Features

- **Table of Contents Extraction**: Extract complete TOC/bookmarks from PDF files
- **Page Range Extraction**: Extract specific page ranges into new PDF files  
- **Page to Image Conversion**: Convert PDF pages to high-quality PNG or JPEG images
- **Text Extraction**: Extract text from PDF pages with optional Markdown formatting
- **Robust Error Handling**: Comprehensive error handling for invalid files and ranges
- **Fast PDF Processing**: Powered by PyMuPDF for efficient document processing
- **Smart File Management**: Files are saved in the same directory as the source with 'mcp_' prefix

## Prerequisites

- **Python 3.12+**: Required for running the server
- **uv**: Recommended for dependency management (install with `pip install uv`)

## Installation

### For Development

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd pdf-mcp-server
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Test the installation**:
   ```bash
   uv run pdf-mcp-server
   ```

### For Production

Install directly from the repository:
```bash
pip install git+<repository-url>
```

## Claude Desktop Configuration

To use this MCP server with Claude Desktop, you need to add it to your Claude Desktop configuration file.

### Configuration File Location

The configuration file is located at:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Setup Instructions

1. **Open Claude Desktop Settings**:
   - Go to Settings → Developer → Edit Config
   - This will create and open `claude_desktop_config.json`

2. **Add the PDF MCP Server configuration**:

   **Option A: Using uv (recommended)**
   ```json
   {
     "mcpServers": {
       "pdf-tools": {
         "command": "uv",
         "args": [
           "run", 
           "--directory", 
           "/path/to/pdf-mcp-server", 
           "pdf-mcp-server"
         ],
         "env": {}
       }
     }
   }
   ```

   **Option B: Using global installation**
   ```json
   {
     "mcpServers": {
       "pdf-tools": {
         "command": "pdf-mcp-server",
         "args": [],
         "env": {}
       }
     }
   }
   ```

   **Option C: Using uvx from GitHub (no local setup needed)**
   ```json
   {
     "mcpServers": {
       "pdf-tools": {
         "command": "uvx",
         "args": [
           "--from", 
           "git+https://github.com/naveenreddy61/pdf_utils_naveen_mcp_server",
           "pdf-mcp-server"
         ]
       }
     }
   }
   ```

   **Option D: Using uvx from local repository**
   ```json
   {
     "mcpServers": {
       "pdf-tools": {
         "command": "uvx",
         "args": [
           "--from", 
           "/path/to/pdf_utils_naveen_mcp_server",
           "pdf-mcp-server"
         ]
       }
     }
   }
   ```

   **Option E: Using Python directly**
   ```json
   {
     "mcpServers": {
       "pdf-tools": {
         "command": "python",
         "args": [
           "-m", 
           "pdf_mcp_server"
         ],
         "env": {
           "PYTHONPATH": "/path/to/pdf-mcp-server/src"
         }
       }
     }
   }
   ```

3. **Choose the best option for your setup**:
   - **Option A (uv)**: Best if you have the repository locally and want to use uv's project management
   - **Option B (global)**: Best if you've installed the package globally with pip
   - **Option C (uvx + GitHub)**: **Recommended for easy setup** - no cloning or local setup needed! Perfect for Windows users.
   - **Option D (uvx + local)**: Best if you have the repo cloned locally but don't want to manage virtual environments
   - **Option E (Python)**: Advanced users who want full control over the Python environment

4. **Benefits of uvx options (C & D)**:
   - **No virtual environment management**: uvx creates temporary isolated environments automatically
   - **No dependency installation**: uvx handles all dependencies transparently  
   - **No uv sync required**: Skip the manual environment setup step
   - **Perfect for testing**: Great for trying out the server without commitment
   - **Cross-platform**: Works consistently on Windows, macOS, and Linux

5. **Update paths if needed**: 
   - For local options (A, D, E): Replace `/path/to/pdf_utils_naveen_mcp_server` with your actual repository path
   - For GitHub option (C): No path changes needed!

6. **Restart Claude Desktop**: Close and reopen Claude Desktop for the changes to take effect.

7. **Verify the setup**: Look for the MCP tools icon in Claude Desktop, indicating that your tools are available.

### Testing the Integration

Once configured, you can test the integration by asking Claude:

```
"Can you get the table of contents from the PDF at /path/to/sample.pdf?"
```

```
"Please extract pages 1-5 from /path/to/document.pdf"
```

```
"Convert pages 1-3 of /path/to/document.pdf to PNG images at 300 DPI"
```

```
"Extract the text from pages 10-15 of /path/to/manual.pdf as Markdown"
```

## Usage

### Available Tools

#### `get_table_of_contents(path: str)`

Extracts the table of contents (bookmarks) from a PDF file.

**Parameters:**
- `path` (str): Absolute path to the PDF file

**Returns:**
- List of lists: `[[level, title, page_number], ...]`
- Example: `[[1, "Introduction", 1], [2, "Chapter 1", 5], [3, "Section 1.1", 7]]`

**Example Usage in Claude Desktop:**
```
"Get the table of contents for /Users/john/Documents/manual.pdf"
```

#### `get_pages_from_pdf(pdf_path: str, start_page: int, end_page: int)`

Extracts a range of pages from a PDF and creates a new PDF file.

**Parameters:**
- `pdf_path` (str): Absolute path to the source PDF
- `start_page` (int): Starting page number (1-based, inclusive)
- `end_page` (int): Ending page number (1-based, inclusive)

**Returns:**
- str: Absolute path to the newly created PDF file (saved with 'mcp_' prefix)

**Example Usage in Claude Desktop:**
```
"Extract pages 10-15 from /Users/john/Documents/report.pdf"
```

#### `get_pages_as_images(pdf_path: str, start_page: int, end_page: int, dpi: int = 150, image_format: str = "png")`

Converts a range of pages from a PDF to image files.

**Parameters:**
- `pdf_path` (str): Absolute path to the source PDF
- `start_page` (int): Starting page number (1-based, inclusive)
- `end_page` (int): Ending page number (1-based, inclusive)
- `dpi` (int, optional): Resolution in dots per inch (default: 150)
- `image_format` (str, optional): Output format - "png" or "jpg" (default: "png")

**Returns:**
- List[str]: List of absolute paths to the created image files

**Example Usage in Claude Desktop:**
```
"Convert pages 1-5 of /Users/john/Documents/presentation.pdf to PNG images at 300 DPI"
```

#### `extract_text_from_pages(pdf_path: str, start_page: int, end_page: int, markdown: bool = True)`

Extracts text from a range of pages in a PDF.

**Parameters:**
- `pdf_path` (str): Absolute path to the PDF file
- `start_page` (int): Starting page number (1-based, inclusive)
- `end_page` (int): Ending page number (1-based, inclusive)
- `markdown` (bool, optional): Return text in Markdown format (default: True)

**Returns:**
- str: Extracted text, optionally formatted as Markdown

**Example Usage in Claude Desktop:**
```
"Extract text from pages 20-25 of /Users/john/Documents/ebook.pdf as Markdown"
```

### Standalone Usage

You can also run the server directly for testing:

```bash
# Start the server
uv run pdf-mcp-server

# The server will listen for MCP requests via STDIO
```

## Development

### Project Structure

```
pdf-mcp-server/
├── src/
│   └── pdf_mcp_server/
│       ├── __init__.py         # Package entry point
│       ├── server.py           # FastMCP server and tool registration
│       └── tools.py            # Core PDF processing logic
├── pyproject.toml              # Project configuration
├── CLAUDE.md                   # Development guidance
└── README.md                   # This file
```

### Adding New Features

1. **Implement the core logic** in `PdfTools` class (`src/pdf_mcp_server/tools.py`)
2. **Register the tool** in `server.py` using the `@mcp.tool` decorator
3. **Add documentation** to this README and `CLAUDE.md`
4. **Test the integration** with Claude Desktop

### Development Commands

```bash
# Install dependencies
uv sync

# Run the server
uv run pdf-mcp-server

# Run tests (if available)
uv run pytest

# Format code (if configured)
uv run black src/
uv run isort src/
```

## Error Handling

The server provides comprehensive error handling for common scenarios:

### FileNotFoundError
**Cause**: The specified PDF file path does not exist  
**Solution**: Verify the file path is absolute and the file exists

### ValueError: Invalid page range
**Cause**: Page numbers are out of bounds or start_page > end_page  
**Example**: Requesting pages 10-15 from a 5-page document  
**Solution**: Check document page count first

### ValueError: PDF has no table of contents
**Cause**: The PDF file doesn't contain embedded bookmarks  
**Solution**: Not all PDFs have TOC data - this is expected for some files

### Permission Errors
**Cause**: Insufficient permissions to read the PDF or write temporary files  
**Solution**: Check file permissions and temporary directory access

## Troubleshooting

### Claude Desktop Issues

**Problem**: MCP tools not appearing in Claude Desktop  
**Solutions:**
- Verify the configuration file syntax is valid JSON
- Check that the file paths in the configuration exist
- Restart Claude Desktop after configuration changes
- Look for error messages in Claude Desktop's developer console

**Problem**: "Command not found" errors  
**Solutions:**
- Ensure `uv` or `uvx` is installed and in your system PATH
- Use absolute paths in the configuration
- Verify the project directory path is correct

**Problem**: uvx GitHub option (Option C) fails  
**Solutions:**
- Check your internet connection for GitHub access
- Verify the repository URL is correct: `git+https://github.com/naveenreddy61/pdf_utils_naveen_mcp_server`
- Try using a local clone with Option D instead
- Ensure Git is installed on your system

**Problem**: uvx local option (Option D) fails  
**Solutions:**
- Verify the repository path exists and contains `pyproject.toml`
- Use absolute paths instead of relative paths
- Check that the console script name `pdf-mcp-server` matches your pyproject.toml
- Ensure the repository has been cloned (not just downloaded as ZIP)

### Server Issues

**Problem**: "Failed to get TOC" or "Failed to extract pages"  
**Solutions:**
- Ensure the PDF file is not password-protected
- Check that the file is a valid PDF (not corrupted)
- Verify file permissions allow reading

**Problem**: Temporary file issues  
**Solutions:**
- Check available disk space
- Verify write permissions to system temp directory
- On Windows, check that temp directory path doesn't contain spaces

### Performance Considerations

- Large PDF files may take longer to process
- Page extraction creates temporary files - ensure adequate disk space
- For high-volume usage, consider implementing cleanup of old temporary files

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Ensure code follows the existing style
5. Submit a pull request

### Code Style

- Follow PEP 8 for Python code
- Use type hints for all function parameters and returns
- Add docstrings for all public functions
- Keep functions focused and single-purpose

## License

This project is provided as-is. See the LICENSE file for details.

## Acknowledgments

- [FastMCP](https://github.com/jlowin/fastmcp) - Excellent MCP framework for Python
- [PyMuPDF](https://pymupdf.readthedocs.io/) - Powerful PDF processing library
- [Model Context Protocol](https://modelcontextprotocol.io/) - Protocol specification
- [Anthropic Claude](https://claude.ai/) - AI assistant integration

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the error messages for specific guidance
3. Create an issue in the repository with detailed information about your setup and the problem

---

**Note**: This server is designed to work with absolute file paths for security and reliability. Always provide full paths when working with PDF files.