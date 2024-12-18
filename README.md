# 📄 Document Analyzer

A user-friendly document analysis tool built with Streamlit and Microsoft's MarkItDown technology. This application enables users to extract and analyze content from various document formats with optional GPT-4o enhancement for image descriptions.

![Document Analyzer Demo](https://github.com/lesteroliver911/doc-markdown/blob/main/misc/doc-markdown-ms.jpg)


## ✨ Features

- **Multi-Format Support**: Analyze a wide range of document formats including PDF, PPTX, DOCX, XLSX, images, audio files, and more
- **GPT-4o Integration**: Image descriptions using OpenAI's GPT-4o
- **Interactive UI**: Simple Intuitive interface built with Streamlit
- **Export Functionality**: Download extracted content in text format
- **Privacy-Focused**: Temporary file handling with secure cleanup
- **Preview**: View document extraction results

## 🚀 Getting Started

### Prerequisites

- Python 3.7+
- OpenAI API key (optional, for GPT-4 enhancement)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/lesteroliver911/doc-markdown.git
cd document-analyzer
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
# Create .env file
touch .env

# Add your OpenAI API key (optional)
echo "OPENAI_API_KEY=your_api_key_here" >> .env
```

4. Run the application:
```bash
streamlit run app.py
```

## 💻 Usage

1. Launch the application
2. Upload your document using the sidebar
3. Toggle GPT-4o enhancement if desired
4. View extracted content and document information in the respective tabs
5. Download the extracted content as needed

## 📋 Supported Formats

- PDF documents
- PowerPoint presentations (PPTX)
- Word documents (DOCX)
- Excel spreadsheets (XLSX)
- Images (JPG, PNG) with EXIF data and OCR
- Audio files (MP3, WAV) with EXIF data and transcription
- HTML files
- Text-based files (CSV, JSON, XML)

## ⚙️ Configuration

The application can be configured using environment variables or through the UI:

- `OPENAI_API_KEY`: Your OpenAI API key for GPT-4 enhancement
- Custom API key input available in the UI
- Cache management with built-in clearing functionality


## 📝 License & MS Repo

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Orginal MS Markitdown repo: https://github.com/microsoft/markitdown

## 🙏 Acknowledgments

- Microsoft MarkItDown technology
- Streamlit framework
- OpenAI GPT-4o (optional integration)

---
Made with ❤️ by Lester Oliver
