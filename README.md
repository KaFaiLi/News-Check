# News-Check

A Python-based news scraping and analysis tool that fetches, analyzes, and summarizes news articles related to AI, Fintech, and Technology using direct Google News scraping and OpenAI's language models.

## Features

- **News Scraping**: 
  - Direct scraping from Google News search results
  - Customizable keywords and date ranges
  - Robust retry mechanism and error handling
- **Content Analysis**: 
  - Analyzes article relevance using keyword matching and fuzzy string comparison
  - Categorizes articles into AI Development, Fintech, and GenAI Usage
  - Generates insights using OpenAI's language models
- **Document Generation**:
  - Creates brief summaries (top 3 articles)
  - Generates detailed reports with category analysis
  - Includes overall summaries and trend analysis
- **Duplicate Detection**: Removes similar articles using fuzzy matching
- **Error Handling**: Implements robust error handling and retry mechanisms

## Directory Structure

```
News-Check/
├── main.py                        # Main entry point
├── src/
│   ├── __init__.py               # Package initialization
│   ├── news_scraper_simple.py    # News scraping module
│   ├── content_analyzer_simple.py # Content analysis module
│   ├── document_generator.py      # Document generation module
│   ├── config.py                 # Configuration settings
│   └── models.py                 # Data models
├── Output/                       # Generated reports
└── requirements.txt              # Project dependencies
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/News-Check.git
cd News-Check
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure API settings:
- Create a copy of `src/config.py` and name it `src/config_local.py`
- Set your OpenAI API key and base URL
- Adjust other settings as needed

## Usage

1. Run the news analyzer:
```bash
python main.py
```

2. The script will:
- Fetch recent news articles based on configured keywords
- Analyze content relevance and generate insights
- Generate two Word documents in the `Output` directory:
  - `brief_news_summary_[timestamp].docx`: Top 3 most relevant articles
  - `detailed_news_report_[timestamp].docx`: Detailed analysis of top articles

## Configuration

Key settings in `src/config.py`:
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_API_BASE`: API base URL
- `USE_LLM`: Enable/disable LLM analysis
- `LLM_THRESHOLD`: Minimum relevance score for LLM analysis
- `MAX_ARTICLES`: Maximum articles to fetch per keyword
- `REQUEST_TIMEOUT`: Request timeout in seconds
- `OUTPUT_DIR`: Directory for generated reports

## Dependencies

Main dependencies include:
- `requests`: HTTP requests
- `beautifulsoup4`: HTML parsing
- `pandas`: Data manipulation
- `langchain`: LLM integration
- `langchain-openai`: OpenAI integration
- `python-docx`: Word document generation
- `fuzzywuzzy`: String matching
- `Pillow`: Image processing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google News for providing news data
- OpenAI for language model support
- Various open-source libraries used in this project
